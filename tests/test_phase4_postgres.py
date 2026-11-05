from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from ianest_extended import (
    ConsolidationEvent,
    ConsolidationExecutor,
    ConsolidationTrigger,
    EngramStatus,
    EngramWrite,
    ExtendedConfig,
    MemoryIdentity,
    Principal,
    TelemetryWriter,
    WriteAuthorityError,
)
from ianest_extended.maintain import run_maintenance


def _write_thread_artifacts(postgres_store, *, stability=0, score=0.0):
    return postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="thread_artifacts",
            content=f"thread_artifacts literal {uuid4()}",
            identity=MemoryIdentity(
                user_id=f"phase4-{uuid4()}",
                session_id="A",
            ),
            namespace="facts",
            stability=stability,
            score=score,
        ),
    )


def _set_age(postgres_store, engram_id, age):
    timestamp = datetime.now(UTC) - age
    with postgres_store._connect() as connection:
        connection.execute(
            """
            UPDATE engrams
            SET created_at = %s,
                last_reinforced_at = %s
            WHERE id = %s
            """,
            (timestamp, timestamp, engram_id),
        )


def _set_session_activity(postgres_store, identity, age):
    timestamp = datetime.now(UTC) - age
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


def _database_snapshot(postgres_store):
    with postgres_store._connect() as connection:
        statuses = tuple(
            connection.execute(
                """
                SELECT id, type_name, status, archived_reason
                FROM engrams
                ORDER BY id
                """
            ).fetchall()
        )
        link_count = connection.execute(
            "SELECT count(*) AS count FROM memory_links"
        ).fetchone()["count"]
    return statuses, link_count


def test_maintain_never_promotes_thread_artifacts_to_semantic(
    postgres_store,
    tmp_path,
):
    source = _write_thread_artifacts(postgres_store, stability=3)
    _set_age(postgres_store, source.id, timedelta(days=120))

    result = run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
    )

    with postgres_store._connect() as connection:
        promoted = connection.execute(
            """
            SELECT count(*) AS count
            FROM memory_links
            WHERE source_id = %s AND link_kind = 'consolidated_from'
            """,
            (source.id,),
        ).fetchone()["count"]

    assert result.dialog_archived == 0
    assert postgres_store.get_engram(source.id).status is EngramStatus.ACTIVE
    assert promoted == 0


def test_phase4_old_dialog_stays_active_while_its_session_is_active(
    postgres_store,
    tmp_path,
):
    identity = MemoryIdentity(
        user_id=f"phase4-dialog-{uuid4()}",
        session_id="A",
    )
    old = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="old dialog",
            identity=identity,
        ),
    )
    recent = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="recent dialog",
            identity=identity,
        ),
    )
    _set_age(postgres_store, old.id, timedelta(hours=5))

    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
    )

    assert postgres_store.get_engram(old.id).status is EngramStatus.ACTIVE
    assert postgres_store.get_engram(recent.id).status is EngramStatus.ACTIVE


def test_phase4_executor_enforces_target_authority(
    postgres_store,
    tmp_path,
):
    source = _write_thread_artifacts(postgres_store)
    executor = ConsolidationExecutor(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
    )
    event = ConsolidationEvent(
        trigger=ConsolidationTrigger.MANUAL,
        principal=Principal.EXTENDED,
        source_ids=(source.id,),
        target_type="identity",
        content=source.content,
        target_namespace="persona",
        reason="conscience_request",
    )

    with pytest.raises(WriteAuthorityError):
        executor.execute(event)
    assert postgres_store.get_engram(source.id).status is EngramStatus.ACTIVE

    result = executor.execute(
        ConsolidationEvent(
            trigger=event.trigger,
            principal=Principal.CONSCIENCE,
            source_ids=event.source_ids,
            target_type=event.target_type,
            content=event.content,
            target_namespace=event.target_namespace,
            reason=event.reason,
        )
    )

    assert result.target is not None
    assert result.target.type_name == "identity"
    assert result.links_created == 1
    assert postgres_store.get_engram(source.id).status is EngramStatus.ARCHIVED


def test_phase4_dry_run_does_not_mutate_database(
    postgres_store,
    tmp_path,
):
    old_thread_artifacts = _write_thread_artifacts(postgres_store, stability=3)
    _set_age(postgres_store, old_thread_artifacts.id, timedelta(days=120))
    old_dialog = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content=f"dry run dialog {uuid4()}",
            identity=MemoryIdentity(
                user_id=f"phase4-dry-{uuid4()}",
                session_id="A",
            ),
        ),
    )
    _set_age(postgres_store, old_dialog.id, timedelta(hours=5))
    _set_session_activity(
        postgres_store,
        MemoryIdentity(
            user_id=old_dialog.user_id,
            session_id=old_dialog.session_id,
        ),
        timedelta(hours=5),
    )
    before = _database_snapshot(postgres_store)

    result = run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.dialog_archived >= 1
    assert _database_snapshot(postgres_store) == before
