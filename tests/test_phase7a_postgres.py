"""Aceptacion de fase 7a contra PostgreSQL real (skip explicito sin DB)."""

import pytest

from ianest_extended import (
    ExtendedComposition,
    ExtendedConfig,
    ExtendedService,
    SchemaMigrationRequiredError,
)

UNREACHABLE = "http://127.0.0.1:1"
UNMIGRATED_SCHEMA = "fase7a_unmigrated"


def _config(dsn, tmp_path, **changes):
    return ExtendedConfig(
        core_url=UNREACHABLE,
        ollama_url=UNREACHABLE,
        database_dsn=dsn,
        telemetry_dir=tmp_path,
        session_state_path=tmp_path / "session_id",
        embedding_dimension=2,
        **changes,
    )


def test_maintain_runs_against_postgres_with_core_and_ollama_down(
    postgres_store,
    tmp_path,
):
    """Criterio 8 sobre el sustrato real: el root no construye lo que no usa."""
    composition = ExtendedComposition(_config(postgres_store._dsn, tmp_path))
    service = ExtendedService(composition)

    result = service.memory_maintain(dry_run=True)

    assert result["dry_run"] is True
    assert result["dialog_archived"] >= 0
    assert composition.core_constructed is False


def test_read_only_capability_fails_on_unmigrated_schema(
    postgres_store,
    tmp_path,
):
    """Criterio 10 sobre el sustrato real: falla tipado y no muta esquema."""
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    parameters = conninfo_to_dict(postgres_store._dsn)
    with psycopg.connect(postgres_store._dsn, autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                sql.Identifier(UNMIGRATED_SCHEMA)
            )
        )
        connection.execute(
            sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(UNMIGRATED_SCHEMA))
        )
    unmigrated_dsn = make_conninfo(
        **{**parameters, "options": f"-c search_path={UNMIGRATED_SCHEMA}"}
    )
    service = ExtendedService(
        ExtendedComposition(_config(unmigrated_dsn, tmp_path))
    )

    with pytest.raises(SchemaMigrationRequiredError) as exc_info:
        service.memory_type_list()

    assert "runtime migrate" in exc_info.value.message
    with psycopg.connect(postgres_store._dsn) as connection:
        rows = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = %s",
            (UNMIGRATED_SCHEMA,),
        ).fetchall()
    assert rows == []
