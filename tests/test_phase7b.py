"""Criterios falsables de la fase 7b, sin depender de red ni PostgreSQL."""

import json
from datetime import UTC, datetime
from uuid import uuid4

from ianest_extended import (
    CoreResult,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    MemoryIdentity,
    RagChunk,
    TaskPlanResult,
)
from ianest_extended.enrichment import estimate_tokens
from ianest_extended.cli import _build_parser

from .fakes import InMemoryRagStore, InMemoryStore


class Phase7bCore:
    def __init__(self):
        self.calls = []
        self.plan_payload = {
            "plan": [
                {
                    "index": 0,
                    "prompt": "administra nftables",
                    "domain": "linux",
                    "depends_on": [],
                    "future_structural_field": {"keep": True},
                },
                {
                    "index": 1,
                    "prompt": "calcula combinaciones",
                    "domain": "codigo",
                    "depends_on": [0],
                },
            ],
            "requirements": [
                {
                    "id": "r1",
                    "statement": "resolver todo",
                    "covered_by": [0, 1],
                }
            ],
            "degradations": [],
            "effort": "high",
            "params": {"effort": "high", "report_only": True},
            "trace": {"request_id": "core-plan", "capability": "task.plan"},
            "future_sibling": {"opaque": [1, 2, 3]},
        }

    def task_plan(self, prompt, identity, *, effort=None):
        self.calls.append(("task.plan", prompt, identity, effort))
        return TaskPlanResult(
            payload=self.plan_payload,
            plan=tuple(self.plan_payload["plan"]),
            trace=self.plan_payload["trace"],
        )

    def task_run(self, prompt, identity, *, plan_payload=None, effort=None):
        self.calls.append(("task.run", prompt, identity, plan_payload, effort))
        return CoreResult(
            response="respuesta combinada",
            trace={"request_id": "core-task", "stop_reason": "task_done"},
            payload={
                "response": "respuesta combinada",
                "stop_reason": "task_done",
                "subtasks": [{"unknown": True}],
                "trace": {
                    "request_id": "core-task",
                    "stop_reason": "task_done",
                },
                "future_response_field": {"intact": True},
            },
        )

    def reasoning_run(self, prompt, identity, model=None, domain=None):
        self.calls.append(("reasoning.run", prompt, identity, model, domain))
        return CoreResult(
            response="salida razonada",
            trace={"request_id": "core-reasoning", "stop_reason": "model_done"},
            payload={
                "output": "salida razonada",
                "steps": [{"iteration": 1, "unknown": "kept"}],
                "trace": {
                    "request_id": "core-reasoning",
                    "stop_reason": "model_done",
                },
                "future_response_field": ["intacto"],
            },
        )

    def prompt_run(self, prompt, identity, model=None, domain=None):
        self.calls.append(("prompt.run", prompt, identity, model, domain))
        return CoreResult(
            response='{"items":[]}',
            trace={"request_id": "core-extract", "finish_reason": "stop"},
            payload={
                "response": '{"items":[]}',
                "trace": {
                    "request_id": "core-extract",
                    "finish_reason": "stop",
                },
            },
        )

    def list_domains(self):
        return ("general", "linux", "codigo")


def _chunk(domain, content, score):
    return RagChunk(
        id=uuid4(),
        corpus_id=uuid4(),
        corpus_name=f"manual-{domain}",
        domains=(domain,),
        content=content,
        source_ref=f"{domain}.md",
        ordinal=0,
        score=score,
        created_at=datetime.now(UTC),
    )


def _service(tmp_path, *, core=None, store=None, rag_store=None, **changes):
    core = core or Phase7bCore()
    store = store or InMemoryStore()
    rag_store = rag_store or InMemoryRagStore()
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
        rag_enabled=False,
        **changes,
    )
    service = ExtendedService(
        ExtendedComposition(
            config,
            core=core,
            memory_store=store,
            rag_store=rag_store,
        )
    )
    return service, core, store, rag_store


def _identity():
    return MemoryIdentity(user_id="u", session_id="s", service="test")


def _task_call(core):
    return next(call for call in core.calls if call[0] == "task.run")


def _events(tmp_path):
    path = next(tmp_path.glob("extended-*.jsonl"))
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


def test_task_plan_is_copied_faithfully_except_params(tmp_path):
    """Criterios 1-3: copia por objeto, params fuera y solo prompt editado."""
    chunks = (
        _chunk("linux", "contexto exclusivo linux", 0.9),
        _chunk("codigo", "contexto exclusivo codigo", 0.9),
    )
    service, core, _, _ = _service(
        tmp_path,
        rag_store=InMemoryRagStore(chunks),
    )

    service.task_run(
        "tarea original",
        _identity(),
        use_memory=False,
        use_rag=True,
        write_back=False,
    )

    sent = _task_call(core)[3]
    assert "params" not in sent
    assert sent["future_sibling"] == core.plan_payload["future_sibling"]
    assert sent["requirements"] == core.plan_payload["requirements"]
    assert sent["effort"] == core.plan_payload["effort"]
    for original, enriched in zip(core.plan_payload["plan"], sent["plan"]):
        assert enriched["index"] == original["index"]
        assert enriched["domain"] == original["domain"]
        assert enriched["depends_on"] == original["depends_on"]
        for key in set(original) - {"prompt"}:
            assert enriched[key] == original[key]


