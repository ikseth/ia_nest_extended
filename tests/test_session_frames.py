"""Criterios falsables del marco de la conversacion (ADR 0017)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from ianest_extended import (
    CoreResult,
    ExtendedComposition,
    ExtendedConfig,
    ExtendedRequestError,
    ExtendedService,
    InvalidEntitySeedError,
    MemoryIdentity,
    Principal,
)
from ianest_extended.entities import read_seed, split_entity_key
from ianest_extended.frames import compose_session_frame, frame_to_core

from .fakes import InMemoryStore


def _facts(*, account="account-1", person="person-1", device="device-1"):
    return {
        "account": {"value": account, "origin": "authenticated"},
        "person": {
            "value": person,
            "origin": "absent" if person is None else "validated",
        },
        "device": {
            "value": device,
            "origin": "absent" if device is None else "asserted",
        },
    }


def _identity(session="session-1", **changes):
    values = {
        "user_id": "user-1",
        "session_id": session,
        "service": "test_channel",
        "frame_facts": _facts(),
    }
    values.update(changes)
    return MemoryIdentity(**values)


def _turn(store, identity, prompt="hola", turn="turn-1"):
    return compose_session_frame(store, identity, prompt=prompt, turn=turn)


def _put(store, key, kind, curated=None):
    return store.put_entity(
        Principal.OPERATOR,
        key,
        kind,
        curated=curated or {},
        origin="test",
    )


def test_opening_is_complete_and_only_changes_when_edge_facts_change():
    store = InMemoryStore()
    identity = _identity()

    opening = _turn(store, identity)
    repeated = _turn(store, identity, turn="turn-2")
    changed = _turn(
        store,
        replace(identity, frame_facts=_facts(device="device:with:colon")),
        turn="turn-3",
    )

    assert opening.seq == 0
    assert opening.cause == "open"
    assert repeated == opening
    assert len(store.frames[("user-1", "session-1")]) == 2
    assert changed.seq == 1
    assert changed.cause == "edge"
    assert changed.changed == ("device",)
    assert changed.device["key"] == "account:account-1:device:with:colon"
    assert split_entity_key(changed.device["key"]) == (
        "account",
        "account-1:device:with:colon",
    )
    for frame in (opening, changed):
        assert frame.missing is not None
        assert all(getattr(frame, part) is not None for part in (
            "account", "person", "device", "place"
        ))


def test_known_unresolved_unknown_shared_and_device_header_priority():
    store = InMemoryStore()
    person = _put(store, "directory:person-1", "person")
    device = _put(store, "account:account-1:device-1", "device")

    known = _turn(store, _identity())
    unresolved = _turn(
        store,
        _identity("session-2", frame_facts=_facts(person="missing")),
    )
    absent = _turn(
        store,
        _identity(
            "session-3",
            frame_facts=_facts(person=None, device=None),
        ),
    )

    assert known.person | {"entity_id": str(person.id)} == known.person
    assert known.person["version"] == person.version
    assert known.device["entity_id"] == str(device.id)
    assert unresolved.person["state"] == "unresolved"
    assert unresolved.person["key"] == "directory:missing"
    assert absent.person["state"] == "unknown"
    assert absent.device["state"] == "unknown"
    assert store.unresolved_frame_keys()[0].key == "directory:missing"

    shared = _put(store, "directory:shared-1", "device", {"shared": True})
    shared_frame = _turn(
        store,
        _identity(
            "session-4",
            frame_facts=_facts(person="shared-1", device=None),
        ),
    )
    assert shared_frame.person["state"] == "unknown"
    assert shared_frame.device["entity_id"] == str(shared.id)

    explicit = _put(store, "account:account-1:explicit", "device")
    explicit_frame = _turn(
        store,
        _identity(
            "session-5",
            frame_facts=_facts(person="shared-1", device="explicit"),
        ),
    )
    assert explicit_frame.person["state"] == "unknown"
    assert explicit_frame.device["entity_id"] == str(explicit.id)


def test_place_prefers_device_and_opening_versions_are_pinned():
    store = InMemoryStore()
    home_person = _put(store, "seed:home-person", "home")
    home_device = _put(store, "seed:home-device", "home")
    person = _put(
        store,
        "directory:person-1",
        "person",
        {"home": "seed:home-person", "language": "es"},
    )
    device = _put(
        store,
        "account:account-1:device-1",
        "device",
        {"home": "seed:home-device", "language": "en"},
    )

    opening = _turn(store, _identity())
    public = frame_to_core(store, opening, channel="test_channel")
    assert opening.place["entity_id"] == str(home_device.id)
    assert opening.place["via"] == "device"
    assert public["language"] == "es"
    assert public["channel"] == "test_channel"
    assert "key" not in str(public)
    assert "entity_id" not in str(public)

    _put(
        store,
        "directory:person-1",
        "person",
        {"home": "seed:home-device"},
    )
    same_session = _turn(store, _identity(), turn="turn-2")
    next_session = _turn(
        store,
        _identity("session-2", frame_facts=_facts(device=None)),
    )
    assert same_session.person["version"] == person.version
    assert same_session.place["entity_id"] == str(home_device.id)
    assert next_session.person["version"] == person.version + 1
    assert next_session.place["entity_id"] == str(home_device.id)
    assert next_session.place["via"] == "person"
    assert home_person.id != home_device.id

    person_only = _turn(
        store,
        _identity(
            "session-3",
            frame_facts=_facts(device=None),
        ),
    )
    assert person_only.person["version"] == person.version + 1
    assert person_only.place["entity_id"] == str(home_device.id)
    _put(
        store,
        "directory:person-1",
        "person",
        {"home": "seed:home-person"},
    )
    pinned = _turn(
        store,
        _identity(
            "session-3",
            frame_facts=_facts(device=None),
        ),
        turn="turn-2",
    )
    following = _turn(
        store,
        _identity(
            "session-4",
            frame_facts=_facts(device=None),
        ),
    )
    assert pinned.person["version"] == person.version + 1
    assert pinned.place["entity_id"] == str(home_device.id)
    assert following.person["version"] == person.version + 2
    assert following.place["entity_id"] == str(home_person.id)
    assert device.kind == "device"


def test_awaiting_part_stores_next_literal_turn_and_then_clears_it():
    store = InMemoryStore()
    identity = _identity(frame_facts=_facts(person=None, device=None))
    _turn(store, identity)
    store.set_session_awaiting_part("user-1", "session-1", "place")

    stated = _turn(store, identity, prompt="en Madrid", turn="turn-2")
    unchanged = _turn(store, identity, prompt="soy papa", turn="turn-3")

    assert stated.seq == 1
    assert stated.cause == "dialog"
    assert stated.changed == ("place",)
    assert stated.place == {
        "state": "stated",
        "origin": "dialog",
        "value": "en Madrid",
        "turn": "turn-2",
    }
    assert "place" not in stated.missing
    assert store.sessions[("user-1", "session-1")].awaiting_part is None
    assert unchanged == stated


def test_old_edge_creates_unknown_frame_without_enrichment():
    store = InMemoryStore()
    frame = _turn(store, _identity(frame_facts=None))

    assert frame.account["state"] == "unknown"
    assert frame.person["state"] == "unknown"
    assert frame.device["state"] == "unknown"
    assert frame.missing == ("person", "device", "place")


@pytest.mark.parametrize(
    "frame_facts",
    [
        {},
        {"account": {}, "person": {}, "device": {}},
        {
            "account": {"value": "a", "origin": "asserted"},
            "person": {"value": None, "origin": "absent"},
            "device": {"value": None, "origin": "absent"},
        },
    ],
)
def test_malformed_frame_facts_stop_before_core(tmp_path, frame_facts):
    service = ExtendedService(
        ExtendedComposition(
            ExtendedConfig(
                telemetry_dir=tmp_path,
                session_state_path=tmp_path / "session",
                embedding_dimension=2,
            ),
            memory_store=InMemoryStore(),
        )
    )
    with pytest.raises(ExtendedRequestError) as exc_info:
        service.prompt_run(
            "hola",
            _identity(frame_facts=frame_facts),
            enrich=False,
        )
    assert exc_info.value.field.startswith("identity.frame_facts")


class _AwaitingCore:
    def __init__(self):
        self.identities = []
        self.turns = []

    def prompt_run(self, prompt, identity, model=None, domain=None, turn=False):
        self.identities.append(identity)
        self.turns.append(turn)
        payload = {
            "response": "donde estas",
            "trace": {"request_id": "core-1", "finish_reason": "stop"},
            "input_required": {"part": "place"},
        }
        return CoreResult("donde estas", payload["trace"], payload)


def test_service_records_provisional_input_required_shape(tmp_path):
    store = InMemoryStore()
    core = _AwaitingCore()
    service = ExtendedService(
        ExtendedComposition(
            ExtendedConfig(
                telemetry_dir=tmp_path,
                session_state_path=tmp_path / "session",
                embedding_dimension=2,
            ),
            core=core,
            memory_store=store,
        )
    )

    service.prompt_run("hola", _identity(), enrich=False)

    assert store.sessions[("user-1", "session-1")].awaiting_part == "place"
    # El turno del interlocutor se declara turno: es el unico que lleva marco.
    assert core.turns == [True]


def test_rest_and_mcp_payload_identity_reads_frame_fields(tmp_path):
    store = InMemoryStore()
    core = _AwaitingCore()
    service = ExtendedService(
        ExtendedComposition(
            ExtendedConfig(
                telemetry_dir=tmp_path,
                session_state_path=tmp_path / "session",
                embedding_dimension=2,
            ),
            core=core,
            memory_store=store,
        )
    )

    service.invoke(
        "prompt.run",
        {
            "prompt": "hola",
            "enrich": False,
            "identity": {
                "user_id": "user-1",
                "session_id": "session-1",
                "interlocutor_profile": "child",
                "audience": "general",
                "frame_facts": _facts(),
            },
        },
    )

    identity = core.identities[-1]
    assert identity.interlocutor_profile == "restricted"
    assert identity.audience == "general"
    assert identity.frame_facts == _facts()
    assert identity.to_core_dict()["interlocutor_profile"] == "restricted"
    assert "audience" not in identity.to_core_dict()


@pytest.mark.parametrize("fact", ("role", "groups"))
def test_seed_rejects_capability_facts_and_dangling_home(tmp_path, fact):
    capability = tmp_path / f"{fact}.toml"
    capability.write_text(
        '[[entity]]\nkey="directory:person-1"\nkind="person"\n'
        f'name="Persona Uno"\n{fact}="forbidden"\n',
        encoding="ascii",
    )
    dangling = tmp_path / "dangling.toml"
    dangling.write_text(
        '[[entity]]\nkey="directory:person-1"\nkind="person"\n'
        'name="Persona Uno"\nhome="seed:missing"\n',
        encoding="ascii",
    )

    with pytest.raises(InvalidEntitySeedError, match=f"entrada 0.*{fact}"):
        read_seed(capability, ())
    with pytest.raises(InvalidEntitySeedError, match="entrada 0.*seed:missing"):
        read_seed(dangling, ())
