"""El CLI invoca capacidades que no declara (ADR 0011, punto 11).

Ninguna piel puede exigir conocer una capacidad para poder invocarla: un
`GRUPO ACCION` desconocido se resuelve como capacidad reenviada.
"""

import json
import threading

import pytest

from ianest_extended import cli
from ianest_extended.capabilities import (
    LOCAL_CAPABILITIES,
    OWN_CAPABILITIES,
)

UNREACHABLE = "http://127.0.0.1:1"
CLOSED_DSN = "postgresql://ianest:local@127.0.0.1:1/ianest_extended"


def _cli_env(monkeypatch, tmp_path, local_service_stub):
    monkeypatch.setenv("IANEST_EXTENDED_CORE_URL", local_service_stub.base_url)
    monkeypatch.setenv("IANEST_EXTENDED_OLLAMA_URL", UNREACHABLE)
    monkeypatch.setenv("IANEST_EXTENDED_DATABASE_DSN", CLOSED_DSN)
    monkeypatch.setenv("IANEST_EXTENDED_TELEMETRY_DIR", str(tmp_path))
    monkeypatch.setenv(
        "IANEST_EXTENDED_SESSION_STATE_PATH",
        str(tmp_path / "session_id"),
    )
    monkeypatch.setenv(
        "IANEST_EXTENDED_CATALOG_CACHE_PATH",
        str(tmp_path / "catalog_cache.json"),
    )
    monkeypatch.setenv("IANEST_EXTENDED_EMBEDDING_DIMENSION", "2")
    return ["--env-file", str(tmp_path / "ausente.env")]


def test_unknown_capability_is_invocable_without_editing_the_layer(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """Criterio 1: `capability nueva` llega al core y devuelve 0."""
    declaradas = {item.name for item in LOCAL_CAPABILITIES}
    assert "capability.nueva" not in declaradas
    assert "capability.nueva" not in set(OWN_CAPABILITIES)
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "capability", "nueva", "--param", "x=1"])

    captured = capsys.readouterr()
    assert code == 0
    path, payload = local_service_stub.requests[-1]
    assert path == "/capability/nueva"
    assert payload["x"] == 1
    assert payload["identity"]["service"] == "local_cli"
    assert json.loads(captured.out)["eco"]["x"] == 1


def test_unknown_capability_without_body_is_a_get(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """Misma regla de verbo que el reenvio declarado: sin cuerpo, GET."""
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "estado", "nuevo", "--json"])

    captured = capsys.readouterr()
    assert code == 0
    assert local_service_stub.requests[-1] == ("/estado/nuevo", None)
    assert json.loads(captured.out) == {
        "estado": "nuevo",
        "campo_desconocido": True,
    }


def test_unknown_capability_streams_event_by_event(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """Criterio 2: una capacidad desconocida con SSE se retransmite."""
    gate = threading.Event()
    gate.set()
    local_service_stub.stream_gate = gate
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "flujo", "nuevo", "--prompt", "hola"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.splitlines() == [
        '{"chunk": "uno"}',
        '{"chunk": "dos"}',
        '{"stop_reason": "stop"}',
    ]
    path, payload = local_service_stub.requests[-1]
    assert path == "/flujo/nuevo"
    assert payload["prompt"] == "hola"


def test_unknown_capability_error_keeps_format_type_and_origin(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """Criterio 3: el error del core sale como siempre, con type y origin."""
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "capability", "rota", "--param", "y=2"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.strip() == (
        "AdapterError (modelo): el adaptador no respondio"
    )

    code_json = cli.main([*argv, "capability", "rota", "--param", "y=2", "--json"])

    captured_json = capsys.readouterr()
    assert code_json == 1
    assert json.loads(captured_json.err) == {
        "error": {
            "type": "AdapterError",
            "message": "el adaptador no respondio",
            "field": "modelo",
            "origin": "ia_nest_core",
            "request_id": "core-error-2",
        }
    }


def test_unknown_group_without_action_is_a_typed_error(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """Falta la accion: error tipado, sin inventar ni adivinar la ruta."""
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "estado"])

    captured = capsys.readouterr()
    assert code == 1
    assert captured.err.startswith("ExtendedError (capability): ")
    assert "GRUPO ACCION" in captured.err
    assert not [
        path for path, _ in local_service_stub.requests if "estado" in path
    ]


def test_unknown_action_in_known_group_is_resolved_dynamically(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """ADR 0011.11: decide GRUPO ACCION, no solo si el grupo es conocido."""
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "memory", "nuevo", "--json"])

    captured = capsys.readouterr()
    assert code == 0
    assert local_service_stub.requests[-1] == ("/memory/nuevo", None)
    assert json.loads(captured.out) == {"memory": "nuevo", "forwarded": True}


def test_top_level_help_declares_the_dynamic_invocation(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "GRUPO ACCION" in captured.out
    assert "aunque no aparezca en esta lista" in captured.out


def test_global_env_file_works_before_and_after_the_capability(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    argv_after = ["capability", "nueva", "--param", "x=1", "--env-file"]
    _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv_after, str(tmp_path / "ausente.env")])

    capsys.readouterr()
    assert code == 0
    assert local_service_stub.requests[-1][0] == "/capability/nueva"
