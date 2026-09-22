import json

from ianest_extended import (
    CoreResult,
    EngramWrite,
    ExtendedConfig,
    MemoryEnricher,
    MemoryIdentity,
    Principal,
    StatedBy,
    TelemetryWriter,
)
from ianest_extended.enrichment import estimate_tokens

from .fakes import InMemoryStore


class SynthesisCore:
    def __init__(self):
        self.calls = []
        self.counter = 0

    def prompt_run(self, prompt, identity, *, model=None, domain=None):
        self.counter += 1
        self.calls.append((prompt, model))
        if prompt.startswith("Extract only literal"):
            response = json.dumps(
                {
                    "from_user": [
                        {
                            "namespace": "facts",
                            "content": prompt.split("USER:\n", 1)[1]
                            .split("\n\nASSISTANT:", 1)[0],
                            "confidence": 1.0,
                            "mentions": [],
                        }
                    ],
                    "from_assistant": [],
                }
            )
        elif prompt.startswith("Summarize the conversation state"):
            response = "Primero era martes; despues el usuario lo cambio a jueves."
        else:
            response = f"respuesta {self.counter}"
        return CoreResult(
            response=response,
            trace={"request_id": f"core-{self.counter}"},
            payload={},
        )


def _identity():
    return MemoryIdentity(user_id="phase9", session_id="thread", service="test")


def _enricher(tmp_path, store, core, **changes):
    return MemoryEnricher(
        store=store,
        core=core,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(
            telemetry_dir=tmp_path,
            embedding_dimension=2,
            rag_enabled=False,
            **changes,
        ),
    )


def _run_turn(enricher, text):
    enricher.enrich(_identity(), text, use_rag=False)


def _summaries(store):
    return [item for item in store.engrams if item.type_name == "thread_summary"]


def test_disabled_is_identical_to_default_and_creates_nothing(tmp_path):
    stores = (InMemoryStore(), InMemoryStore())
    cores = (SynthesisCore(), SynthesisCore())
    default = _enricher(tmp_path / "default", stores[0], cores[0])
    explicit = _enricher(
        tmp_path / "explicit",
        stores[1],
        cores[1],
        thread_synthesis_enabled=False,
    )

    for text in ("la reunion es el martes", "perdona, es el jueves"):
        _run_turn(default, text)
        _run_turn(explicit, text)

    left = default.recall(_identity(), "que dia es?").context
    right = explicit.recall(_identity(), "que dia es?").context
    assert left == right
    assert not _summaries(stores[0])
    assert not _summaries(stores[1])
    assert stores[0].summary_links == stores[1].summary_links == {}
    assert cores[0].calls == cores[1].calls


def test_window_replacement_provenance_composition_cost_and_trace(tmp_path):
    store = InMemoryStore()
    core = SynthesisCore()
    enricher = _enricher(
        tmp_path,
        store,
        core,
        thread_synthesis_enabled=True,
        thread_synthesis_window_turns=2,
        synthesis_model="summary-model",
    )

    _run_turn(enricher, "la reunion es el martes")
    assert not _summaries(store)
    _run_turn(enricher, "perdona, es el jueves")
    first = _summaries(store)
    assert len(first) == 1
    assert first[0].stated_by is StatedBy.UNKNOWN
    assert len(store.summary_links[first[0].id]) >= 4

    baseline = _enricher(
        tmp_path / "baseline",
        store,
        SynthesisCore(),
        thread_synthesis_enabled=False,
    ).recall(_identity(), "que dia es?").context
    synthesized = enricher.recall(_identity(), "que dia es?").context
    assert "[thread_summary/thread]" in synthesized
    assert "la reunion es el martes" not in synthesized
    assert "perdona, es el jueves" not in synthesized
    assert estimate_tokens(synthesized) <= estimate_tokens(baseline)
    assert any(item.content == "la reunion es el martes" for item in store.engrams)

    _run_turn(enricher, "confirma el jueves")
    assert len(_summaries(store)) == 1
    _run_turn(enricher, "queda confirmado")
    summaries = _summaries(store)
    assert len(summaries) == 2
    assert summaries[0].status.value == "archived"
    assert summaries[1].status.value == "active"

    events = [
        json.loads(line)
        for line in next(tmp_path.glob("extended-*.jsonl")).read_text().splitlines()
    ]
    event = [item for item in events if item["event"] == "memory.thread_synthesis"][-1]
    assert event["counters"]["window_turns"] == 2
    assert event["counters"]["turns_summarized"] == 4
    assert event["counters"]["items_summarized"] >= 8
    assert event["model"] == "summary-model"
    assert event["status"] == "ok"


def test_summary_keeps_both_contradiction_sides_and_replaces_the_rest(tmp_path):
    store = InMemoryStore()
    identity = _identity()
    model = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="la clave del refugio es Cobalto",
            identity=identity,
            namespace="facts",
            stated_by=StatedBy.MODEL,
        ),
    )
    user = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="la clave del refugio es Ambar",
            identity=identity,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    store.record_contradiction(
        Principal.EXTENDED,
        stated_by_user=user,
        conflict_threshold=0.5,
        dedup_threshold=0.92,
    )
    ordinary = store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="el inventario tiene tres mantas",
            identity=identity,
            namespace="facts",
            stated_by=StatedBy.USER,
        ),
    )
    store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="La clave vigente es Ambar y hay tres mantas.",
        source_ids=(model.id, user.id, ordinary.id),
        source_trace_id="summary",
    )
    enricher = _enricher(
        tmp_path,
        store,
        SynthesisCore(),
        thread_synthesis_enabled=True,
    )

    context = enricher.recall(identity, "cual es la clave?").context

    assert "[thread_summary/thread]" in context
    assert "el inventario tiene tres mantas" not in context
    user_line = (
        "[episodic/facts] (fuente: usuario) "
        "la clave del refugio es Ambar"
    )
    model_line = (
        "[episodic/facts] (fuente: modelo, sin verificar; "
        "hay una version del usuario sobre esto) "
        "la clave del refugio es Cobalto"
    )
    assert user_line in context
    assert model_line in context
    assert context.index(user_line) < context.index(model_line)

    constrained = enricher.recall(
        identity,
        "cual es la clave?",
        token_budget=35,
    ).context
    assert estimate_tokens(constrained) <= 35
