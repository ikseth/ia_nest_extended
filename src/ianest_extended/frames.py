"""Composicion versionada del marco de una sesion (extended ADR 0017)."""

from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from .errors import ExtendedRequestError
from .models import Entity, EntityVersion, MemoryIdentity, SessionFrame

FRAME_PARTS = ("account", "person", "device", "place")
AWAITABLE_PARTS = ("person", "device", "place")


def compose_session_frame(
    store,
    identity: MemoryIdentity,
    *,
    prompt: str,
    turn: str,
) -> SessionFrame:
    """Declara la sesion y devuelve su marco vigente para este turno."""
    if not identity.user_id or not identity.session_id:
        raise ExtendedRequestError(
            "el marco exige user_id y session_id", "identity"
        )
    store.touch_session(identity.user_id, identity.session_id)
    current = store.get_session_frame(identity.user_id, identity.session_id)
    awaiting = store.take_session_awaiting_part(
        identity.user_id, identity.session_id
    )
    if current is not None and awaiting in AWAITABLE_PARTS:
        stated = _stated_part(prompt, turn)
        parts = _parts(current)
        parts[awaiting] = stated
        current = store.append_session_frame(
            replace(
                current,
                seq=current.seq + 1,
                **parts,
                missing=_missing(parts),
                cause="dialog",
                changed=(awaiting,),
            )
        )

    if current is None:
        parts = _resolve_opening(store, identity)
        return store.append_session_frame(
            SessionFrame(
                user_id=identity.user_id,
                session_id=identity.session_id,
                seq=0,
                **parts,
                missing=_missing(parts),
                cause="open",
                changed=FRAME_PARTS,
                created_at=store.frame_timestamp(),
            )
        )

    if identity.frame_facts is None:
        return current
    parts = _resolve_edge(store, identity, current)
    previous = _parts(current)
    changed = tuple(name for name in FRAME_PARTS if parts[name] != previous[name])
    if not changed:
        return current
    return store.append_session_frame(
        replace(
            current,
            seq=current.seq + 1,
            **parts,
            missing=_missing(parts),
            cause="edge",
            changed=changed,
        )
    )


def frame_to_core(store, frame: SessionFrame, *, channel: str | None) -> dict[str, Any]:
    """Proyecta el marco sin claves, ids ni versiones internas."""
    person_version = _part_version(store, frame.person)
    device_version = _part_version(store, frame.device)
    place_version = _part_version(store, frame.place)
    person = _public_part(frame.person)
    device = _public_part(frame.device)
    place = _public_part(frame.place)
    if person_version is not None:
        person["name"] = person_version.name
    if device_version is not None:
        device["name"] = device_version.name
        if "shared" in device_version.curated:
            device["shared"] = device_version.curated["shared"]
    if place_version is not None:
        place["home"] = place_version.name
        for name in ("locality", "timezone"):
            if name in place_version.curated:
                place[name] = place_version.curated[name]
    language = None
    for version in (person_version, device_version):
        if version is not None and isinstance(version.curated.get("language"), str):
            language = version.curated["language"]
            break
    stated = {
        name: part["value"]
        for name, part in _parts(frame).items()
        if part["state"] == "stated"
    }
    result: dict[str, Any] = {
        "channel": channel,
        "person": person,
        "device": device,
        "place": place,
        "language": language,
        "missing": list(frame.missing),
    }
    if stated:
        result["stated"] = stated
    return result


def frame_telemetry(frame: SessionFrame | None) -> dict[str, Any]:
    if frame is None:
        return {"composed": False}
    return {
        "composed": True,
        "seq": frame.seq,
        "account": frame.account["state"],
        "person": frame.person["state"],
        "device": frame.device["state"],
        "place": frame.place["state"],
        "missing": list(frame.missing),
    }


def input_required_part(result: object) -> str | None:
    """Compatibilidad provisional hasta que el core publique su ADR."""
    if not isinstance(result, dict):
        return None
    candidates = (result.get("input_required"), _trace_input_required(result))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        part = candidate.get("part")
        if part in AWAITABLE_PARTS:
            return str(part)
    return None


def _trace_input_required(result: dict[str, Any]) -> object:
    trace = result.get("trace")
    return trace.get("input_required") if isinstance(trace, dict) else None


def _resolve_opening(store, identity: MemoryIdentity) -> dict[str, dict[str, Any]]:
    if identity.frame_facts is None:
        return {
            "account": _unknown("absent"),
            "person": _unknown("absent"),
            "device": _unknown("absent"),
            "place": _unknown("absent"),
        }
    return _resolve_edge(store, identity, None)


