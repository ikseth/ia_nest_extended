"""Criterios falsables de la Fase 7c-2: piel MCP."""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from types import ModuleType, SimpleNamespace
from typing import Any, get_args

import httpx
import pytest

from ianest_extended import (
    CoreConnectionError,
    DownstreamError,
    EnrichmentParameterError,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    ForwardedJson,
    LOCAL_CAPABILITIES,
)
from ianest_extended import cli
from ianest_extended.catalog_cache import write_catalog_cache
from ianest_extended.mcp_server import McpToolError, create_server
from ianest_extended.rest import create_app

from .fakes import InMemoryStore


class _FakeFastMCP:
    def __init__(self, name, **kwargs):
        self.name = name
        self.instructions = kwargs.get("instructions")
        self.host = kwargs.get("host")
        self.port = kwargs.get("port")
        self.tools = {}

    def add_tool(self, fn, *, name, description, structured_output):
        self.tools[name] = SimpleNamespace(
            fn=fn,
            description=description,
            structured_output=structured_output,
        )


@pytest.fixture(autouse=True)
def fake_mcp_sdk(monkeypatch):
    mcp = ModuleType("mcp")
    server = ModuleType("mcp.server")
    fastmcp = ModuleType("mcp.server.fastmcp")
    fastmcp.FastMCP = _FakeFastMCP
    monkeypatch.setitem(sys.modules, "mcp", mcp)
    monkeypatch.setitem(sys.modules, "mcp.server", server)
    monkeypatch.setitem(sys.modules, "mcp.server.fastmcp", fastmcp)


def _config(tmp_path):
    return ExtendedConfig(
        core_url="http://127.0.0.1:1",
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        catalog_cache_path=tmp_path / "catalog.json",
        embedding_dimension=2,
        rag_enabled=False,
        write_back_enabled=False,
    )


def _request(app, method, path, *, json_body=None):
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, json=json_body)

    return asyncio.run(run())


def test_mcp_rest_and_cli_have_parity_for_own_capability(
    tmp_path, capsys
):
    """Criterio 1: las tres pieles devuelven el mismo resultado."""
    config = _config(tmp_path)
    service = ExtendedService(
        ExtendedComposition(config, memory_store=InMemoryStore())
    )
    server = create_server(config, service)

    cli._memory_type_list(service, config, SimpleNamespace(json=True))
    cli_payload = json.loads(capsys.readouterr().out)
    rest_payload = _request(
        create_app(config, service), "GET", "/memory_type/list"
    ).json()
    mcp_payload = server.tools["memory_type.list"].fn()

    assert mcp_payload == rest_payload == cli_payload == {"types": []}


def test_mcp_rest_and_cli_have_parity_with_declared_parameters(
    tmp_path, capsys
):
    """Criterio 1: paridad de memory.recall con los mismos parametros."""
    config = _config(tmp_path)
    service = ExtendedService(
        ExtendedComposition(config, memory_store=InMemoryStore())
    )
    server = create_server(config, service)
    arguments = {
        "prompt": "hola",
        "use_memory": False,
        "use_rag": False,
    }

    cli._memory_recall(
        service,
        config,
        SimpleNamespace(
            **arguments,
            user_id=None,
            service=None,
            session_id=None,
            namespace=None,
            domain=None,
            json=True,
        ),
    )
    cli_payload = json.loads(capsys.readouterr().out)
    rest_payload = _request(
        create_app(config, service),
        "POST",
        "/memory/recall",
        json_body=arguments,
    ).json()
    mcp_payload = server.tools["memory.recall"].fn(**arguments)

    assert mcp_payload == rest_payload == cli_payload


class _OfflineCore:
    def __init__(self):
        self.calls = 0

    def list_capabilities(self):
        self.calls += 1
        raise AssertionError("construir MCP intento consultar el core")


def test_server_starts_offline_with_own_tools_and_declares_gap(tmp_path):
    """Criterios 2, 3, 5 y 6: nombres canonicos, propias y hueco local."""
    config = _config(tmp_path)
    core = _OfflineCore()
    service = ExtendedService(ExtendedComposition(config, core=core))

    server = create_server(config, service)

    assert core.calls == 0
    assert "memory.recall" in server.tools
    assert "prompt.run" in server.tools
    assert set(server.tools) == {item.name for item in LOCAL_CAPABILITIES}
    assert "Catalogo ajeno no cacheado" in server.instructions
    assert "streaming por MCP esta fuera de alcance" in server.instructions


def test_offline_capability_list_reports_the_missing_downstream_catalog(
    tmp_path,
):
    """Criterio 5: el hueco ajeno aparece tambien como error tipado."""
    config = _config(tmp_path)

    class UnreachableCore:
        def list_capabilities(self):
            raise CoreConnectionError("core inalcanzable", "core_url")

    service = ExtendedService(
        ExtendedComposition(config, core=UnreachableCore())
    )
    server = create_server(config, service)

    result = server.tools["capability.list"].fn()

    assert result["core_version"] is None
    assert result["error"]["type"] == "CoreConnectionError"
    assert result["error"]["origin"] == "ia_nest_extended"
    assert "memory.recall" in {
        capability["name"] for capability in result["capabilities"]
    }


class _ForwardProxy:
    def __init__(self):
        self.calls = []

    def forward(self, capability, payload, *, method=None):
        self.calls.append((capability, payload, method))
        return ForwardedJson(
            {"unknown": {"nested": [1, 2, 3]}, "echo": payload}
        )


