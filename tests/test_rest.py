"""Criterios falsables de la Fase 7c-1: piel REST."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

import httpx

from ianest_extended import (
    CoreResult,
    DownstreamError,
    EngramWrite,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    ForwardedJson,
    ForwardedStream,
    MemoryIdentity,
    Principal,
    SseEvent,
)
from ianest_extended import cli
from ianest_extended.rest import _stream_events, create_app

from .fakes import InMemoryStore


def _request(app, method, path, *, json_body=None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json_body)

    return asyncio.run(run())


def _config(tmp_path, **changes):
    return ExtendedConfig(
        core_url="http://127.0.0.1:1",
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        catalog_cache_path=tmp_path / "catalog.json",
        embedding_dimension=2,
        rag_enabled=False,
        write_back_enabled=False,
        **changes,
    )


def test_rest_and_cli_return_the_same_own_capability(tmp_path, capsys):
    """Criterio 1: paridad REST/CLI sobre memory_type.list."""
    config = _config(tmp_path)
    service = ExtendedService(
        ExtendedComposition(config, memory_store=InMemoryStore())
    )

    cli._memory_type_list(service, config, SimpleNamespace(json=True))
    cli_payload = json.loads(capsys.readouterr().out)
    rest_payload = _request(
        create_app(config, service), "GET", "/memory_type/list"
    ).json()

    assert rest_payload == cli_payload == {"types": []}


class _CoreSpy:
    def __init__(self):
        self.calls = []

    def prompt_run(self, prompt, identity, model=None, domain=None):
        self.calls.append(("prompt_run", prompt))
        return CoreResult(
            response=f"echo:{prompt}",
            payload={
                "response": f"echo:{prompt}",
                "trace": {"request_id": "core-1", "finish_reason": "stop"},
            },
            trace={"request_id": "core-1", "finish_reason": "stop"},
        )

    def list_domains(self):
        self.calls.append(("list_domains", None))
        return ("general", "linux")


class _StatusStore:
    def verify_schema(self):
        return None

    def confirmed_corpus_counts(self, domains):
        return {domain: 0 for domain in domains}


def test_own_routes_only_use_core_for_their_declared_work(tmp_path):
    """Criterio 2: recall no llama al core; status solo lista dominios."""
    config = _config(tmp_path)
    core = _CoreSpy()
    store = InMemoryStore()
    service = ExtendedService(
        ExtendedComposition(
            config,
            core=core,
            memory_store=store,
            rag_store=_StatusStore(),
        )
    )
    app = create_app(config, service)

    recall = _request(
        app,
        "POST",
        "/memory/recall",
        json_body={"prompt": "hola", "use_memory": False, "use_rag": False},
    )
    status = _request(app, "GET", "/knowledge/status")

    assert recall.status_code == 200
    assert status.status_code == 200
    assert core.calls == [("list_domains", None)]


def test_overridden_prompt_is_enriched_while_direct_core_prompt_is_not(tmp_path):
    """Criterio 3: prompt.run REST usa el vertical enriquecido del servicio."""
    config = _config(tmp_path, memory_enabled=True)
    core = _CoreSpy()
    store = InMemoryStore()
    identity = MemoryIdentity(
        user_id="rest-user",
        session_id="rest-session",
        service="test",
        namespace="preferences",
    )
    store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="contexto recordado",
            identity=identity,
        ),
    )
    service = ExtendedService(
        ExtendedComposition(config, core=core, memory_store=store)
    )

    response = _request(
        create_app(config, service),
        "POST",
        "/prompt/run",
        json_body={
            "prompt": "pregunta",
            "identity": identity.to_core_dict(),
            "use_memory": True,
            "use_rag": False,
            "write_back": False,
        },
    )
    core.prompt_run("pregunta", identity)

    assert response.status_code == 200
    assert "contexto recordado" in core.calls[0][1]
    assert core.calls[1] == ("prompt_run", "pregunta")


class _RouteProxy:
    def __init__(self):
        self.calls = []
        self.catalog_calls = 0

    def invoke(self, capability, payload):
        if capability == "prompt.run":
            raise ValueError("no usado")
        raise AssertionError(capability)

    def capability_list(self):
        self.catalog_calls += 1
        raise AssertionError("el reenvio por ruta no consulta el catalogo")

    def forward(self, capability, payload, *, method=None):
        self.calls.append((capability, payload, method))
        return ForwardedJson(
            {
                "unknown": {"nested": [1, 2, 3]},
                "payload": payload,
            },
            status_code=201,
        )


def test_unknown_route_is_forwarded_without_catalog_and_stays_opaque(tmp_path):
    """Criterios 4 y 5: ruta desconocida sin catalogo y respuesta opaca."""
    proxy = _RouteProxy()
    response = _request(
        create_app(_config(tmp_path), proxy),
        "POST",
        "/future/inspect",
        json_body={"new_input": True},
    )

    assert response.status_code == 201
    assert response.json() == {
        "unknown": {"nested": [1, 2, 3]},
        "payload": {"new_input": True},
    }
    assert proxy.calls == [
        ("/future/inspect", {"new_input": True}, "POST")
    ]
    assert proxy.catalog_calls == 0


class _StreamingProxy(_RouteProxy):
    def __init__(self):
        super().__init__()
        self.closed = False

    def forward(self, capability, payload, *, method=None):
        self.calls.append((capability, payload, method))
        events = iter(
            (
                SseEvent("token", "uno", "event: token\ndata: uno"),
                SseEvent("done", "fin", "event: done\ndata: fin"),
            )
        )
        return ForwardedStream(events, self._close)

    def _close(self):
        self.closed = True


def test_streaming_route_retransmits_sse_events_without_json_conversion(tmp_path):
    """Criterio 6: retransmision SSE evento a evento."""
    proxy = _StreamingProxy()
    stream = proxy.forward(
        "/prompt/stream",
        {"prompt": "hola"},
        method="POST",
    )

    events = iter(_stream_events(stream))
    assert next(events) == b"event: token\ndata: uno\n\n"
    assert next(events) == b"event: done\ndata: fin\n\n"
    with pytest.raises(StopIteration):
        next(events)
    assert proxy.closed is True


class _ErrorProxy(_RouteProxy):
    def forward(self, capability, payload, *, method=None):
        raise DownstreamError(
            {
                "type": "CoreSpecificError",
                "message": "fallo abajo",
                "field": "model",
                "origin": "ia_nest_core",
                "request_id": "core-error-7",
            },
            status_code=422,
        )


def test_downstream_error_keeps_type_origin_and_status(tmp_path):
    """Criterio 7: error ajeno intacto, incluido el codigo HTTP."""
    response = _request(
        create_app(_config(tmp_path), _ErrorProxy()),
        "POST",
        "/future/fail",
        json_body={},
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "type": "CoreSpecificError",
        "message": "fallo abajo",
        "field": "model",
        "origin": "ia_nest_core",
        "request_id": "core-error-7",
    }


def test_own_error_has_extended_origin_and_type(tmp_path):
    """Criterio 8: error propio con taxonomia y origin de extended."""
    service = ExtendedService(ExtendedComposition(_config(tmp_path)))
    response = _request(
        create_app(_config(tmp_path), service),
        "POST",
        "/prompt/run",
        json_body={"prompt": "hola", "enrich": False, "use_rag": True},
    )

    assert response.status_code == 400
    assert response.json()["error"]["type"] == "EnrichmentParameterError"
    assert response.json()["error"]["origin"] == "ia_nest_extended"


class _CatalogCore:
    def list_capabilities(self):
        return {
            "core_version": "0.4.0",
            "capabilities": [
                {
                    "name": "future.inspect",
                    "summary": "futura",
                    "identity": False,
                    "streaming": False,
                    "params": [],
                    "rest": {"path": "/future/inspect", "method": "GET"},
                    "cli": None,
                    "mcp": None,
                }
            ],
        }


def test_capability_list_matches_cli_and_contains_fused_provenance(
    tmp_path, capsys
):
    """Criterio 9: catalogo fusionado igual por REST y CLI."""
    config = _config(tmp_path)
    service = ExtendedService(ExtendedComposition(config, core=_CatalogCore()))

    cli._capability_list(service, config, SimpleNamespace(json=True))
    cli_payload = json.loads(capsys.readouterr().out)
    rest_payload = _request(
        create_app(config, service), "GET", "/capability/list"
    ).json()

    assert rest_payload == cli_payload
    assert {item["provenance"] for item in rest_payload["capabilities"]} == {
        "own",
        "overridden",
        "forwarded",
    }


def test_rest_defaults_to_loopback_and_handlers_only_call_service(tmp_path):
    """Criterios 10 y 11: loopback y piel sin reglas de dominio."""
    config = ExtendedConfig()
    proxy = _RouteProxy()
    assert config.rest_host == "127.0.0.1"
    response = _request(
        create_app(_config(tmp_path), proxy),
        "POST",
        "/future/inspect",
        json_body={"a": 1},
    )
    assert response.status_code == 201
    assert proxy.calls == [("/future/inspect", {"a": 1}, "POST")]
