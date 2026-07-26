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


def _write_episodic(postgres_store, *, stability=0, score=0.0):
    return postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content=f"episodic literal {uuid4()}",
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


def test_phase4_promotion_preserves_source_and_creates_lineage(
    postgres_store,
    tmp_path,
):
    source = _write_episodic(postgres_store, stability=3)
    _set_age(postgres_store, source.id, timedelta(days=120))
    before_count = len(_database_snapshot(postgres_store)[0])

    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
    )

    archived = postgres_store.get_engram(source.id)
    with postgres_store._connect() as connection:
        target = connection.execute(
            """
            SELECT e.*
            FROM memory_links ml
            JOIN engrams e ON e.id = ml.target_engram_id
            WHERE ml.source_id = %s
              AND ml.link_kind = 'consolidated_from'
            """,
            (source.id,),
        ).fetchone()
        after_count = connection.execute(
            "SELECT count(*) AS count FROM engrams"
        ).fetchone()["count"]

    assert archived.status is EngramStatus.ARCHIVED
    assert archived.archived_reason == "promoted_to_semantic"
    assert target["type_name"] == "semantic"
    assert target["content"] == source.content
    assert after_count >= before_count + 1


def test_phase4_recent_or_unmerited_episodic_is_not_promoted(
    postgres_store,
    tmp_path,
):
    recent = _write_episodic(postgres_store, stability=3)
    old_without_merit = _write_episodic(postgres_store)
    _set_age(postgres_store, old_without_merit.id, timedelta(days=120))

    run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
    )

    assert postgres_store.get_engram(recent.id).status is EngramStatus.ACTIVE
    assert (
        postgres_store.get_engram(old_without_merit.id).status
        is EngramStatus.ACTIVE
    )
    with postgres_store._connect() as connection:
        links = connection.execute(
            """
            SELECT count(*) AS count
            FROM memory_links
            WHERE source_id = ANY(%s::uuid[])
              AND link_kind = 'consolidated_from'
            """,
            ([recent.id, old_without_merit.id],),
        ).fetchone()["count"]
    assert links == 0


def test_phase4_old_dialog_is_archived_and_recent_stays_active(
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

    assert postgres_store.get_engram(old.id).status is EngramStatus.ARCHIVED
    assert postgres_store.get_engram(recent.id).status is EngramStatus.ACTIVE


def test_phase4_executor_enforces_target_authority(
    postgres_store,
    tmp_path,
):
    source = _write_episodic(postgres_store)
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
    old_episodic = _write_episodic(postgres_store, stability=3)
    _set_age(postgres_store, old_episodic.id, timedelta(days=120))
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
    before = _database_snapshot(postgres_store)

    result = run_maintenance(
        store=postgres_store,
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(telemetry_dir=tmp_path),
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.dialog_archived >= 1
    assert result.episodic_promoted >= 1
    assert _database_snapshot(postgres_store) == before
