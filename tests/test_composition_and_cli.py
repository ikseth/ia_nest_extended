"""Criterios 8-11: pereza, aislamiento de la piel, migracion y codigos de salida."""

import ast
import json
from pathlib import Path

import pytest

from ianest_extended import (
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    SchemaMigrationRequiredError,
    cli,
    remembered_session_id,
)

from .fakes import InMemoryRagStore, InMemoryStore, UnmigratedStore

UNREACHABLE = "http://127.0.0.1:1"
CLOSED_DSN = "postgresql://ianest:local@127.0.0.1:1/ianest_extended"


def _config(tmp_path, **changes):
    return ExtendedConfig(
        core_url=UNREACHABLE,
        ollama_url=UNREACHABLE,
        database_dsn=CLOSED_DSN,
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "state" / "session_id",
        embedding_dimension=2,
        **changes,
    )


def test_maintain_runs_with_core_and_ollama_unreachable(tmp_path):
    """Criterio 8: construccion perezosa."""
    store = InMemoryStore()
    composition = ExtendedComposition(_config(tmp_path), memory_store=store)
    service = ExtendedService(composition)

    result = service.memory_maintain(dry_run=False)

    assert result == {
        "dialog_archived": 0,
        "episodic_promoted": 0,
        "candidates_seen": 0,
        "dry_run": False,
    }
    assert composition.core_constructed is False
    assert store.verified == 1


def test_cli_does_not_import_adapters_or_clients():
    """Criterio 9: aislamiento de la piel."""
    source = Path(cli.__file__).read_text(encoding="utf-8")
    imported: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported.extend(f"{node.module or ''}.{a.name}" for a in node.names)

    assert not [name for name in imported if "adapters" in name]
    assert not [name for name in imported if "clients" in name]


def test_read_only_capability_fails_on_unmigrated_schema(tmp_path):
    """Criterio 10: verifica el esquema y no lo muta."""
    store = UnmigratedStore()
    service = ExtendedService(
        ExtendedComposition(_config(tmp_path), memory_store=store)
    )

    with pytest.raises(SchemaMigrationRequiredError) as exc_info:
        service.memory_type_list()

    assert "runtime migrate" in exc_info.value.message
    assert store.migrated is False


def test_runtime_migrate_is_the_only_path_that_mutates(tmp_path):
    memory_store = UnmigratedStore()
    rag_store = InMemoryRagStore()
    service = ExtendedService(
        ExtendedComposition(
            _config(tmp_path),
            memory_store=memory_store,
            rag_store=rag_store,
        )
    )

    assert service.runtime_migrate() == {
        "memory_schema": "migrated",
        "rag_schema": "migrated",
    }
    assert memory_store.migrated is True
    assert rag_store.migrated is True


def test_session_id_is_generated_once_and_remembered(tmp_path):
    path = tmp_path / "state" / "session_id"

    first = remembered_session_id(path)
    second = remembered_session_id(path)

    assert first == second
    assert path.read_text(encoding="ascii").strip() == first


# --- codigos de salida (criterio 11) --------------------------------------


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


def test_exit_code_zero_on_forwarded_capability(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "runtime", "health", "--json"])

    captured = capsys.readouterr()
    assert code == 0
    assert json.loads(captured.out) == {
        "status": "ok",
        "campo_desconocido": {"anidado": [1, 2, 3]},
    }


def test_exit_code_one_on_typed_error(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main(
        [*argv, "prompt", "run", "--prompt", "hola", "--no-enrich", "--use-rag"]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err.startswith("EnrichmentParameterError (use_rag): ")


def test_exit_code_one_with_json_error_payload(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "eval", "run", "--param", "suite=humo", "--json"])

    captured = capsys.readouterr()
    assert code == 1
    assert json.loads(captured.err) == {
        "error": {
            "type": "ConfigError",
            "message": "suite desconocida",
            "field": "suite",
            "origin": "ia_nest_core",
            "request_id": "core-error-1",
        }
    }


def test_exit_code_two_prints_group_help(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "memory"])

    captured = capsys.readouterr()
    assert code == 2
    assert "acciones" in captured.out
    assert "maintain" in captured.out
    assert "recall" in captured.out


def test_general_help_uses_the_merged_catalog(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    """La ayuda general usa la cache local, nunca la red (retrabajo, criterio 4).

    `capability list` es quien refresca la cache; sin ese paso previo la
    ayuda general no conoceria 'future' -es el comportamiento correcto tras
    el retrabajo, no una regresion: construir el parser es una operacion
    puramente local.
    """
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)
    assert cli.main([*argv, "capability", "list", "--json"]) == 0
    capsys.readouterr()

    with pytest.raises(SystemExit) as exc_info:
        cli.main([*argv, "--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "future" in captured.out


def test_cli_streams_forwarded_events(
    monkeypatch,
    tmp_path,
    capsys,
    local_service_stub,
):
    argv = _cli_env(monkeypatch, tmp_path, local_service_stub)

    code = cli.main([*argv, "prompt", "stream", "--prompt", "hola"])

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out.splitlines() == [
        '{"chunk": "uno"}',
        '{"chunk": "dos"}',
        '{"stop_reason": "stop"}',
    ]
    path, payload = local_service_stub.requests[-1]
    assert path == "/prompt/stream"
    assert payload["prompt"] == "hola"
    assert payload["identity"]["service"] == "local_cli"
