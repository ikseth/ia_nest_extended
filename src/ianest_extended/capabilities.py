"""Catalogo de capacidades: lo propio, y AYUDA de lo ajeno que conocemos.

`FORWARDED_CAPABILITIES` NO es la condicion para poder invocar una capacidad del
core, y no debe volver a serlo (ADR 0011, punto 11). El reenvio del servicio es
GENERICO y el CLI resuelve como capacidad reenviada cualquier `GRUPO ACCION` que
no declare: una capacidad nueva del core es invocable sin editar este fichero.

Lo unico que aporta esta lista es AYUDA ENRIQUECIDA -subcomando documentado,
verbo declarado, resumen- para las capacidades que hoy conocemos. Conocerlas
mejora la ergonomia; no las habilita.

INTERINO DECLARADO: sigue siendo una copia del catalogo ajeno, aunque ya no
bloquee nada. Desaparece cuando el core entregue `capability.list`
(`extended CR-0002`), momento en que el catalogo de abajo se OBTIENE en
ejecucion y se fusiona con el propio (ADR 0011, puntos 9 y 10).
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
        name="reasoning.stream",
        group="reasoning",
        action="stream",
        method="POST",
        streaming=True,
        summary=(
            "reenvia el razonamiento en streaming al core; NO lleva "
            "enriquecimiento"
        ),
    ),
    ForwardedCapability(
        name="task.plan",
        group="task",
        action="plan",
        method="POST",
        summary="reenvia la planificacion de tarea del core sin enriquecer",
    ),
    ForwardedCapability(
        name="task.stream",
        group="task",
        action="stream",
        method="POST",
        streaming=True,
        summary=(
            "reenvia la tarea en streaming al core; NO lleva enriquecimiento"
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
OVERRIDDEN_CAPABILITIES: tuple[str, ...] = (
    "prompt.run",
    "reasoning.run",
    "task.run",
)

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
