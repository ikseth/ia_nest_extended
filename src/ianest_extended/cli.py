"""Piel CLI de operador: gramatica GRUPO ACCION, calcada de la del core.

Esta piel es FINA: no conoce adaptadores ni clientes, solo el servicio. Toda la
logica vive en `ExtendedService`, de modo que REST y MCP (fase 7c) la compartan
sin divergir.

Ninguna capacidad necesita ser CONOCIDA para poder invocarse (ADR 0011, punto
11): un `GRUPO ACCION` que esta piel no declara se resuelve como la capacidad
`grupo.accion` y se reenvia por el camino generico del servicio. Conocerla de
antemano solo sirve para ofrecer mejor ayuda, nunca para habilitarla.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .capabilities import CapabilityParam, LOCAL_CAPABILITIES, local_catalog, merge_forwarded
from .catalog_cache import read_catalog_cache
from .config import ExtendedConfig
from .errors import ExtendedError
from .identity import resolve_identity
from .service import ExtendedService

PROG = "ianest-extended"


def main(argv: list[str] | None = None) -> int:
    tokens = list(sys.argv[1:] if argv is None else argv)
    parser = _build_parser()
    if _is_general_help(tokens):
        parser = _build_general_help_parser(tokens)
    elif _first_positional(tokens) is not None:
        parser = _build_runtime_catalog_parser(tokens, parser)
    group = _first_positional(tokens)
    if group is not None:
        action = _second_positional(tokens, group)
        if group not in _group_names(parser) or (
            action is not None and action not in _action_names(parser, group)
        ):
            return _run_unknown_capability(group, tokens)
    args = parser.parse_args(tokens)
    if args.command is None:
        parser.print_help()
        return 2
    action = getattr(args, f"{args.command}_command", None)
    if action is None:
        _print_group_help(parser, args.command)
        return 2
    try:
        config = ExtendedConfig.from_env(env_file=args.env_file)
        service = ExtendedService.from_config(config)
        handler = args.handler
        return handler(service, config, args)
    except ExtendedError as exc:
        return _emit_error(exc, json_output=getattr(args, "json", False))


# --- capacidad no declarada por esta piel ---------------------------------


def _first_positional(tokens: list[str]) -> str | None:
    """Primer token posicional, saltando las opciones globales y sus valores."""
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token == "--":
            continue
        if token.startswith("-"):
            if token in ("-h", "--help"):
                # La ayuda pedida antes de cualquier posicional es la general.
                return None
            if token == "--env-file":
                skip_next = True
            continue
        return token
    return None


def _group_names(parser: argparse.ArgumentParser) -> set[str]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    return set()


def _action_names(parser: argparse.ArgumentParser, group: str) -> set[str]:
    for action in parser._actions:
        if not isinstance(action, argparse._SubParsersAction):
            continue
        group_parser = action.choices.get(group)
        if group_parser is None:
            return set()
        for nested in group_parser._actions:
            if isinstance(nested, argparse._SubParsersAction):
                return set(nested.choices)
    return set()


def _is_general_help(tokens: list[str]) -> bool:
    return not tokens or (
        _first_positional(tokens) is None
        and any(token in ("-h", "--help") for token in tokens)
    )


def _build_general_help_parser(tokens: list[str]) -> argparse.ArgumentParser:
    """Enriquece solo la ayuda general; construir el parser sigue siendo local."""
    env_file = _env_file_from_tokens(tokens)
    try:
        config = ExtendedConfig.from_env(env_file=env_file)
        catalog = _cached_catalog(config)
    except (ExtendedError, AttributeError):
        catalog = None
    return _build_parser(catalog=catalog)


def _build_runtime_catalog_parser(
    tokens: list[str], fallback: argparse.ArgumentParser
) -> argparse.ArgumentParser:
    """Anade la declaracion ajena SI esta cacheada; invocar no depende de ella.

    Construir el parser es una operacion puramente local (defecto 2 del
    retrabajo de herencia de parametros): nunca consulta al core. Sin cache
    -o con una cache de otro core- esta capa degrada a `fallback`, que ya
    conserva las banderas propias y resuelve lo ajeno por `--param`.
    """
    try:
        config = ExtendedConfig.from_env(env_file=_env_file_from_tokens(tokens))
        catalog = _cached_catalog(config)
    except (ExtendedError, AttributeError):
        return fallback
    if catalog is None:
        return fallback
    return _build_parser(catalog=catalog)


def _cached_catalog(config: ExtendedConfig) -> list[dict[str, Any]] | None:
    """Catalogo fusionado desde la cache local del catalogo remoto.

    `None` si no hay cache o si es de un core distinto del configurado: en
    ambos casos quien llama degrada como si no existiera, nunca falla.
    """
    cached = read_catalog_cache(config.catalog_cache_path, core_url=config.core_url)
    if cached is None:
        return None
    return merge_forwarded(local_catalog(), cached["capabilities"])


def _env_file_from_tokens(tokens: list[str]) -> str:
    env_file = ".env"
    for index, token in enumerate(tokens):
        if token == "--env-file" and index + 1 < len(tokens):
            env_file = tokens[index + 1]
        elif token.startswith("--env-file="):
            env_file = token.partition("=")[2]
    return env_file


def _run_unknown_capability(group: str, tokens: list[str]) -> int:
    """Resuelve `GRUPO ACCION` desconocidos como capacidad reenviada.

    Mismas banderas de cuerpo, misma regla de verbo (sin cuerpo, GET; con
    cuerpo, POST), mismo tratamiento de streaming, `--json` y codigos de salida
    que el reenvio de las capacidades declaradas. No se inventan rutas: la
    capacidad es literalmente `grupo.accion`, y si el core no la sirve, su error
    llega tal cual.
    """
    action = _second_positional(tokens, group)
    if action is None:
        return _emit_error(
            ExtendedError(
                f"'{group}' no es un grupo de esta capa; para invocar una "
                "capacidad del core hace falta GRUPO ACCION",
                "capability",
            ),
            json_output="--json" in tokens,
        )
    name = f"{group}.{action}"
    parser = _build_unknown_capability_parser(group, action)
    remaining = _without(tokens, group, action)
    args = parser.parse_args(remaining)
    try:
        config = ExtendedConfig.from_env(env_file=args.env_file)
        service = ExtendedService.from_config(config)
        payload = _declared_payload(config, args)
        result = service.forward(name, payload)
        return _emit_forward(result, args.json)
    except ExtendedError as exc:
        return _emit_error(exc, json_output=args.json)


def _second_positional(tokens: list[str], group: str) -> str | None:
    remaining = _tokens_after_group(tokens, group)
    return _first_positional(remaining)


def _tokens_after_group(tokens: list[str], group: str) -> list[str]:
    index = tokens.index(group)
    return tokens[index + 1 :]


def _without(tokens: list[str], group: str, action: str) -> list[str]:
    index = tokens.index(group)
    rest = tokens[index + 1 :]
    action_index = rest.index(action)
    return tokens[:index] + rest[:action_index] + rest[action_index + 1 :]


def _build_unknown_capability_parser(
    group: str,
    action: str,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=f"{PROG} {group} {action}",
        description=(
            f"Reenvia la capacidad '{group}.{action}' al core SIN alterar su "
            "respuesta. Esta piel no la declara: se resuelve por el camino "
            "generico, de modo que una capacidad nueva del core es invocable "
            "sin editar esta capa."
        ),
        epilog=(
            "Sin cuerpo declarado la peticion es GET; con cuerpo, POST. El "
            "cuerpo se declara con --prompt, --param y --payload."
        ),
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        metavar="RUTA",
        help="fichero de entorno de la capa (por defecto: %(default)s)",
    )
    parser.add_argument("--prompt", metavar="TEXTO")
    parser.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="CLAVE=VALOR",
        help="campo del cuerpo reenviado; se puede repetir",
    )
    parser.add_argument(
        "--payload",
        metavar="JSON",
        help="cuerpo completo reenviado, como objeto JSON",
    )
    _add_identity_arguments(parser)
    _add_json_argument(parser)
    return parser


def _declared_payload(config, args) -> dict[str, Any] | None:
    """Cuerpo solo si el operador declaro alguno; si no, peticion sin cuerpo."""
    if args.prompt is None and not args.param and not args.payload:
        return None
    return _forward_payload(config, args)


# --- parser ---------------------------------------------------------------


def _build_parser(
    *,
    catalog: list[dict[str, Any]] | None = None,
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Ejecuta el contrato del ente enriquecido con memoria y "
            "conocimiento. Reenvia sin alterar lo que esta capa no enriquece."
        ),
        epilog=(
            f"Usa '{PROG} GRUPO --help' para ver sus acciones y "
            f"'{PROG} GRUPO ACCION --help' para ver todas sus opciones. "
            "CUALQUIER capacidad del core es invocable como GRUPO ACCION "
            "aunque no aparezca en esta lista: los grupos listados solo son "
            "los que esta capa conoce lo bastante para documentarlos."
        ),
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        metavar="RUTA",
        help="fichero de entorno de la capa (por defecto: %(default)s)",
    )
    groups: dict[str, argparse._SubParsersAction] = {}
    subparsers = parser.add_subparsers(
        dest="command",
        title="grupos",
        metavar="GRUPO",
    )

    def group(name: str, summary: str, description: str):
        if name not in groups:
            group_parser = subparsers.add_parser(
                name,
                help=summary,
                description=description,
            )
            groups[name] = group_parser.add_subparsers(
                dest=f"{name}_command",
                title="acciones",
                metavar="ACCION",
            )
        return groups[name]

    capability_group = group(
        "capability",
        "consulta las capacidades de la pila",
        "Consulta el catalogo local y el obtenido del core en ejecucion.",
    )
    capability_list = _add_local_parser(capability_group, "capability.list")
    _add_json_argument(capability_list)
    capability_list.set_defaults(handler=_capability_list)

    prompt_group = group(
        "prompt",
        "ejecuta inferencias",
        "Ejecuta prompts contra el core, con o sin enriquecimiento.",
    )
    run_parser = _add_local_parser(prompt_group, "prompt.run")
    run_parser.add_argument("--prompt", required=True, metavar="TEXTO")
    run_parser.add_argument("--model", metavar="MODELO")
    _add_enrichment_arguments(run_parser)
    run_parser.add_argument(
        "--show-context",
        action="store_true",
        help="imprime el bloque de contexto inyectado",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="compone e imprime el prompt enriquecido sin llamar al core",
    )
    _add_identity_arguments(run_parser)
    _add_json_argument(run_parser)
    run_parser.set_defaults(handler=_prompt_run)

    reasoning_group = group(
        "reasoning",
        "ejecuta razonamiento iterativo",
        "Ejecuta reasoning.run con el mismo enriquecimiento upfront que prompt.run.",
    )
    reasoning_run = _add_local_parser(reasoning_group, "reasoning.run")
    reasoning_run.add_argument("--prompt", required=True, metavar="TEXTO")
    reasoning_run.add_argument("--model", metavar="MODELO")
    _add_enrichment_arguments(reasoning_run)
    reasoning_run.add_argument(
        "--show-context",
        action="store_true",
        help="imprime el bloque de contexto inyectado",
    )
    reasoning_run.add_argument(
        "--dry-run",
        action="store_true",
        help="compone e imprime el prompt enriquecido sin llamar al core",
    )
    _add_identity_arguments(reasoning_run)
    _add_json_argument(reasoning_run)
    reasoning_run.set_defaults(handler=_reasoning_run)

    task_group = group(
        "task",
        "ejecuta tareas orquestadas",
        "Planifica en el core y enriquece cada subtarea por su dominio resuelto.",
    )
    task_run = _add_local_parser(task_group, "task.run")
    _add_local_parameter(task_run, "task.run", "prompt")
    _add_local_parameter(task_run, "task.run", "effort")
    _add_cli_inputs(task_run, _local_capability("task.run").cli.inputs)
    _add_enrichment_arguments(task_run, include_auto_domain=False)
    _add_identity_arguments(task_run, task_domain=True)
    _add_json_argument(task_run)
    task_run.set_defaults(handler=_task_run)

    memory_group = group(
        "memory",
        "capacidades propias de memoria",
        "Recuperacion y mantenimiento del sustrato de memoria de la capa.",
    )
    recall_parser = _add_local_parser(memory_group, "memory.recall")
    _add_local_parameter(recall_parser, "memory.recall", "prompt")
    _add_local_parameter(recall_parser, "memory.recall", "use_memory")
    _add_local_parameter(recall_parser, "memory.recall", "use_rag")
    _add_identity_arguments(recall_parser)
    _add_json_argument(recall_parser)
    recall_parser.set_defaults(handler=_memory_recall)

    maintain_parser = _add_local_parser(memory_group, "memory.maintain")
    _add_local_parameter(maintain_parser, "memory.maintain", "dry_run")
    _add_json_argument(maintain_parser)
    maintain_parser.set_defaults(handler=_memory_maintain)

    memory_type_group = group(
        "memory_type",
        "registro de tipos de memoria",
        "Consulta el roster de tipos declarados por la capa.",
    )
    memory_type_list = _add_local_parser(
        memory_type_group, "memory_type.list"
    )
    _add_json_argument(memory_type_list)
    memory_type_list.set_defaults(handler=_memory_type_list)

    knowledge_group = group(
        "knowledge",
        "conocimiento por dominio",
        "Ingesta curada y curacion de vinculos dominio-corpus.",
    )
    ingest_parser = _add_local_parser(knowledge_group, "knowledge.ingest")
    _add_local_parameter(ingest_parser, "knowledge.ingest", "corpus")
    _add_local_parameter(ingest_parser, "knowledge.ingest", "domain")
    _add_local_parameter(ingest_parser, "knowledge.ingest", "source_ref")
    ingest_parser.add_argument("path", type=Path)
    _add_json_argument(ingest_parser)
    ingest_parser.set_defaults(handler=_knowledge_ingest)

    status_parser = _add_local_parser(knowledge_group, "knowledge.status")
    _add_json_argument(status_parser)
    status_parser.set_defaults(handler=_knowledge_status)

    suggest_parser = _add_local_parser(knowledge_group, "knowledge.suggest")
    _add_local_parameter(suggest_parser, "knowledge.suggest", "corpus")
    _add_json_argument(suggest_parser)
    suggest_parser.set_defaults(handler=_knowledge_suggest)

    confirm_parser = _add_local_parser(knowledge_group, "knowledge.confirm")
    _add_local_parameter(confirm_parser, "knowledge.confirm", "corpus")
    _add_local_parameter(confirm_parser, "knowledge.confirm", "domain")
    _add_json_argument(confirm_parser)
    confirm_parser.set_defaults(handler=_knowledge_confirm)

    reject_parser = _add_local_parser(knowledge_group, "knowledge.reject")
    _add_local_parameter(reject_parser, "knowledge.reject", "corpus")
    _add_local_parameter(reject_parser, "knowledge.reject", "domain")
    _add_json_argument(reject_parser)
    reject_parser.set_defaults(handler=_knowledge_reject)

    runtime_group = group(
        "runtime",
        "operacion local de la capa",
        "Estado del runtime y migracion explicita del esquema local.",
    )
    migrate_parser = runtime_group.add_parser(
        "migrate",
        help="migra el esquema local de la capa",
        description=(
            "Unico comando que muta el esquema. El resto lo VERIFICA y falla "
            "si falta migrar."
        ),
    )
    _add_json_argument(migrate_parser)
    migrate_parser.set_defaults(handler=_runtime_migrate)

    if catalog is not None:
        _add_catalog_help(group, catalog)
    return parser


def _add_local_parser(actions, name: str) -> argparse.ArgumentParser:
    capability = _local_capability(name)
    projection = capability.cli
    assert projection is not None and projection.action is not None
    return actions.add_parser(
        projection.action,
        help=capability.summary,
        description=projection.description,
        epilog=projection.epilog,
    )


def _local_capability(name: str):
    return next(item for item in LOCAL_CAPABILITIES if item.name == name)


def _add_local_parameter(
    parser: argparse.ArgumentParser,
    capability_name: str,
    parameter_name: str,
) -> None:
    capability = _local_capability(capability_name)
    parameter = next(
        item for item in capability.params if item.name == parameter_name
    )
    _add_catalog_parameter(parser, parameter)


def _option_registered(parser: argparse.ArgumentParser, option: str) -> bool:
    return option in parser._option_string_actions


def _add_catalog_parameter(
    parser, parameter: CapabilityParam | dict[str, Any], *, suppress_default: bool = False
) -> bool:
    """Construye una bandera desde una declaracion, sin conocer capacidades.

    Regla de colision, UNA sola y derivada del dato (no una lista de casos):
    si el parser YA tiene esa bandera -porque la capa la posee de antemano,
    identidad, enriquecimiento o salida-, la bandera propia gana y el
    parametro del catalogo no se vuelve a declarar. Devuelve `False` en ese
    caso para que quien llama pueda explicarlo en la ayuda; `True` si se
    anadio.
    """
    value = _catalog_value(parameter, "name")
    assert isinstance(value, str)
    option = f"--{value.replace('_', '-')}"
    if _option_registered(parser, option):
        return False
    kwargs: dict[str, Any] = {
        "required": bool(_catalog_value(parameter, "required", False)),
        "help": str(_catalog_value(parameter, "summary", "")),
    }
    metavar = _catalog_value(parameter, "metavar")
    if isinstance(metavar, str):
        kwargs["metavar"] = metavar
    choices = _catalog_value(parameter, "choices")
    if choices is not None:
        kwargs["choices"] = choices
    param_type = _catalog_value(parameter, "type")
    default = _catalog_value(parameter, "default")
    if param_type == "boolean":
        kwargs["action"] = (
            "store_true"
            if default is False
            else argparse.BooleanOptionalAction
        )
        kwargs["default"] = argparse.SUPPRESS if suppress_default else default
    elif param_type == "array":
        kwargs["action"] = "append"
        kwargs["default"] = argparse.SUPPRESS if suppress_default else list(default or ())
    elif param_type == "integer":
        kwargs["type"] = int
        kwargs["default"] = argparse.SUPPRESS if suppress_default else default
    else:
        kwargs["default"] = argparse.SUPPRESS if suppress_default else default
    parser.add_argument(option, **kwargs)
    return True


def _catalog_value(item, name: str, default=None):
    return getattr(item, name, item.get(name, default) if isinstance(item, dict) else default)


def _add_cli_inputs(parser, inputs) -> None:
    """Misma regla de colision que `_add_catalog_parameter`, para entradas."""
    for input_spec in inputs:
        name = _catalog_value(input_spec, "name")
        if not isinstance(name, str):
            continue
        option = f"--{name.replace('_', '-')}"
        if _option_registered(parser, option):
            continue
        parser.add_argument(
            option,
            dest=name,
            metavar=_catalog_value(input_spec, "metavar"),
            help=_catalog_value(input_spec, "summary", ""),
        )


def _add_catalog_help(group, catalog: list[dict[str, Any]]) -> None:
    """Anade ayuda ajena usando solo los campos conocidos de la proyeccion.

    Las banderas propias de la capa -identidad, `--param` y `--json`- se
    declaran ANTES de recorrer los parametros del catalogo, para que la
    regla de colision (`_add_catalog_parameter`) las encuentre ya puestas y
    ceda ante ellas en lugar de intentar redeclararlas.
    """
    for capability in catalog:
        if capability.get("provenance") != "forwarded":
            continue
        projection = capability.get("cli")
        if not isinstance(projection, dict):
            continue
        group_name = projection.get("group")
        action = projection.get("action")
        if not isinstance(group_name, str) or not isinstance(action, str):
            continue
        actions = group(
            group_name,
            "capacidades obtenidas del core",
            "Ayuda obtenida del catalogo del core en ejecucion.",
        )
        if action in actions.choices:
            continue
        parser = actions.add_parser(
            action,
            help=str(capability.get("summary", "capacidad reenviada")),
            description=str(
                projection.get("description", "Capacidad reenviada al core.")
            ),
            epilog=projection.get("epilog"),
        )
        parser.add_argument(
            "--param",
            action="append",
            default=[],
            metavar="CLAVE=VALOR",
            help="campo no declarado del cuerpo reenviado; se puede repetir",
        )
        _add_identity_arguments(parser)
        _add_json_argument(parser)
        governed: list[str] = []
        for parameter in capability.get("params", []):
            if not isinstance(parameter, dict) or parameter.get("cli") is False:
                continue
            name = parameter.get("name")
            if _add_catalog_parameter(parser, parameter, suppress_default=True):
                continue
            if isinstance(name, str):
                governed.append(name)
        _add_cli_inputs(parser, projection.get("inputs", ()))
        if governed:
            note = (
                "Parametros que gobierna la bandera propia de la capa, no "
                "el catalogo: " + ", ".join(f"--{n.replace('_', '-')}" for n in sorted(governed))
            )
            parser.epilog = f"{parser.epilog}\n\n{note}" if parser.epilog else note
        parser.set_defaults(
            handler=_catalog_forward,
            catalog_capability=capability,
        )


def _add_enrichment_arguments(
    parser: argparse.ArgumentParser,
    *,
    include_auto_domain: bool = True,
) -> None:
    extension = parser.add_argument_group("parametros de enriquecimiento")
    extension.add_argument(
        "--enrich",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "activa o desactiva el enriquecimiento completo; sin indicar, "
            "toma el default de configuracion"
        ),
    )
    switches = [
        ("use-memory", "usa o no la memoria de la capa"),
        ("use-rag", "usa o no el conocimiento RAG"),
        ("write-back", "persiste o no lo aprendido en la interaccion"),
    ]
    if include_auto_domain:
        switches.append(("auto-domain", "resuelve el dominio con domain.route"))
    for name, helptext in switches:
        extension.add_argument(
            f"--{name}",
            action=argparse.BooleanOptionalAction,
            default=None,
            help=f"{helptext}; sin indicar, default de configuracion",
        )


def _add_identity_arguments(
    parser: argparse.ArgumentParser,
    *,
    task_domain: bool = False,
) -> None:
    identity = parser.add_argument_group("identidad del request")
    identity.add_argument(
        "--user-id",
        metavar="ID",
        help="identificador de usuario; por defecto, el configurado",
    )
    identity.add_argument(
        "--service",
        metavar="SERVICIO",
        help="servicio de origen; por defecto, el configurado",
    )
    identity.add_argument(
        "--session-id",
        metavar="ID",
        help="continuidad de sesion; sin indicar, se recuerda la persistida",
    )
    identity.add_argument(
        "--namespace",
        metavar="ESPACIO",
        help="espacio de identidad incluido en la traza",
    )
    identity.add_argument(
        "--domain",
        metavar="DOMINIO",
        help=(
            "faceta de lectura de memoria; no se envia al core como dominio "
            "de tarea"
            if task_domain
            else "dominio unico: gatea el conocimiento, rutea el modelo y "
            "etiqueta la memoria"
        ),
    )


def _add_json_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="emite el resultado como JSON",
    )


def _print_group_help(parser: argparse.ArgumentParser, command: str) -> None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            group_parser = action.choices.get(command)
            if group_parser is not None:
                group_parser.print_help()
                return
    parser.print_help()


# --- handlers -------------------------------------------------------------


def _capability_list(service, config, args) -> int:
    payload = service.capability_list()
    lines = [
        f"{item.get('name', '(sin nombre)')} "
        f"[{item.get('provenance', 'forwarded')}]"
        for item in payload["capabilities"]
    ]
    if payload.get("error") is not None:
        error = payload["error"]
        lines.append(
            f"catalogo inferior no disponible: {error['type']}: "
            f"{error['message']}"
        )
    return _emit(payload, args.json, text="\n".join(lines))


def _prompt_run(service, config, args) -> int:
    identity = _identity(config, args)
    result = service.prompt_run(
        args.prompt,
        identity,
        enrich=args.enrich,
        use_memory=args.use_memory,
        use_rag=args.use_rag,
        write_back=args.write_back,
        domain=getattr(args, "domain", None),
        auto_domain=args.auto_domain,
        model=args.model,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        payload = {
            "request_id": result.request_id,
            "enriched_prompt": result.enriched_prompt,
            "context": result.context,
            "dry_run": True,
        }
        return _emit(payload, args.json, text=result.enriched_prompt)
    if args.json:
        _print_json(result.payload)
        return 0
    if args.show_context:
        print(result.context or "(sin contexto recuperado)")
        print()
    print(result.response)
    return 0


def _reasoning_run(service, config, args) -> int:
    result = service.reasoning_run(
        args.prompt,
        _identity(config, args),
        enrich=args.enrich,
        use_memory=args.use_memory,
        use_rag=args.use_rag,
        write_back=args.write_back,
        domain=getattr(args, "domain", None),
        auto_domain=args.auto_domain,
        model=args.model,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        payload = {
            "request_id": result.request_id,
            "enriched_prompt": result.enriched_prompt,
            "context": result.context,
            "dry_run": True,
        }
        return _emit(payload, args.json, text=result.enriched_prompt)
    if args.json:
        _print_json(result.payload)
        return 0
    if args.show_context:
        print(result.context or "(sin contexto recuperado)")
        print()
    print(result.output)
    return 0


def _task_run(service, config, args) -> int:
    plan_payload = _input_payload(args, _local_capability("task.run"))
    if plan_payload is not None and args.effort is not None:
        raise ExtendedError(
            "--plan-file y --effort rellenan ambos 'effort'",
            "effort",
        )
    result = service.task_run(
        args.prompt,
        _identity(config, args, include_domain=False),
        enrich=args.enrich,
        use_memory=args.use_memory,
        use_rag=args.use_rag,
        write_back=args.write_back,
        domain=getattr(args, "domain", None),
        effort=args.effort,
        plan_payload=plan_payload,
    )
    if args.json:
        _print_json(result.payload)
    else:
        print(result.response)
    return 0


def _catalog_forward(service, config, args) -> int:
    """Reenvio de una declaracion descubierta, construido solo del catalogo."""
    capability = args.catalog_capability
    payload = _catalog_payload(config, args, capability)
    return _emit_forward(service.forward(capability["name"], payload), args.json)


def _catalog_payload(config, args, capability: dict[str, Any]) -> dict[str, Any] | None:
    params = {
        item["name"]
        for item in capability.get("params", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }
    payload = _input_payload(args, capability) or {}
    for parameter in capability.get("params", []):
        if not isinstance(parameter, dict) or parameter.get("cli") is False:
            continue
        name = parameter.get("name")
        if not isinstance(name, str):
            continue
        if hasattr(args, name):
            value = getattr(args, name)
            if name in payload:
                raise ExtendedError(
                    f"entrada de fichero y bandera rellenan ambos '{name}'", name
                )
            if value is not None:
                payload[name] = value
        elif parameter.get("default") is not None:
            payload[name] = parameter["default"]
    for item in args.param:
        key, separator, raw = item.partition("=")
        if not separator or not key.strip():
            raise ExtendedError(f"--param espera CLAVE=VALOR; recibido '{item}'", "param")
        key = key.strip()
        if key in params:
            raise ExtendedError(
                f"--param no puede rellenar el parametro declarado '{key}'",
                key,
            )
        try:
            payload[key] = json.loads(raw)
        except json.JSONDecodeError:
            payload[key] = raw
    if capability.get("identity") and "identity" not in payload:
        payload["identity"] = _identity(config, args).to_core_dict()
    return payload or None


def _input_payload(args, capability) -> dict[str, Any] | None:
    """Lee entradas declaradas y reparte su JSON; las colisiones son errores."""
    projection = _catalog_value(capability, "cli")
    if projection is None:
        return None
    payload: dict[str, Any] = {}
    used = False
    for input_spec in _catalog_value(projection, "inputs", ()):
        input_name = _catalog_value(input_spec, "name")
        if not isinstance(input_name, str):
            continue
        path = getattr(args, input_name, None)
        if path is None:
            continue
        used = True
        if _catalog_value(input_spec, "source") != "json_file":
            raise ExtendedError("entrada CLI no soportada", input_name)
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            raise ExtendedError(f"no se pudo leer '{path}': {exc}", input_name)
        except json.JSONDecodeError as exc:
            raise ExtendedError(f"'{path}' no contiene JSON valido: {exc}", input_name)
        if not isinstance(document, dict):
            raise ExtendedError("la entrada JSON debe ser un objeto", input_name)
        targets = _catalog_value(input_spec, "targets", ())
        for target in targets:
            if target not in document:
                raise ExtendedError(
                    f"la entrada '{input_name}' no contiene '{target}'",
                    input_name,
                )
            if target in payload:
                raise ExtendedError(
                    f"dos entradas CLI rellenan '{target}'",
                    target,
                )
            payload[target] = document[target]
    return payload if used else None


def _memory_recall(service, config, args) -> int:
    payload = service.memory_recall(
        _identity(config, args),
        args.prompt,
        use_memory=args.use_memory,
        use_rag=args.use_rag,
    )
    return _emit(
        payload,
        args.json,
        text=payload["context"] or "(sin contexto recuperado)",
    )


def _memory_maintain(service, config, args) -> int:
    payload = service.memory_maintain(dry_run=args.dry_run)
    text = (
        "dialog_archived={dialog_archived} "
        "episodic_promoted={episodic_promoted} "
        "candidates_seen={candidates_seen} dry_run={dry_run}"
    ).format(**{**payload, "dry_run": str(payload["dry_run"]).lower()})
    return _emit(payload, args.json, text=text)


def _memory_type_list(service, config, args) -> int:
    payload = service.memory_type_list()
    lines = [
        "name={name} class={memory_class} writer={writer_principal} "
        "mode={retrieval_mode} scope={scope} namespaces={namespaces}".format(
            **{**item, "namespaces": ",".join(item["namespaces"]) or "(ninguno)"}
        )
        for item in payload["types"]
    ]
    return _emit(payload, args.json, text="\n".join(lines))


def _knowledge_ingest(service, config, args) -> int:
    payload = service.knowledge_ingest(
        path=args.path,
        corpus_name=args.corpus,
        domains=tuple(args.domain),
        source_ref=args.source_ref,
    )
    text = (
        f"corpus={payload['corpus_name']} "
        f"domains={','.join(payload['domains']) or '(global)'} "
        f"chunks_new={payload['chunks_new']} "
        f"chunks_updated={payload['chunks_updated']}"
    )
    return _emit(payload, args.json, text=text)


def _knowledge_status(service, config, args) -> int:
    payload = service.knowledge_status()
    lines = [
        "domain={domain} confirmed_corpora={confirmed_corpora} status={label}".format(
            **item,
            label="OK" if item["confirmed_corpora"] else "HUECO",
        )
        for item in payload["domains"]
    ]
    return _emit(payload, args.json, text="\n".join(lines))


def _knowledge_suggest(service, config, args) -> int:
    payload = service.knowledge_suggest(args.corpus)
    if not payload["suggestions"]:
        text = f"corpus={args.corpus} proposals=0"
    else:
        text = "\n".join(
            f"corpus={args.corpus} domain={item['domain']} "
            f"confidence={item['confidence']:.3f} "
            f"proposal={'stored' if item['stored'] else 'protected'}"
            for item in payload["suggestions"]
        )
    return _emit(payload, args.json, text=text)


def _knowledge_confirm(service, config, args) -> int:
    payload = service.knowledge_confirm(args.corpus, args.domain)
    text = (
        f"corpus={args.corpus} domain={args.domain} "
        f"confirmed={'yes' if payload['confirmed'] else 'already'}"
    )
    return _emit(payload, args.json, text=text)


def _knowledge_reject(service, config, args) -> int:
    payload = service.knowledge_reject(args.corpus, args.domain)
    text = (
        f"corpus={args.corpus} domain={args.domain} "
        f"rejected={'yes' if payload['rejected'] else 'absent'}"
    )
    return _emit(payload, args.json, text=text)


def _runtime_migrate(service, config, args) -> int:
    payload = service.runtime_migrate()
    text = " ".join(f"{key}={value}" for key, value in payload.items())
    return _emit(payload, args.json, text=text)


def _emit_forward(result, json_output: bool) -> int:
    """Salida del reenvio: JSON opaco o retransmision evento a evento."""
    if hasattr(result, "payload"):
        _print_json(result.payload, compact=json_output)
        return 0
    try:
        for event in result:
            if json_output:
                _print_json(
                    {"event": event.event, "data": event.data},
                    compact=True,
                )
            else:
                print(event.data, flush=True)
    finally:
        result.close()
    return 0


def _forward_payload(config, args) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if getattr(args, "payload", None):
        try:
            declared = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            raise ExtendedError(f"--payload no es JSON valido: {exc}", "payload")
        if not isinstance(declared, dict):
            raise ExtendedError("--payload debe ser un objeto JSON", "payload")
        payload.update(declared)
    for item in getattr(args, "param", []):
        key, separator, raw = item.partition("=")
        if not separator or not key.strip():
            raise ExtendedError(
                f"--param espera CLAVE=VALOR; recibido '{item}'",
                "param",
            )
        try:
            payload[key.strip()] = json.loads(raw)
        except json.JSONDecodeError:
            payload[key.strip()] = raw
    if getattr(args, "prompt", None) is not None:
        payload["prompt"] = args.prompt
    if "identity" not in payload:
        payload["identity"] = _identity(config, args).to_core_dict()
    return payload


def _identity(config, args, *, include_domain: bool = True):
    return resolve_identity(
        config,
        user_id=getattr(args, "user_id", None),
        session_id=getattr(args, "session_id", None),
        service=getattr(args, "service", None),
        namespace=getattr(args, "namespace", None),
        domain=getattr(args, "domain", None) if include_domain else None,
    )


# --- salida ---------------------------------------------------------------


def _emit(payload: dict[str, Any], json_output: bool, *, text: str) -> int:
    if json_output:
        _print_json(payload, compact=True)
    elif text:
        print(text)
    return 0


def _print_json(payload: Any, *, compact: bool = False) -> None:
    if compact:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _emit_error(exc: ExtendedError, *, json_output: bool) -> int:
    if json_output:
        print(
            json.dumps(
                {"error": exc.to_dict()},
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
    else:
        field = f" ({exc.field})" if exc.field else ""
        print(f"{exc.type}{field}: {exc.message}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
