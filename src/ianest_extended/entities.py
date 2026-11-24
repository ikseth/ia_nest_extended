"""Esquema cerrado y entrada TOML del registro de entidades."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import InvalidEntityError, InvalidEntitySeedError


@dataclass(frozen=True, slots=True)
class EntityClass:
    observed: dict[str, type]
    curated: dict[str, type]


# Unica lista cerrada. Anadir una clase es anadir una entrada y sus hechos.
ENTITY_CLASSES: dict[str, EntityClass] = {
    "provider": EntityClass(observed={"name": str}, curated={"trusted": bool}),
    "person": EntityClass(observed={}, curated={"home": str, "language": str}),
    "device": EntityClass(
        observed={}, curated={"home": str, "shared": bool, "language": str}
    ),
    "home": EntityClass(
        observed={}, curated={"locality": str, "timezone": str, "provider": str}
    ),
}

ENTITY_KEY_NAMESPACES = {
    "provider": {"provider"},
    "person": {"directory"},
    "device": {"account", "directory"},
    "home": {"seed"},
}


@dataclass(frozen=True, slots=True)
class SeedEntity:
    key: str
    kind: str
    name: str | None
    curated: dict[str, Any]
    index: int


@dataclass(frozen=True, slots=True)
class SeedDocument:
    entries: tuple[SeedEntity, ...]
    sha256: str

    @property
    def origin(self) -> str:
        return f"seed:{self.sha256}"


def split_entity_key(key: str) -> tuple[str, str]:
    if not isinstance(key, str) or ":" not in key:
        raise InvalidEntityError(
            "entity key debe tener la forma namespace:external_id", "key"
        )
    namespace, external_id = key.split(":", 1)
    if not namespace or not external_id:
        raise InvalidEntityError(
            "entity key debe tener namespace y external_id no vacios", "key"
        )
    return namespace, external_id


def validate_facts(kind: str, part: str, facts: dict[str, Any]) -> None:
    declaration = ENTITY_CLASSES.get(kind)
    if declaration is None:
        raise InvalidEntityError(f"clase de entidad desconocida: {kind!r}", "kind")
    allowed = declaration.observed if part == "observed" else declaration.curated
    for name, value in facts.items():
        expected = allowed.get(name)
        if expected is None:
            raise InvalidEntityError(
                f"hecho {part} no declarado para {kind!r}: {name!r}", name
            )
        if type(value) is not expected:
            raise InvalidEntityError(
                f"hecho {name!r} de {kind!r} debe ser {expected.__name__}", name
            )


def validate_entity_key(key: str, kind: str) -> tuple[str, str]:
    namespace, external_id = split_entity_key(key)
    if namespace not in ENTITY_KEY_NAMESPACES.get(kind, set()):
        raise InvalidEntityError(
            f"namespace {namespace!r} no declarado para {kind!r}", "key"
        )
    if kind == "device" and namespace == "account":
        account, separator, device = external_id.partition(":")
        if not separator or not account or not device:
            raise InvalidEntityError(
                "device con namespace account exige account:<uid>:<device_id>",
                "key",
            )
    return namespace, external_id


def read_seed(
    path: Path,
    provider_ceiling: tuple[str, ...],
    *,
    current_home_keys: tuple[str, ...] = (),
) -> SeedDocument:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InvalidEntitySeedError(
            f"no se puede leer la siembra: {path}", "file"
        ) from exc
    try:
        document = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InvalidEntitySeedError(
            f"siembra TOML invalida: {exc}", "file"
        ) from exc
    raw_entries = document.get("entity", [])
    if not isinstance(raw_entries, list):
        raise InvalidEntitySeedError("[[entity]] debe ser una lista TOML", "entity")
    entries: list[SeedEntity] = []
    seen: set[str] = set()
    ceiling = set(provider_ceiling)
    for index, raw_entry in enumerate(raw_entries):
        key_hint = raw_entry.get("key") if isinstance(raw_entry, dict) else None
        label = f"entrada {index} ({key_hint!r})"
        try:
            if not isinstance(raw_entry, dict):
                raise InvalidEntityError("la entrada debe ser una tabla", "entity")
            key = raw_entry.get("key")
            kind = raw_entry.get("kind")
            if not isinstance(key, str):
                raise InvalidEntityError("key debe ser texto", "key")
            if not isinstance(kind, str):
                raise InvalidEntityError("kind debe ser texto", "kind")
            namespace, external_id = validate_entity_key(key, kind)
            if key in seen:
                raise InvalidEntityError("clave repetida", "key")
            name = raw_entry.get("name")
            if name is not None and (not isinstance(name, str) or not name.strip()):
                raise InvalidEntityError("name debe ser texto no vacio", "name")
            if kind in {"person", "device", "home"} and name is None:
                raise InvalidEntityError("name es obligatorio", "name")
            curated = {
                name: value
                for name, value in raw_entry.items()
                if name not in {"key", "kind", "name"}
            }
            validate_facts(kind, "curated", curated)
            if kind == "provider" and external_id not in ceiling:
                raise InvalidEntityError(
                    f"provider {external_id!r} no esta en el techo", "key"
                )
        except InvalidEntityError as exc:
            raise InvalidEntitySeedError(
                f"{label}: {exc.message}", exc.field or "entity"
            ) from exc
        seen.add(key)
        entries.append(SeedEntity(key, kind, name, curated, index))
    extra = set(document) - {"entity"}
    if extra:
        raise InvalidEntitySeedError(
            f"claves TOML no declaradas: {', '.join(sorted(extra))}", "file"
        )
    home_keys = {
        entry.key for entry in entries if entry.kind == "home"
    } | set(current_home_keys)
    for entry in entries:
        try:
            home = entry.curated.get("home")
            if home is not None and home not in home_keys:
                raise InvalidEntityError(
                    f"home {home!r} no identifica una casa vigente o sembrada",
                    "home",
                )
            provider = entry.curated.get("provider")
            if provider is not None:
                namespace, external_id = split_entity_key(provider)
                if namespace != "provider" or external_id not in ceiling:
                    raise InvalidEntityError(
                        f"provider {provider!r} no esta en el techo", "provider"
                    )
        except InvalidEntityError as exc:
            raise InvalidEntitySeedError(
                f"entrada {entry.index} ({entry.key!r}): {exc.message}",
                exc.field or "entity",
            ) from exc
    return SeedDocument(tuple(entries), hashlib.sha256(raw).hexdigest())
