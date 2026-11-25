"""Persistencia PostgreSQL del marco de la conversacion (ADR 0017)."""

from __future__ import annotations

from uuid import uuid4

import psycopg

from ianest_extended import MemoryIdentity, Principal
from ianest_extended.frames import compose_session_frame
from ianest_extended.migrations import migration_resource


def _facts(account, person, device):
    return {
        "account": {"value": account, "origin": "authenticated"},
        "person": {"value": person, "origin": "validated"},
        "device": {"value": device, "origin": "asserted"},
    }


def test_postgres_frames_are_append_only_complete_and_idempotently_migrated(
    postgres_store,
):
    suffix = uuid4().hex
    user_id = f"user-{suffix}"
    session_id = f"session-{suffix}"
    account_id = f"account-{suffix}"
    person_id = f"person-{suffix}"
    device_id = f"device-{suffix}"
    home_key = f"seed:home-{suffix}"
    postgres_store.put_entity(
        Principal.OPERATOR,
        home_key,
        "home",
        curated={"locality": "Villa Prueba"},
        origin="cli",
    )
    postgres_store.put_entity(
        Principal.OPERATOR,
        f"directory:{person_id}",
        "person",
        curated={"home": home_key},
        origin="cli",
    )
    postgres_store.put_entity(
        Principal.OPERATOR,
        f"account:{account_id}:{device_id}",
        "device",
        curated={"home": home_key},
        origin="cli",
    )
    identity = MemoryIdentity(
        user_id=user_id,
        session_id=session_id,
        service="test",
        frame_facts=_facts(account_id, person_id, device_id),
    )

    opening = compose_session_frame(
        postgres_store, identity, prompt="hola", turn="turn-1"
    )
    repeated = compose_session_frame(
        postgres_store, identity, prompt="otra", turn="turn-2"
    )
    changed = compose_session_frame(
        postgres_store,
        MemoryIdentity(
            user_id=user_id,
            session_id=session_id,
            service="test",
            frame_facts=_facts(account_id, person_id, "other-device"),
        ),
        prompt="otra",
        turn="turn-3",
    )

    assert opening.seq == 0
    assert opening.person["state"] == "known"
    assert opening.device["state"] == "known"
    assert opening.place["state"] == "known"
    assert opening.missing == ()
    assert repeated == opening
    assert changed.seq == 1
    assert changed.cause == "edge"
    assert changed.changed == ("device", "place")
    assert changed.missing == ("device",)
    assert changed.place["via"] == "person"

    with postgres_store._connect() as connection:
        row = connection.execute(
            """SELECT count(*) FROM session_frames
               WHERE user_id = %s AND session_id = %s""",
            (user_id, session_id),
        ).fetchone()
    assert row["count"] == 2

    with psycopg.connect(postgres_store._dsn) as connection:
        migration = migration_resource("0009_session_frames.sql").read_text(
            encoding="ascii"
        )
        connection.execute(migration)
        connection.execute(migration)

    with psycopg.connect(postgres_store._dsn) as connection:
        try:
            connection.execute(
                """UPDATE session_frames SET cause = 'edge'
                   WHERE user_id = %s AND session_id = %s AND seq = 0""",
                (user_id, session_id),
            )
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("session_frames permitio UPDATE")


def test_postgres_unresolved_lists_entities_without_home(postgres_store):
    suffix = uuid4().hex
    account_id = f"account-{suffix}"
    home_key = f"seed:home-{suffix}"
    postgres_store.put_entity(
        Principal.OPERATOR, home_key, "home",
        curated={"locality": "Villa Prueba"}, origin="cli",
    )
    postgres_store.put_entity(
        Principal.OPERATOR, f"directory:person-{suffix}", "person",
        curated={}, origin="cli",
    )
    postgres_store.put_entity(
        Principal.OPERATOR, f"account:{account_id}:device-home-{suffix}", "device",
        curated={"home": home_key}, origin="cli",
    )
    postgres_store.put_entity(
        Principal.OPERATOR, f"account:{account_id}:device-bare-{suffix}", "device",
        curated={}, origin="cli",
    )

    def turn(name, person, device):
        compose_session_frame(
            postgres_store,
            MemoryIdentity(
                user_id=f"user-{name}-{suffix}",
                session_id=f"session-{name}-{suffix}",
                service="test",
                frame_facts={
                    "account": {"value": account_id, "origin": "authenticated"},
                    "person": {
                        "value": person,
                        "origin": "absent" if person is None else "validated",
                    },
                    "device": {
                        "value": device,
                        "origin": "absent" if device is None else "asserted",
                    },
                },
            ),
            prompt="hola",
            turn=f"turn-{name}",
        )

    turn("alone", f"person-{suffix}", None)
    turn("with-home", f"person-{suffix}", f"device-home-{suffix}")
    turn("bare", None, f"device-bare-{suffix}")
    turn("missing", f"missing-{suffix}", None)

    rows = {
        (row.key, row.reason): row
        for row in postgres_store.unresolved_frame_keys()
        if suffix in row.key
    }
    assert rows[(f"directory:person-{suffix}", "no_home")].count == 1
    assert (f"account:{account_id}:device-bare-{suffix}", "no_home") in rows
    assert (f"account:{account_id}:device-home-{suffix}", "no_home") not in rows
    assert (f"directory:missing-{suffix}", "no_entity") in rows
