"""Criterios del paso cero antes de recuperar conocimiento."""

from __future__ import annotations

import json
from pathlib import Path

from ianest_extended import (
    CoreClient,
    CoreResult,
    EngramWrite,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    FakeEmbedder,
    MemoryIdentity,
    MemoryEnricher,
    Principal,
    TelemetryWriter,
)
from ianest_extended.knowledge_gate import GateDecision, KnowledgeGate

from .fakes import InMemoryRagStore, InMemoryStore


class RecordingFakeEmbedder(FakeEmbedder):
    def __init__(self) -> None:
        super().__init__(dimension=16)
        self.batch_calls: list[tuple[str, ...]] = []
        self.embed_calls: list[str] = []

    def embed(self, text: str) -> tuple[float, ...]:
        self.embed_calls.append(text)
        return super().embed(text)

    def embed_many(self, texts):
        self.batch_calls.append(tuple(texts))
        return tuple(FakeEmbedder.embed(self, text) for text in texts)


class RecordingRagStore(InMemoryRagStore):
    def __init__(self) -> None:
        super().__init__(())
        self.query_embeddings = []

    def retrieve(self, query_text, **kwargs):
        self.query_embeddings.append(kwargs.get("query_embedding"))
        return super().retrieve(query_text, **kwargs)


class FixedGate:
    def __init__(self, decision: str) -> None:
        self._decision = decision

    def decide(self, prompt: str) -> GateDecision:
        return GateDecision(
            decision=self._decision,
            score=0.8 if self._decision != "error" else None,
            threshold=0.7,
            nearest="hola" if self._decision != "error" else None,
            embedding=(1.0, 0.0) if self._decision == "search" else None,
        )


class CoreStub:
    def prompt_run(self, prompt, identity, model=None, domain=None):
        return CoreResult(
            response="OK",
            trace={"request_id": "core-test", "finish_reason": "stop"},
            payload={
                "response": "OK",
                "trace": {"request_id": "core-test", "finish_reason": "stop"},
            },
        )


def _config(tmp_path, **changes):
    return ExtendedConfig(
        core_url="http://core.invalid",
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=16,
        write_back_enabled=False,
        knowledge_gate_threshold=0.99,
        **changes,
    )


def _identity():
    return MemoryIdentity(user_id="u", session_id="s", service="test")


def _events(tmp_path):
    return [
        json.loads(line)
        for path in tmp_path.glob("extended-*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]


def test_exact_courtesy_skips_and_other_turn_searches_once_per_phrase_cache(
    tmp_path,
):
    embedder = RecordingFakeEmbedder()
    gate = KnowledgeGate(
        embedder=embedder,
        enabled=True,
        threshold=0.99,
    )

    exact = gate.decide("hola")
    other = gate.decide("explica la fotosintesis con detalle tecnico")

    assert exact.decision == "skip"
    assert other.decision == "search"
    assert len(embedder.batch_calls) == 1
    assert "hola" in embedder.batch_calls[0]
    assert embedder.embed_calls == ["hola", "explica la fotosintesis con detalle tecnico"]


def test_prompt_and_memory_recall_share_gate_and_keep_memory_on_skip(
    tmp_path,
):
    embedder = RecordingFakeEmbedder()
    rag_store = RecordingRagStore()
    store = InMemoryStore()
    service = ExtendedService(
        ExtendedComposition(
            _config(tmp_path),
            core=CoreStub(),
            embedder=embedder,
            memory_store=store,
            rag_store=rag_store,
        )
    )
    identity = _identity()
    store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="recuerdo que debe seguir en contexto",
            identity=identity,
        ),
    )

    prompt_result = service.prompt_run(
        "hola",
        identity,
        use_memory=True,
        use_rag=True,
        write_back=False,
    )
    recall_result = service.memory_recall(
        identity,
        "hola",
        use_memory=True,
        use_rag=True,
    )

    assert prompt_result.payload["knowledge_gate"]["decision"] == "skip"
    assert prompt_result.payload["knowledge"] == {"fragments": 0}
    assert "recuerdo que debe seguir en contexto" in prompt_result.context
    assert recall_result["knowledge_gate"]["decision"] == "skip"
    assert "recuerdo que debe seguir en contexto" in recall_result["context"]
    assert rag_store.query_embeddings == []