def test_task_rag_is_gated_and_bounded_per_subtask(tmp_path):
    """Criterios 4-5: dominio propio y rag_max_tokens por cada subtarea."""
    chunks = (
        _chunk("linux", "LINUX_ONLY " + "l" * 35, 0.9),
        _chunk("codigo", "CODIGO_ONLY " + "c" * 35, 0.9),
        _chunk("linux", "LOW_LINUX " + "x" * 35, 0.1),
        _chunk("codigo", "LOW_CODIGO " + "y" * 35, 0.1),
    )
    service, core, _, rag = _service(
        tmp_path,
        rag_store=InMemoryRagStore(chunks),
        rag_max_tokens=40,
        rag_top_k=4,
    )

    result = service.task_run(
        "tarea original",
        _identity(),
        use_memory=False,
        use_rag=True,
        write_back=False,
    )

    sent_plan = _task_call(core)[3]["plan"]
    assert rag.domains == ["linux", "codigo"]
    assert "LINUX_ONLY" in sent_plan[0]["prompt"]
    assert "CODIGO_ONLY" not in sent_plan[0]["prompt"]
    assert "CODIGO_ONLY" in sent_plan[1]["prompt"]
    assert "LINUX_ONLY" not in sent_plan[1]["prompt"]
    for original, enriched in zip(core.plan_payload["plan"], sent_plan):
        injected = enriched["prompt"].removesuffix(original["prompt"])
        assert estimate_tokens(injected) <= 40
    assert result.subtasks_enriched == 2


def test_task_passthrough_does_not_plan_or_supply_a_plan(tmp_path):
    """Criterio 7: --no-enrich conserva el camino replanificable del core."""
    service, core, _, _ = _service(tmp_path)

    result = service.task_run("tarea original", _identity(), enrich=False)

    assert [call[0] for call in core.calls] == ["task.run"]
    call = _task_call(core)
    assert call[1] == "tarea original"
    assert call[3] is None
    assert result.enriched is False


def test_task_write_back_uses_only_original_and_combined_turns(tmp_path):
    """Criterio 8: dos dialog, ninguno por subtarea."""
    store = InMemoryStore()
    service, core, _, _ = _service(tmp_path, store=store)

    service.task_run(
        "tarea original",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=True,
    )

    dialogs = [engram for engram in store.engrams if engram.type_name == "dialog"]
    assert [engram.content for engram in dialogs] == [
        "tarea original",
        "respuesta combinada",
    ]
    assert not any(
        item["prompt"] in {engram.content for engram in store.engrams}
        for item in core.plan_payload["plan"]
    )


def test_reasoning_run_keeps_the_core_payload_intact(tmp_path):
    """Criterio 9: solo se interpreta output y trace; lo demas sigue intacto."""
    service, _, _, _ = _service(tmp_path)

    result = service.reasoning_run(
        "razona",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=False,
    )

    assert result.output == "salida razonada"
    assert result.payload["steps"] == [{"iteration": 1, "unknown": "kept"}]
    assert result.payload["future_response_field"] == ["intacto"]


def test_task_telemetry_chains_ids_and_counts_subtasks(tmp_path):
    """Criterio 10: ids encadenados y contador de subtareas enriquecidas."""
    chunks = (
        _chunk("linux", "linux", 0.9),
        _chunk("codigo", "codigo", 0.9),
    )
    service, _, _, _ = _service(
        tmp_path,
        rag_store=InMemoryRagStore(chunks),
    )

    result = service.task_run(
        "tarea",
        _identity(),
        use_memory=False,
        use_rag=True,
        write_back=False,
    )

    event = next(item for item in _events(tmp_path) if item["event"] == "task.run")
    assert event["request_id"] == result.request_id
    assert event["downstream_request_id"] == "core-task"
    assert event["counters"]["subtasks_enriched"] == 2


def test_task_rag_telemetry_declares_domain_and_corpora(tmp_path):
    chunks = (
        _chunk("linux", "linux", 0.9),
        _chunk("codigo", "codigo", 0.9),
    )
    service, _, _, _ = _service(tmp_path, rag_store=InMemoryRagStore(chunks))

    service.task_run(
        "tarea",
        _identity(),
        use_memory=False,
        use_rag=True,
        write_back=False,
    )

    events = [
        item for item in _events(tmp_path) if item["event"] == "rag.retrieve"
    ]
    assert [event["domain"] for event in events] == ["linux", "codigo"]
    assert [event["corpora"] for event in events] == [
        ["manual-linux"],
        ["manual-codigo"],
    ]


def test_task_domain_is_only_a_memory_facet(tmp_path):
    """La bandera CLI no fuerza dominio de tarea ni invoca domain.route."""
    service, core, _, _ = _service(tmp_path)

    service.task_run(
        "tarea",
        _identity(),
        use_memory=False,
        use_rag=False,
        write_back=False,
        domain="linux",
    )

    plan_call = next(call for call in core.calls if call[0] == "task.plan")
    run_call = _task_call(core)
    assert plan_call[2].domain_tag is None
    assert run_call[2].domain_tag is None


def test_interim_cli_keeps_neighboring_capabilities_reachable():
    """Crear los grupos nuevos no bloquea task.plan ni los streams crudos."""
    parser = _build_parser()

    task_plan = parser.parse_args(["task", "plan", "--prompt", "tarea"])
    task_stream = parser.parse_args(["task", "stream", "--prompt", "tarea"])
    reasoning_stream = parser.parse_args(
        ["reasoning", "stream", "--prompt", "razona"]
    )

    assert task_plan.capability.name == "task.plan"
    assert task_stream.capability.name == "task.stream"
    assert reasoning_stream.capability.name == "reasoning.stream"
