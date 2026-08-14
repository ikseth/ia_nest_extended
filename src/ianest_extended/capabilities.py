"""Catalogo de capacidades: unico sitio donde se declara lo reenviado.

INTERINO DECLARADO (fase 7a): el reenvio del servicio es GENERICO y no necesita
esta lista -una capacidad que el core anada es alcanzable sin tocar codigo-.
La lista existe solo porque el CLI debe construir su ayuda y el core aun no
ofrece catalogo (`extended CR-0002`, propuesto). Cuando exista `capability.list`,
sustituir este dato por la consulta debe ser un cambio local a este modulo.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ForwardedCapability:
    """Una capacidad del core que esta capa reenvia sin alterar."""

    name: str
    group: str
    action: str
    method: str
    streaming: bool = False
    summary: str = ""


FORWARDED_CAPABILITIES: tuple[ForwardedCapability, ...] = (
    ForwardedCapability(
        name="prompt.stream",
        group="prompt",
        action="stream",
        method="POST",
        streaming=True,
        summary=(
            "reenvia el prompt en streaming al core; en esta fase NO lleva "
            "enriquecimiento (memoria ni RAG)"
        ),
    ),
    ForwardedCapability(
        name="domain.list",
        group="domain",
        action="list",
        method="GET",
        summary="reenvia el catalogo de dominios del core",
    ),
    ForwardedCapability(
        name="domain.route",
        group="domain",
        action="route",
        method="POST",
        summary="reenvia el ruteo semantico de un prompt al core",
    ),
    ForwardedCapability(
        name="model.list",
        group="model",
        action="list",
        method="GET",
        summary="reenvia el catalogo de modelos del core",
    ),
    ForwardedCapability(
        name="runtime.health",
        group="runtime",
        action="health",
        method="GET",
        summary="reenvia el estado del runtime del core",
    ),
    ForwardedCapability(
        name="config.validate",
        group="config",
        action="validate",
        method="POST",
        summary="reenvia la validacion de configuracion del core",
    ),
    ForwardedCapability(
        name="eval.run",
        group="eval",
        action="run",
        method="POST",
        summary="reenvia la bateria de evaluacion del core",
    ),
)

# Capacidades del core que esta capa SOBREESCRIBE (enriquece).
OVERRIDDEN_CAPABILITIES: tuple[str, ...] = ("prompt.run",)

# Capacidades PROPIAS de esta capa (extension aditiva).
OWN_CAPABILITIES: tuple[str, ...] = (
    "memory_type.list",
    "memory_type.validate",
    "memory.recall",
    "memory.write",
    "memory.consolidate",
    "memory.maintain",
    "knowledge.ingest",
    "knowledge.status",
    "knowledge.suggest",
    "knowledge.confirm",
    "knowledge.reject",
)


def forwarded_by_name(name: str) -> ForwardedCapability | None:
    for capability in FORWARDED_CAPABILITIES:
        if capability.name == name:
            return capability
    return None
