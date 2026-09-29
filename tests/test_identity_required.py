"""ADR 0014: las superficies de servidor no inventan interlocutores.

Un default pensado para la CLI -recordar la sesion entre invocaciones- lo
heredaba el camino de peticion de REST y MCP. Publicada la capa en red, eso
hacia que todo llamante anonimo fuera el mismo usuario en el mismo hilo
interminable. Aqui se fija que ya no.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

pytest.importorskip("starlette")
pytest.importorskip("httpx")

import httpx

from ianest_extended import ExtendedComposition, ExtendedConfig, ExtendedService
from ianest_extended import cli
from ianest_extended.rest import create_app

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


def _service(config):
    return ExtendedService(
        ExtendedComposition(config, memory_store=InMemoryStore())
    )


def test_rest_refuses_a_request_without_user_id(tmp_path):
    config = _config(tmp_path)
    app = create_app(config, _service(config))

    response = _request(
        app, "POST", "/memory/recall", json_body={"prompt": "hola"}
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["type"] == "ExtendedRequestError"
    assert error["field"] == "identity.user_id"


def test_rest_refuses_a_request_without_session_id(tmp_path):
    config = _config(tmp_path)
    app = create_app(config, _service(config))

    response = _request(
        app,
        "POST",
        "/memory/recall",
        json_body={"prompt": "hola", "identity": {"user_id": "quien-sea"}},
    )

    assert response.status_code == 400
    error = response.json()["error"]
    assert error["field"] == "identity.session_id"
    # El mensaje dice como salir del paso, no solo que falta algo.
    assert "session.new" in error["message"]


def test_the_server_never_remembers_a_session(tmp_path):
    """Punto 3 del ADR 0014: el fichero de estado es de la CLI, no del servidor."""
    config = _config(tmp_path)
    app = create_app(config, _service(config))

    _request(app, "POST", "/memory/recall", json_body={"prompt": "hola"})

    assert not config.session_state_path.exists()


def test_session_capabilities_need_user_but_not_session(tmp_path):
    """Exigir una sesion para poder CREARLA no tendria salida."""
    config = _config(tmp_path)
    app = create_app(config, _service(config))
    identity = {"user_id": "sin-hilo-todavia"}

    created = _request(
        app, "POST", "/session/new", json_body={"identity": identity}
    )
    listed = _request(
        app, "POST", "/session/list", json_body={"identity": identity}
    )
    anonymous = _request(app, "POST", "/session/list", json_body={})

    assert created.status_code == 200
    assert listed.status_code == 200
    assert anonymous.status_code == 400
    assert anonymous.json()["error"]["field"] == "identity.user_id"


def test_the_cli_keeps_its_defaults(tmp_path, capsys):
    """El punto 7 del ADR 0011 sigue vigente donde se penso: un terminal."""
    config = _config(tmp_path)

    code = cli._memory_recall(
        _service(config),
        config,
        SimpleNamespace(
            prompt="hola",
            use_memory=False,
            use_rag=False,
            user_id=None,
            service=None,
            session_id=None,
            namespace=None,
            domain=None,
            json=True,
        ),
    )

    assert code == 0
    assert capsys.readouterr().out
