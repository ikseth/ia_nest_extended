from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ianest_extended import (
    EngramStatus,
    EngramWrite,
    ExtendedConfig,
    MemoryIdentity,
    Principal,
    RecallQuery,
    SessionAlreadyExistsError,
    SessionNotActiveError,
    SessionStatus,
    StatedBy,
    TelemetryWriter,
)
from ianest_extended.maintain import run_maintenance
from ianest_extended.migrations import migration_resource


def _identity(user=None, session="shared"):
    return MemoryIdentity(
        user_id=user or f"session-{uuid4()}",
        session_id=session,
        service="test",
    )


def _dialog(postgres_store, identity, content):
    return postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content=content,
            identity=identity,
            stated_by=StatedBy.USER,
        ),
    )


def _set_activity(postgres_store, identity, timestamp):
    with postgres_store._connect() as connection:
        connection.execute(
            """
            UPDATE sessions
            SET last_activity_at = %s,
                created_at = LEAST(created_at, %s)
            WHERE user_id = %s AND session_id = %s
            """,
            (timestamp, timestamp, identity.user_id, identity.session_id),
        )


def test_active_session_keeps_its_first_turn_past_four_hours(
    postgres_store,
    tmp_path,
):
    identity = _identity()
    first = _dialog(postgres_store, identity, "primer turno")
    now = datetime.now(UTC)
    with postgres_store._connect() as connection:
        connection.execute(
            "UPDATE engrams SET created_at = %s WHERE id = %s",
            (now - timedelta(hours=10), first.id),
        )
    _dialog(postgres_store, identity, "actividad reciente")

    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        now=now,
    )

    assert postgres_store.get_session(
        identity.user_id, identity.session_id
    ).status is SessionStatus.ACTIVE
    assert postgres_store.get_engram(first.id).status is EngramStatus.ACTIVE
    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("dialog",),
            identity=identity,
            text="primer turno",
            top_k=10,
        )
    )
    assert first.id in {item.engram.id for item in recalled}


def test_inactive_session_archives_with_dialog_and_summary(
    postgres_store,
    tmp_path,
):
    identity = _identity()
    user = _dialog(postgres_store, identity, "turno usuario")
    model = _dialog(postgres_store, identity, "turno modelo")
    summary = postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=identity,
        content="resumen del hilo",
        source_ids=(user.id, model.id),
        source_trace_id="summary",
    ).summary
    now = datetime.now(UTC)
    _set_activity(postgres_store, identity, now - timedelta(hours=5))

    result = run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        now=now,
    )

    session = postgres_store.get_session(identity.user_id, identity.session_id)
    assert session.status is SessionStatus.ARCHIVED
    assert session.archived_at == now
    assert session.closed_at is None
    assert result.dialog_archived == 2
    assert postgres_store.get_engram(user.id).status is EngramStatus.ARCHIVED
    assert postgres_store.get_engram(model.id).status is EngramStatus.ARCHIVED
    assert postgres_store.get_engram(summary.id).status is EngramStatus.ARCHIVED


def test_archived_session_rejects_a_new_turn_with_typed_error(
    postgres_store,
    tmp_path,
):
    identity = _identity()
    _dialog(postgres_store, identity, "turno inicial")
    now = datetime.now(UTC)
    _set_activity(postgres_store, identity, now - timedelta(hours=5))
    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        now=now,
    )

    with pytest.raises(SessionNotActiveError) as exc_info:
        _dialog(postgres_store, identity, "no resucita")

    assert identity.session_id in exc_info.value.message
    assert SessionStatus.ARCHIVED.value in exc_info.value.message


def test_same_session_text_is_isolated_by_user(postgres_store, tmp_path):
    first = _identity(user=f"first-{uuid4()}")
    second = _identity(user=f"second-{uuid4()}")
    first_dialog = _dialog(postgres_store, first, "primero")
    second_dialog = _dialog(postgres_store, second, "segundo")
    now = datetime.now(UTC)
    _set_activity(postgres_store, first, now - timedelta(hours=5))

    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        now=now,
    )

    assert postgres_store.get_session(
        first.user_id, first.session_id
    ).status is SessionStatus.ARCHIVED
    assert postgres_store.get_session(
        second.user_id, second.session_id
    ).status is SessionStatus.ACTIVE
    assert postgres_store.get_engram(first_dialog.id).status is EngramStatus.ARCHIVED
    assert postgres_store.get_engram(second_dialog.id).status is EngramStatus.ACTIVE