def _resolve_edge(
    store,
    identity: MemoryIdentity,
    current: SessionFrame | None,
) -> dict[str, dict[str, Any]]:
    facts = identity.frame_facts
    assert facts is not None
    old = _parts(current) if current is not None else {}
    account_value = facts["account"]["value"]
    account = _account_part(account_value, facts["account"]["origin"])
    account = _pin_same(old.get("account"), account)

    person_value = facts["person"]["value"]
    person_key = None if person_value is None else f"directory:{person_value}"
    person = _unknown(facts["person"]["origin"])
    shared_device = None
    if person_key is not None:
        old_person = old.get("person")
        old_device = old.get("device")
        if _same_key(old_person, person_key):
            person = old_person
        elif _same_key(old_device, person_key) and old_person is not None:
            person = old_person
            shared_device = old_device
        else:
            resolved = store.resolve_entity(person_key)
            if resolved is None:
                person = _unresolved(person_key, facts["person"]["origin"])
            elif resolved.kind == "person":
                person = _known(resolved, person_key, facts["person"]["origin"])
            elif resolved.kind == "device" and resolved.curated.get("shared") is True:
                person = _unknown(facts["person"]["origin"])
                shared_device = _known(resolved, person_key, "derived")
            else:
                person = _unresolved(person_key, facts["person"]["origin"])
    elif old.get("person", {}).get("state") == "stated":
        person = old["person"]

    device_value = facts["device"]["value"]
    if device_value is not None and account_value is not None:
        device_key = f"account:{account_value}:{device_value}"
        if _same_key(old.get("device"), device_key):
            device = old["device"]
        else:
            resolved = store.resolve_entity(device_key)
            device = (
                _unresolved(device_key, facts["device"]["origin"])
                if resolved is None or resolved.kind != "device"
                else _known(resolved, device_key, facts["device"]["origin"])
            )
    elif shared_device is not None:
        device = shared_device
    elif old.get("device", {}).get("state") == "stated":
        device = old["device"]
    else:
        device = _unknown(facts["device"]["origin"])

    if current is not None and person == old["person"] and device == old["device"]:
        place = old["place"]
    else:
        place = _derive_place(store, device, person, old.get("place"))
    return {"account": account, "person": person, "device": device, "place": place}


def _derive_place(store, device, person, previous):
    for via, part in (("device", device), ("person", person)):
        version = _part_version(store, part)
        if version is None:
            continue
        home_key = version.curated.get("home")
        if not isinstance(home_key, str):
            continue
        if _same_key(previous, home_key):
            if previous.get("via") == via:
                return previous
            return {**previous, "via": via}
        home = store.resolve_entity(home_key)
        if home is not None and home.kind == "home":
            known = _known(home, home_key, "derived")
            known["via"] = via
            return known
    return _unknown("absent")


def _account_part(value: str | None, origin: str | None) -> dict[str, Any]:
    if value is None:
        return _unknown(origin or "absent")
    return {"state": "known", "origin": origin, "key": f"account:{value}"}


def _known(entity: Entity, key: str, origin: str | None) -> dict[str, Any]:
    return {
        "state": "known",
        "origin": origin,
        "key": key,
        "entity_id": str(entity.id),
        "version": entity.version,
    }


def _unresolved(key: str, origin: str | None) -> dict[str, Any]:
    return {"state": "unresolved", "origin": origin, "key": key}


def _unknown(origin: str | None) -> dict[str, Any]:
    return {"state": "unknown", "origin": origin or "absent"}


def _stated_part(value: str, turn: str) -> dict[str, Any]:
    return {"state": "stated", "origin": "dialog", "value": value, "turn": turn}


def _pin_same(previous, candidate):
    return previous if _same_key(previous, candidate.get("key")) else candidate


def _same_key(part, key) -> bool:
    return isinstance(part, dict) and key is not None and part.get("key") == key


def _parts(frame: SessionFrame | None) -> dict[str, dict[str, Any]]:
    if frame is None:
        return {}
    return {name: getattr(frame, name) for name in FRAME_PARTS}


def _missing(parts: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    return tuple(
        name
        for name in ("person", "device", "place")
        if parts[name]["state"] in {"unknown", "unresolved"}
    )


def _part_version(store, part: dict[str, Any]) -> EntityVersion | None:
    if part.get("state") != "known" or "entity_id" not in part:
        return None
    return store.get_entity_version(UUID(part["entity_id"]), int(part["version"]))


def _public_part(part: dict[str, Any]) -> dict[str, Any]:
    return {"state": part["state"]}
