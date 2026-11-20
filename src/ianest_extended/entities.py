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
}


@dataclass(frozen=True, slots=True)
class SeedEntity:
    key: str
    kind: str
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


def read_seed(path: Path, provider_ceiling: tuple[str, ...]) -> SeedDocument:
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
            namespace, external_id = split_entity_key(key)
            if key in seen:
                raise InvalidEntityError("clave repetida", "key")
            if namespace != kind:
                raise InvalidEntityError(
                    "el namespace de key debe coincidir con kind", "key"
                )
            curated = {
                name: value
                for name, value in raw_entry.items()
                if name not in {"key", "kind"}
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
        entries.append(SeedEntity(key, kind, curated, index))
    extra = set(document) - {"entity"}
    if extra:
        raise InvalidEntitySeedError(
            f"claves TOML no declaradas: {', '.join(sorted(extra))}", "file"
        )
    return SeedDocument(tuple(entries), hashlib.sha256(raw).hexdigest())