def _cached_capabilities():
    return [
        {
            "name": "future.inspect",
            "summary": "inspeccion futura",
            "identity": False,
            "streaming": False,
            "params": [
                {
                    "name": "count",
                    "type": "integer",
                    "required": True,
                    "choices": None,
                    "default": None,
                    "summary": "numero",
                    "metavar": "N",
                },
                {
                    "name": "mode",
                    "type": "string",
                    "required": False,
                    "choices": ["fast", "safe"],
                    "default": "safe",
                    "summary": "modo",
                    "metavar": "MODO",
                },
            ],
            "rest": {"path": "/future/inspect", "method": "POST"},
            "cli": None,
            "mcp": {"tool": "alias.prohibido"},
        },
        {
            "name": "prompt.stream",
            "summary": "flujo",
            "identity": True,
            "streaming": True,
            "params": [],
            "rest": {"path": "/prompt/stream", "method": "POST"},
            "cli": None,
            "mcp": None,
        },
        {
            "name": "reasoning.stream",
            "summary": "flujo de razonamiento",
            "identity": True,
            "streaming": True,
            "params": [],
            "rest": {"path": "/reasoning/stream", "method": "POST"},
            "cli": None,
            "mcp": None,
        },
        {
            "name": "task.stream",
            "summary": "flujo de tarea",
            "identity": True,
            "streaming": True,
            "params": [],
            "rest": {"path": "/task/stream", "method": "POST"},
            "cli": None,
            "mcp": None,
        },
    ]


def test_cached_forwarded_tool_uses_catalog_schema_and_generic_forward(
    tmp_path,
):
    """Criterios 2, 4 y 7: cache, parametros, nombre y reenvio opaco."""
    config = _config(tmp_path)
    write_catalog_cache(
        config.catalog_cache_path,
        core_url=config.core_url,
        core_version="0.4.0",
        capabilities=_cached_capabilities(),
    )
    proxy = _ForwardProxy()

    server = create_server(config, proxy)
    handler = server.tools["future.inspect"].fn
    signature = inspect.signature(handler)
    result = handler(count=3)

    assert "alias.prohibido" not in server.tools
    assert signature.parameters["count"].default is inspect.Parameter.empty
    assert signature.parameters["count"].annotation is int
    choice_annotation, none_annotation = get_args(
        signature.parameters["mode"].annotation
    )
    assert none_annotation is type(None)
    assert set(get_args(choice_annotation)) == {
        "fast",
        "safe",
    }
    assert signature.parameters["mode"].default == "safe"
    assert proxy.calls == [
        ("future.inspect", {"count": 3, "mode": "safe"}, "POST")
    ]
    assert result == {
        "unknown": {"nested": [1, 2, 3]},
        "echo": {"count": 3, "mode": "safe"},
    }


class _ErrorProxy:
    def forward(self, capability, payload, *, method=None):
        raise DownstreamError(
            {
                "type": "CoreSpecificError",
                "message": "fallo abajo",
                "field": "model",
                "origin": "ia_nest_core",
                "request_id": "core-error-7",
            }
        )


def test_mcp_errors_keep_type_and_origin(tmp_path):
    """Criterio 8: error ajeno intacto y error propio con origin extended."""
    config = _config(tmp_path)
    write_catalog_cache(
        config.catalog_cache_path,
        core_url=config.core_url,
        core_version="0.4.0",
        capabilities=_cached_capabilities(),
    )
    downstream = create_server(config, _ErrorProxy())

    with pytest.raises(McpToolError) as caught:
        downstream.tools["future.inspect"].fn(count=1)
    assert caught.value.payload["error"]["type"] == "CoreSpecificError"
    assert caught.value.payload["error"]["origin"] == "ia_nest_core"

    class OwnErrorProxy:
        def invoke(self, capability, payload):
            raise EnrichmentParameterError("contradiccion", "enrich")

    own = create_server(config, OwnErrorProxy())
    with pytest.raises(McpToolError) as caught:
        own.tools["prompt.run"].fn(prompt="hola")
    assert caught.value.payload["error"]["type"] == "EnrichmentParameterError"
    assert caught.value.payload["error"]["origin"] == "ia_nest_extended"


def test_streaming_gaps_are_declared_and_not_exposed(tmp_path):
    """Criterio 9: el flujo queda fuera y el hueco no se silencia."""
    config = _config(tmp_path)
    write_catalog_cache(
        config.catalog_cache_path,
        core_url=config.core_url,
        core_version="0.4.0",
        capabilities=_cached_capabilities(),
    )

    server = create_server(config, _ForwardProxy())

    assert {"prompt.stream", "reasoning.stream", "task.stream"}.isdisjoint(
        server.tools
    )
    assert (
        "No expuestas por MCP: prompt.stream, reasoning.stream, task.stream."
        in server.instructions
    )


def test_handlers_only_dispatch_to_the_shared_service(tmp_path):
    """Criterio 10: el handler local solo usa invoke; el ajeno, forward."""
    config = _config(tmp_path)
    write_catalog_cache(
        config.catalog_cache_path,
        core_url=config.core_url,
        core_version="0.4.0",
        capabilities=_cached_capabilities(),
    )

    class ServiceSpy(_ForwardProxy):
        def __init__(self):
            super().__init__()
            self.invocations = []

        def invoke(self, capability, payload):
            self.invocations.append((capability, payload))
            return {"ok": True}

    service = ServiceSpy()
    server = create_server(config, service)
    assert server.tools["memory_type.list"].fn() == {"ok": True}
    server.tools["future.inspect"].fn(count=1)

    assert service.invocations == [("memory_type.list", {})]
    assert service.calls == [
        ("future.inspect", {"count": 1, "mode": "safe"}, "POST")
    ]
