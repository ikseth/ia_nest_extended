"""Criterios 4-7 y 13: sobreescritura, passthrough, contradiccion, RAG y traza."""

import json

import pytest

from ianest_extended import (
    EnrichmentParameterError,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    MemoryIdentity,
    RagUnavailableError,
)

from .fakes import InMemoryRagStore, InMemoryStore

CLOSED_DSN = "postgresql://ianest:local@127.0.0.1:1/ianest_extended"


def _config(tmp_path, local_service_stub, **changes):
    return ExtendedConfig(
        core_url=local_service_stub.base_url,
        database_dsn=CLOSED_DSN,
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
        connect_timeout_seconds=5,
        inactivity_timeout_seconds=5,
        **changes,
    )


def _service(tmp_path, local_service_stub, *, store=None, rag_store=None, **changes):
    composition = ExtendedComposition(
        _config(tmp_path, local_service_stub, **changes),
        memory_store=store,
        rag_store=rag_store,
    )
    return ExtendedService(composition)


def _events(tmp_path):
    path = next(tmp_path.glob("extended-*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


def _identity():
    return MemoryIdentity(user_id="u", session_id="A", service="local_cli")


def test_overridden_prompt_run_keeps_core_shape(tmp_path, local_service_stub):
    """Criterio 4: misma FORMA que el core, con response y trace intactos."""
    store = InMemoryStore()
    service = _service(
        tmp_path,
        local_service_stub,
        store=store,
        rag_store=InMemoryRagStore(),
    )

    result = service.prompt_run("remember-blue", _identity())

    core_payloads = [
        payload
        for path, payload in local_service_stub.requests
        if path == "/prompt/run" and "model" not in payload
    ]
    assert set(result.payload) == {
        "response",
        "model",
        "domain",
        "params",
        "trace",
    }
    assert result.payload["response"] == f"echo:{core_payloads[0]['prompt']}"
    assert result.payload["trace"]["finish_reason"] == "stop"
    assert result.payload["trace"]["request_id"].startswith("core-")


def test_passthrough_does_not_recall_inject_or_write(
    tmp_path,
    local_service_stub,
):
    """Criterio 5: enrich desactivado no recupera, no inyecta y no persiste."""
    store = InMemoryStore()
    service = _service(tmp_path, local_service_stub, store=store)

    result = service.prompt_run("remember-blue", _identity(), enrich=False)

    core_requests = [
        payload
        for path, payload in local_service_stub.requests
        if path == "/prompt/run"
    ]
    assert len(core_requests) == 1
    assert core_requests[0]["prompt"] == "remember-blue"
    assert "<enrichment_context>" not in core_requests[0]["prompt"]
    assert store.engrams == []
    assert result.context == ""
    events = _events(tmp_path)
    assert [event["event"] for event in events] == ["prompt.run"]
    assert events[0]["counters"] == {
        "enrich": 0,
        "use_memory": 0,
        "use_rag": 0,
        "write_back": 0,
    }
    assert events[0]["status"] == "ok"


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"enrich": False, "use_rag": True}, "use_rag"),
        ({"enrich": False, "use_memory": True}, "use_memory"),
        ({"enrich": False, "write_back": True}, "write_back"),
        ({"domain": "linux", "auto_domain": True}, "auto_domain"),
    ],
)
def test_contradictory_combination_is_a_typed_error(
    tmp_path,
    local_service_stub,
    kwargs,
    field,
):
    """Criterio 6: contradiccion tipada, no precedencia silenciosa."""
    service = _service(tmp_path, local_service_stub, store=InMemoryStore())

    with pytest.raises(EnrichmentParameterError) as exc_info:
        service.prompt_run("hola", _identity(), **kwargs)

    assert exc_info.value.field == field
    assert not [
        path for path, _ in local_service_stub.requests if path == "/prompt/run"
    ]


def test_requested_rag_without_substrate_fails_typed(
    tmp_path,
    local_service_stub,
):
    """Criterio 7: RAG pedido sin sustrato es error tipado, no silencio."""
    service = _service(tmp_path, local_service_stub, store=InMemoryStore())

    with pytest.raises(RagUnavailableError) as exc_info:
        service.prompt_run("hola", _identity(), use_rag=True)

    assert exc_info.value.field == "use_rag"
    assert exc_info.value.origin == "ia_nest_extended"
    assert not [
        path for path, _ in local_service_stub.requests if path == "/prompt/run"
    ]


def test_rag_policy_flag_does_not_decide_wiring(tmp_path, local_service_stub):
    """La politica da el default; el cableado lo hace el root."""
    rag_store = InMemoryRagStore()
    service = _service(
        tmp_path,
        local_service_stub,
        store=InMemoryStore(),
        rag_store=rag_store,
        rag_enabled=False,
    )

    service.prompt_run("hola", _identity())
    assert rag_store.domains == []

    service.prompt_run("hola", _identity(), use_rag=True)
    assert rag_store.domains == [None]


def test_telemetry_chains_the_downstream_request_id(
    tmp_path,
    local_service_stub,
):
    """Criterio 13: request_id propio mas downstream_request_id del core."""
    service = _service(
        tmp_path,
        local_service_stub,
        store=InMemoryStore(),
        rag_store=InMemoryRagStore(),
    )

    result = service.prompt_run("smalltalk", _identity())

    events = [
        event for event in _events(tmp_path) if event["event"] == "prompt.run"
    ]
    assert len(events) == 1
    assert events[0]["request_id"] == result.request_id
    assert events[0]["downstream_request_id"] == result.downstream_request_id
    assert events[0]["downstream_request_id"].startswith("core-")
    assert "core_request_id" not in events[0]


def test_dry_run_composes_without_calling_the_core(tmp_path, local_service_stub):
    store = InMemoryStore()
    service = _service(
        tmp_path,
        local_service_stub,
        store=store,
        rag_store=InMemoryRagStore(),
    )

    result = service.prompt_run("hola", _identity(), dry_run=True)

    assert result.dry_run is True
    assert result.enriched_prompt.endswith("hola")
    assert store.engrams == []
    assert not [
        path for path, _ in local_service_stub.requests if path == "/prompt/run"
    ]
