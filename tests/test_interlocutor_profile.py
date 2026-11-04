"""CR-0002: el perfil es procedencia y el hecho infantil no se pierde."""

from __future__ import annotations

import json
import pytest

from ianest_extended import (
    CoreResult,
    EngramWrite,
    EnrichmentParameterError,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    ForwardedStream,
    MemoryIdentity,
    Principal,
    SseEvent,
    TaskPlanResult,
)
from ianest_extended.enrichment import MemoryEnricher

from .fakes import InMemoryRagStore, InMemoryStore


CHILD_TEXT = "El interlocutor es un nino o una nina."


class ProfileCore:
    def __init__(self) -> None:
        self.calls = []

    def prompt_run(self, prompt, identity, model=None, domain=None):
        self.calls.append(("prompt.run", prompt, identity))
        response = '{"items":[]}' if model else "respuesta"
        return CoreResult(
            response=response,
            trace={"request_id": f"core-{len(self.calls)}", "finish_reason": "stop"},
            payload={"response": response, "trace": {"request_id": "core"}},
        )

    def reasoning_run(self, prompt, identity, model=None, domain=None):
        self.calls.append(("reasoning.run", prompt, identity))
        return CoreResult(
            response="salida",
            trace={"request_id": "core-reasoning", "finish_reason": "stop"},
            payload={"output": "salida", "trace": {"request_id": "core-reasoning"}},
        )

    def prompt_stream(self, prompt, identity, model=None, domain=None):
        self.calls.append(("prompt.stream", prompt, identity))
        return _stream("prompt", "texto")

    def reasoning_stream(self, prompt, identity, model=None, domain=None):
        self.calls.append(("reasoning.stream", prompt, identity))
        return _stream("reasoning", "salida")

    def task_plan(self, prompt, identity, *, effort=None):
        self.calls.append(("task.plan", prompt, identity))
        payload = {
            "plan": [
                {"index": 0, "prompt": "primera subtarea", "domain": "general"},
                {"index": 1, "prompt": "segunda subtarea", "domain": "general"},
            ],
            "trace": {"request_id": "core-plan"},
        }
        return TaskPlanResult(payload, tuple(payload["plan"]), payload["trace"])

    def task_run(self, prompt, identity, *, plan_payload=None, effort=None):
        self.calls.append(("task.run", prompt, identity, plan_payload))
        return CoreResult(
            response="tarea",
            trace={"request_id": "core-task", "stop_reason": "task_done"},
            payload={"response": "tarea", "trace": {"request_id": "core-task"}},
        )

    def list_domains(self):
        return ("general",)


def _stream(kind, value):
    if kind == "prompt":
        data = {"text": value, "finish_reason": "stop"}
        name = "done"
    else:
        data = {"output": value, "trace": {"request_id": "core-stream"}}
        name = "done"
    encoded = json.dumps({"type": name, "data": data})
    return ForwardedStream(iter((SseEvent(name, encoded, encoded),)), lambda: None)


def _service(tmp_path):
    core = ProfileCore()
    store = InMemoryStore()
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
        rag_enabled=False,
        memory_enabled=False,
        write_back_enabled=False,
    )
    service = ExtendedService(
        ExtendedComposition(
            config,
            core=core,
            memory_store=store,
            rag_store=InMemoryRagStore(),
        )
    )
    return service, core, store


def _identity(profile=None):
    return MemoryIdentity(
        user_id="same-user",
        session_id="same-session",
        service="test",
        interlocutor_profile=profile,
    )


def _events(tmp_path):
    path = next(tmp_path.glob("extended-*.jsonl"))
    return [json.loads(line) for line in path.read_text(encoding="ascii").splitlines()]


@pytest.mark.parametrize("profile,composed", [("child", True), ("adult", False), (None, False)])
@pytest.mark.parametrize("capability", ["prompt.run", "reasoning.run", "prompt.stream", "reasoning.stream"])
def test_profile_is_composed_in_all_inference_paths_even_without_enrichment(
    tmp_path, profile, composed, capability
):
    service, core, _ = _service(tmp_path)
    identity = _identity(profile)
    if capability == "prompt.run":
        service.prompt_run("pregunta literal", identity, enrich=False)
    elif capability == "reasoning.run":
        service.reasoning_run("pregunta literal", identity, enrich=False)
    elif capability == "prompt.stream":
        list(service.prompt_stream("pregunta literal", identity, enrich=False))
    else:
        list(service.reasoning_stream("pregunta literal", identity, enrich=False))

    call = next(item for item in core.calls if item[0] == capability)
    assert (CHILD_TEXT in call[1]) is composed
    assert call[2].interlocutor_profile == profile
    event = next(item for item in _events(tmp_path) if item["event"] == capability)
    assert event["interlocutor_context"] == {"profile": profile, "composed": composed}


