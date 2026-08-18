"""Catalogo declarativo de las capacidades que esta capa implementa.

El catalogo ajeno nunca vive aqui. `LOCAL_CAPABILITIES` contiene solamente las
capacidades propias y las sobreescritas por extended. El catalogo del core se
obtiene en ejecucion y se fusiona en :mod:`ianest_extended.service`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal


ParamType = Literal["string", "integer", "boolean", "array", "object"]
Provenance = Literal["own", "overridden", "forwarded"]


@dataclass(frozen=True, slots=True)
class CapabilityParam:
    name: str
    type: ParamType
    required: bool
    choices: tuple[str, ...] | None
    default: object | None
    summary: str
    metavar: str | None
    cli: bool = True


@dataclass(frozen=True, slots=True)
class RestProjection:
    path: str
    method: str


@dataclass(frozen=True, slots=True)
class CliInput:
    name: str
    source: str
    targets: tuple[str, ...]
    metavar: str
    summary: str


@dataclass(frozen=True, slots=True)
class CliProjection:
    group: str
    action: str | None
    description: str
    epilog: str | None = None
    flags: tuple[str, ...] = ()
    flag_help: tuple[tuple[str, str], ...] = ()
    aliases: tuple[str, ...] = ()
    alias_summaries: tuple[tuple[str, str], ...] = ()
    inputs: tuple[CliInput, ...] = ()
    order: int = 0


@dataclass(frozen=True, slots=True)
class McpProjection:
    tool: str


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    summary: str
    identity: bool
    streaming: bool
    params: tuple[CapabilityParam, ...]
    rest: RestProjection | None
    cli: CliProjection | None
    mcp: McpProjection | None
    provenance: Provenance


def _param(
    name: str,
    type: ParamType,
    summary: str,
    *,
    required: bool = False,
    choices: tuple[str, ...] | None = None,
    default: object | None = None,
    metavar: str | None = None,
    cli: bool = True,
) -> CapabilityParam:
    return CapabilityParam(
        name, type, required, choices, default, summary, metavar, cli
    )


def _cli(
    group: str,
    action: str,
    description: str,
    *,
    flags: tuple[str, ...] = ("json",),
    flag_help: tuple[tuple[str, str], ...] = (
        ("json", "emite el resultado como JSON"),
    ),
    inputs: tuple[CliInput, ...] = (),
) -> CliProjection:
    return CliProjection(
        group,
        action,
        description,
        flags=flags,
        flag_help=flag_help,
        inputs=inputs,
    )


_PROMPT = _param(
    "prompt",
    "string",
    "texto que se enviara al modelo",
    required=True,
    metavar="TEXTO",
)
_MODEL = _param("model", "string", "modelo directo", metavar="MODELO")
_DOMAIN = _param(
    "domain",
    "string",
    "dominio unico de enriquecimiento y ruteo",
    metavar="DOMINIO",
)
_ENRICH = _param(
    "enrich", "boolean", "activa o desactiva el enriquecimiento completo"
)
_USE_MEMORY = _param("use_memory", "boolean", "usa o no la memoria de la capa")
_USE_RAG = _param("use_rag", "boolean", "usa o no el conocimiento RAG")
_WRITE_BACK = _param(
    "write_back",
    "boolean",
    "persiste o no lo aprendido en la interaccion",
)
_AUTO_DOMAIN = _param(
    "auto_domain", "boolean", "resuelve el dominio con domain.route"
)


LOCAL_CAPABILITIES: tuple[Capability, ...] = (
    Capability(
        "capability.list",
        "lista el catalogo fusionado de la pila",
        False,
        False,
        (),
        None,
        _cli(
            "capability",
            "list",
            "Lista las capacidades propias y las obtenidas del core en ejecucion.",
        ),
        None,
        "overridden",
    ),
    Capability(
        "knowledge.confirm",
        "confirma un vinculo dominio-corpus",
        False,
        False,
        (
            _param(
                "corpus",
                "string",
                "nombre del corpus",
                required=True,
                metavar="CORPUS",
            ),
            _param(
                "domain",
                "string",
                "dominio del core",
                required=True,
                metavar="DOMINIO",
            ),
        ),
        None,
        _cli(
            "knowledge",
            "confirm",
            "Confirma un vinculo y habilita el gate de recuperacion.",
        ),
        None,
        "own",
    ),
    Capability(
        "knowledge.ingest",
        "ingiere texto curado en un corpus",
        False,
        False,
        (
            _param(
                "corpus",
                "string",
                "nombre del corpus",
                required=True,
                metavar="CORPUS",
            ),
            _param(
                "domain",
                "array",
                "dominio del core; se puede repetir",
                default=(),
                metavar="DOMINIO",
            ),
            _param(
                "source_ref",
                "string",
                "referencia de procedencia",
                metavar="REFERENCIA",
            ),
            _param(
                "path",
                "string",
                "ruta local con texto curado",
                required=True,
                metavar="RUTA",
                cli=False,
            ),
        ),
        None,
        _cli(
            "knowledge",
            "ingest",
            "Ingiere ficheros .txt/.md de una ruta local en un corpus.",
            inputs=(
                CliInput(
                    "path",
                    "path",
                    ("path",),
                    "RUTA",
                    "ruta local que se ingiere",
                ),
            ),
        ),
        None,
        "own",
    ),
    Capability(
        "knowledge.reject",
        "retira una propuesta de vinculo",
        False,
        False,
        (
            _param("corpus", "string", "nombre del corpus", required=True, metavar="CORPUS"),
            _param("domain", "string", "dominio del core", required=True, metavar="DOMINIO"),
        ),
        None,
        _cli("knowledge", "reject", "Retira una propuesta automatica no confirmada."),
        None,
        "own",
    ),
    Capability(
        "knowledge.status",
        "muestra la cobertura de conocimiento por dominio",
        False,
        False,
        (),
        None,
        _cli("knowledge", "status", "Compara los dominios del core con los corpus confirmados."),
        None,
        "own",
    ),
    Capability(
        "knowledge.suggest",
        "propone dominios para un corpus",
        False,
        False,
        (_param("corpus", "string", "nombre del corpus", required=True, metavar="CORPUS"),),
        None,
        _cli("knowledge", "suggest", "Propone vinculos via domain.route, sin confirmarlos."),
        None,
        "own",
    ),
    Capability(
        "memory.consolidate",
        "ejecuta un evento de consolidacion",
        False,
        False,
        (_param("event", "object", "evento de consolidacion", required=True, cli=False),),
        None,
        None,
        None,
        "own",
    ),
    Capability(
        "memory.maintain",
        "archiva y promociona memoria estricta por umbrales",
        False,
        False,
        (_param("dry_run", "boolean", "muestra el resumen sin mutar", default=False),),
        None,
        _cli(
            "memory",
            "maintain",
            "Barrido mecanico: archiva dialog y promociona episodic elegible. No necesita el core ni Ollama.",
        ),
        None,
        "own",
    ),
    Capability(
        "memory.recall",
        "recupera lo que se inyectaria sin ejecutar inferencia",
        True,
        False,
        (_PROMPT, _USE_MEMORY, _USE_RAG),
        None,
        _cli("memory", "recall", "Ejecuta memory.recall sin llamar a la inferencia del core."),
        None,
        "own",
    ),
    Capability(
        "memory.write",
        "escribe un engrama con autoridad por principal",
        True,
        False,
        (
            _param("principal", "string", "principal que solicita la escritura", required=True, choices=("extended", "conscience"), cli=False),
            _param("request", "object", "engrama que se desea escribir", required=True, cli=False),
        ),
        None,
        None,
        None,
        "own",
    ),
    Capability(
        "memory_type.list",
        "lista el roster de tipos de memoria",
        False,
        False,
        (),
        None,
        _cli("memory_type", "list", "Namespaces, tier, scopes y writer_principal declarados."),
        None,
        "own",
    ),
    Capability(
        "memory_type.validate",
        "valida una declaracion de tipo de memoria",
        False,
        False,
        (_param("memory_type", "object", "declaracion que se valida", required=True, cli=False),),
        None,
        None,
        None,
        "own",
    ),
    Capability(
        "prompt.run",
        "ejecuta un prompt enriquecido",
        True,
        False,
        (_PROMPT, _MODEL, _ENRICH, _USE_MEMORY, _USE_RAG, _WRITE_BACK, _DOMAIN, _AUTO_DOMAIN, _param("dry_run", "boolean", "compone sin llamar al core", default=False)),
        None,
        _cli(
            "prompt",
            "run",
            "Recupera contexto, compone dentro del presupuesto, llama al core y aplica write-back.",
            flags=("json", "show_context"),
            flag_help=(("json", "emite el resultado como JSON"), ("show_context", "imprime el bloque de contexto inyectado")),
        ),
        None,
        "overridden",
    ),
    Capability(
        "reasoning.run",
        "ejecuta razonamiento iterativo enriquecido",
        True,
        False,
        (_PROMPT, _MODEL, _ENRICH, _USE_MEMORY, _USE_RAG, _WRITE_BACK, _DOMAIN, _AUTO_DOMAIN, _param("dry_run", "boolean", "compone sin llamar al core", default=False)),
        None,
        _cli(
            "reasoning",
            "run",
            "Recupera contexto, llama a reasoning.run y aplica write-back.",
            flags=("json", "show_context"),
            flag_help=(("json", "emite el resultado como JSON"), ("show_context", "imprime el bloque de contexto inyectado")),
        ),
        None,
        "overridden",
    ),
    Capability(
        "task.run",
        "ejecuta una tarea enriquecida por subtarea",
        True,
        False,
        (
            _PROMPT,
            _param("effort", "string", "nivel de esfuerzo", choices=("low", "medium", "high"), metavar="NIVEL"),
            _ENRICH,
            _USE_MEMORY,
            _USE_RAG,
            _WRITE_BACK,
            _DOMAIN,
        ),
        None,
        _cli("task", "run", "Planifica en el core y enriquece cada subtarea por su dominio resuelto."),
        None,
        "overridden",
    ),
)


OVERRIDDEN_CAPABILITIES: tuple[str, ...] = tuple(
    item.name for item in LOCAL_CAPABILITIES if item.provenance == "overridden"
)
OWN_CAPABILITIES: tuple[str, ...] = tuple(
    item.name for item in LOCAL_CAPABILITIES if item.provenance == "own"
)


def local_catalog() -> list[dict[str, Any]]:
    """Serializa declaraciones locales con la misma forma publica del core."""
    return [asdict(capability) for capability in LOCAL_CAPABILITIES]


def extended_version() -> str:
    try:
        return version("ianest-extended")
    except PackageNotFoundError:
        return "0.0.0"


def _assert_catalog_invariants() -> None:
    names = tuple(item.name for item in LOCAL_CAPABILITIES)
    assert names == tuple(sorted(names))
    assert len(names) == len(set(names))
    assert "knowledge.retrieve" not in names
    assert "knowledge.corpus.list" not in names
    assert all(item.rest is None and item.mcp is None for item in LOCAL_CAPABILITIES)


_assert_catalog_invariants()