def test_search_reuses_the_gate_embedding_for_the_rag_store(
    tmp_path,
):
    embedder = RecordingFakeEmbedder()
    rag_store = RecordingRagStore()
    service = ExtendedService(
        ExtendedComposition(
            _config(tmp_path),
            embedder=embedder,
            memory_store=InMemoryStore(),
            rag_store=rag_store,
        )
    )

    result = service.memory_recall(
        _identity(),
        "explica la fotosintesis con detalle tecnico",
        use_memory=False,
        use_rag=True,
    )

    assert result["knowledge_gate"]["decision"] == "search"
    assert len(rag_store.query_embeddings) == 1
    assert rag_store.query_embeddings[0] is not None
    assert embedder.embed_calls == ["explica la fotosintesis con detalle tecnico"]


def test_not_applied_does_not_embed_when_rag_is_off_or_gate_is_disabled(
    tmp_path,
):
    off_embedder = RecordingFakeEmbedder()
    off_service = ExtendedService(
        ExtendedComposition(
            _config(tmp_path),
            embedder=off_embedder,
            memory_store=InMemoryStore(),
            rag_store=RecordingRagStore(),
        )
    )
    no_rag = off_service.memory_recall(
        _identity(), "pregunta", use_memory=False, use_rag=False
    )

    disabled_embedder = RecordingFakeEmbedder()
    disabled_service = ExtendedService(
        ExtendedComposition(
            _config(tmp_path, knowledge_gate_enabled=False),
            embedder=disabled_embedder,
            memory_store=InMemoryStore(),
            rag_store=RecordingRagStore(),
        )
    )
    disabled = disabled_service.memory_recall(
        _identity(), "pregunta", use_memory=False, use_rag=True
    )

    assert no_rag["knowledge_gate"]["decision"] == "not_applied"
    assert disabled["knowledge_gate"]["decision"] == "not_applied"
    assert off_embedder.batch_calls == off_embedder.embed_calls == []
    assert disabled_embedder.batch_calls == disabled_embedder.embed_calls == []


def test_rag_telemetry_declares_all_gate_decisions(tmp_path):
    for decision in ("skip", "search", "not_applied", "error"):
        rag_store = RecordingRagStore()
        enricher = MemoryEnricher(
            store=InMemoryStore(),
            core=CoreClient("http://core.invalid"),
            telemetry=TelemetryWriter(tmp_path),
            config=_config(tmp_path),
            rag_store=rag_store,
            knowledge_gate=FixedGate(decision),
        )
        if decision == "not_applied":
            enricher.retrieve_rag(
                request_id=f"task-{decision}", identity=_identity(), prompt="pregunta"
            )
        else:
            enricher.recall_with_rag(
                request_id=f"preview-{decision}",
                identity=_identity(),
                prompt="pregunta",
                use_rag=True,
                include_memory=False,
            )

    decisions = {
        event["knowledge_gate"]["decision"]
        for event in _events(tmp_path)
        if event["event"] == "rag.retrieve"
    }
    assert decisions == {"skip", "search", "not_applied", "error"}


def test_courtesy_signal_has_no_overlap_with_blind_or_mixed_battery():
    root = Path(__file__).parents[1]
    phrases = {
        line.strip()
        for line in (root / "src/ianest_extended/data/courtesy_es.txt").read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    battery = json.loads(
        (root / "tools/lab/paso_cero_bateria.json").read_text(encoding="utf-8")
    )

    assert not phrases.intersection(battery["cortesia_ciega"])
    assert not phrases.intersection(battery["mixtos"])
