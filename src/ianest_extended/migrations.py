"""Recursos SQL incluidos en el paquete instalado."""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable


MIGRATION_NAMES = (
    "0001_memory_registry.sql",
    "0002_rag.sql",
    "0003_rag_domains.sql",
)


def migration_resource(name: str) -> Traversable:
    """Devuelve una migracion desde el paquete, editable o instalado."""
    if name not in MIGRATION_NAMES:
        raise ValueError(f"migracion desconocida: {name!r}")
    resource = files("ianest_extended").joinpath("db", "migrations", name)
    if not resource.is_file():
        raise FileNotFoundError(
            f"la migracion {name!r} no esta incluida en el paquete ianest_extended"
        )
    return resource