@pytest.mark.parametrize("enrich", [False, True])
def test_task_child_reaches_planner_combiner_and_every_subtask(tmp_path, enrich):
    service, core, _ = _service(tmp_path)
    service.task_run(
        "prepara una tarea",
        _identity("child"),
        enrich=enrich,
        use_memory=False,
        use_rag=False,
        write_back=False,
    )

    planner = next(item for item in core.calls if item[0] == "task.plan")
    runner = next(item for item in core.calls if item[0] == "task.run")
    assert CHILD_TEXT in planner[1]
    assert CHILD_TEXT in runner[1]
    assert all(CHILD_TEXT in item["prompt"] for item in runner[3]["plan"])
    event = next(item for item in _events(tmp_path) if item["event"] == "task.run")
    assert event["interlocutor_context"] == {"profile": "child", "composed": True}


@pytest.mark.parametrize("profile", ["adult", None])
def test_task_without_child_keeps_prompts_and_telemetry_uncomposed(tmp_path, profile):
    service, core, _ = _service(tmp_path)
    service.task_run(
        "prepara una tarea",
        _identity(profile),
        enrich=True,
        use_memory=False,
        use_rag=False,
        write_back=False,
    )

    planner = next(item for item in core.calls if item[0] == "task.plan")
    runner = next(item for item in core.calls if item[0] == "task.run")
    assert CHILD_TEXT not in planner[1]
    assert CHILD_TEXT not in runner[1]
    assert all(CHILD_TEXT not in item["prompt"] for item in runner[3]["plan"])
    event = next(item for item in _events(tmp_path) if item["event"] == "task.run")
    assert event["interlocutor_context"] == {"profile": profile, "composed": False}


def test_child_context_is_permanent_and_memory_key_is_unchanged(tmp_path):
    service, core, store = _service(tmp_path)
    config = service.config
    enricher = MemoryEnricher(
        store=store,
        core=core,
        telemetry=service._composition.telemetry(),
        config=config,
        rag_store=InMemoryRagStore(),
    )
    store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="recuerdo compartido",
            identity=_identity("child"),
        ),
    )
    tiny_child = enricher.recall(
        _identity("child"), "literal", include_memory=False, token_budget=1
    )
    child = enricher.recall(_identity("child"), "literal", token_budget=500)
    adult = enricher.recall(_identity("adult"), "literal", token_budget=500)
    assert tiny_child.context == f"## interlocutor\n{CHILD_TEXT}"
    assert child.context.startswith(f"## interlocutor\n{CHILD_TEXT}")
    assert "recuerdo compartido" in child.context
    assert "recuerdo compartido" in adult.context
    assert "## interlocutor" not in adult.context


def test_invalid_profile_stops_before_any_core_or_memory_write(tmp_path):
    service, core, store = _service(tmp_path)
    with pytest.raises(EnrichmentParameterError) as exc_info:
        service.prompt_run("literal", _identity("other"), enrich=False)
    assert exc_info.value.field == "interlocutor_profile"
    assert core.calls == []
    assert store.engrams == []


def test_child_dry_run_composes_and_declares_telemetry(tmp_path):
    service, core, _ = _service(tmp_path)
    result = service.prompt_run(
        "pregunta literal", _identity("child"), enrich=False, dry_run=True
    )
    assert CHILD_TEXT in result.enriched_prompt
    assert core.calls == []
    event = next(item for item in _events(tmp_path) if item["event"] == "prompt.run")
    assert event["status"] == "dry_run"
    assert event["interlocutor_context"] == {"profile": "child", "composed": True}


def test_rest_and_mcp_service_input_reject_invalid_profile_before_work(tmp_path):
    service, core, store = _service(tmp_path)
    payload = {
        "prompt": "literal",
        "identity": {
            "user_id": "same-user",
            "session_id": "same-session",
            "interlocutor_profile": "other",
        },
        "enrich": False,
    }
    with pytest.raises(EnrichmentParameterError):
        service.invoke("prompt.run", payload)
    assert core.calls == []
    assert store.engrams == []


def test_write_back_keeps_the_literal_question_and_profile_is_not_an_engram(tmp_path):
    service, _, store = _service(tmp_path)
    result = service.prompt_run(
        "pregunta literal", _identity("child"), use_memory=False, write_back=True
    )
    assert CHILD_TEXT in result.enriched_prompt
    assert store.engrams
    assert all(CHILD_TEXT not in engram.content for engram in store.engrams)
    assert any(engram.content == "pregunta literal" for engram in store.engrams)