def test_session_surface_store_lists_by_user_filters_and_derives_title(
    postgres_store,
    tmp_path,
):
    first = _identity(user=f"surface-first-{uuid4()}", session="shared")
    second = _identity(user=f"surface-second-{uuid4()}", session="shared")
    first_dialog = _dialog(postgres_store, first, "turno del primer usuario")
    _dialog(postgres_store, second, "turno del segundo usuario")
    summary_text = (
        "Resumen persistido que solo puede titular el hilo del primer usuario"
    )
    postgres_store.write_thread_summary(
        Principal.EXTENDED,
        identity=first,
        content=summary_text,
        source_ids=(first_dialog.id,),
        source_trace_id="surface-summary",
    )
    now = datetime.now(UTC)
    _set_activity(postgres_store, first, now - timedelta(hours=5))
    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        now=now,
    )

    assert postgres_store.list_sessions(first.user_id) == ()
    archived = postgres_store.list_sessions(
        first.user_id,
        SessionStatus.ARCHIVED,
    )
    assert len(archived) == 1
    assert archived[0].session_id == "shared"
    assert archived[0].title == summary_text
    assert archived[0].archived_at == now
    assert [item.session_id for item in postgres_store.list_sessions(second.user_id)] == [
        "shared"
    ]
    assert postgres_store.get_session(first.user_id, "shared").title == summary_text


def test_session_surface_store_creates_and_rejects_duplicate(postgres_store):
    user_id = f"surface-create-{uuid4()}"

    created = postgres_store.create_session(user_id, "client-chosen")

    assert created.user_id == user_id
    assert created.session_id == "client-chosen"
    assert created.status is SessionStatus.ACTIVE
    with pytest.raises(SessionAlreadyExistsError) as exc_info:
        postgres_store.create_session(user_id, "client-chosen")
    assert "ya existe" in exc_info.value.message


def test_sessions_migration_backfills_and_can_be_reapplied(postgres_store):
    psycopg = pytest.importorskip("psycopg")
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    schema = f"sessions_{uuid4().hex}"
    parameters = conninfo_to_dict(postgres_store._dsn)
    isolated_dsn = make_conninfo(
        **{**parameters, "options": f"-c search_path={schema},public"}
    )
    now = datetime.now(UTC)
    try:
        with psycopg.connect(postgres_store._dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema))
            )
        with psycopg.connect(isolated_dsn) as connection:
            base = migration_resource("0001_memory_registry.sql").read_text(
                encoding="ascii"
            ).replace("{{embedding_dimension}}", str(postgres_store._embedder.dimension))
            connection.execute(base)
            connection.execute(
                """
                INSERT INTO memory_types (
                    name, "class", writer_principal, retrieval_mode, scope,
                    namespaces, w_recency, w_similarity, w_stability, w_score,
                    half_life_seconds
                )
                VALUES ('dialog', 'strict', 'extended', 'ranked', 'session',
                        '{}', 1, 0, 0, 0, 14400)
                """
            )
            for session_id, created_at in (
                ("old", now - timedelta(hours=5)),
                ("recent", now - timedelta(hours=1)),
            ):
                vector = postgres_store._embedder.embed(session_id)
                vector_literal = "[" + ",".join(str(item) for item in vector) + "]"
                connection.execute(
                    """
                    INSERT INTO engrams (
                        type_name, user_id, session_id, namespace, content,
                        embedding, created_at
                    )
                    VALUES ('dialog', 'backfill-user', %s, NULL, %s,
                            %s::vector, %s)
                    """,
                    (session_id, session_id, vector_literal, created_at),
                )
            migration = migration_resource("0006_sessions.sql").read_text(
                encoding="ascii"
            )
            connection.execute(migration)
            connection.execute(migration)
            rows = connection.execute(
                """
                SELECT session_id, status, archived_at, closed_at
                FROM sessions ORDER BY session_id
                """
            ).fetchall()
            engram_rows = connection.execute(
                """
                SELECT session_id, status, archived_at
                FROM engrams ORDER BY session_id
                """
            ).fetchall()
            nullable = connection.execute(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'sessions' AND column_name = 'status'
                """
            ).fetchone()[0]
        assert [(row[0], row[1]) for row in rows] == [
            ("old", SessionStatus.ARCHIVED.value),
            ("recent", SessionStatus.ACTIVE.value),
        ]
        assert rows[0][2] is not None and rows[0][3] is None
        assert rows[1][2] is None and rows[1][3] is None
        assert [(row[0], row[1]) for row in engram_rows] == [
            ("old", EngramStatus.ARCHIVED.value),
            ("recent", EngramStatus.ACTIVE.value),
        ]
        assert engram_rows[0][2] == rows[0][2]
        assert engram_rows[1][2] is None
        assert nullable == "NO"
    finally:
        with psycopg.connect(postgres_store._dsn, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(
                    sql.Identifier(schema)
                )
            )
