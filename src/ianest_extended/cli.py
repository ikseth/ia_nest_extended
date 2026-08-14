"""Piel CLI de operador: gramatica GRUPO ACCION, calcada de la del core.

Esta piel es FINA: no conoce adaptadores ni clientes, solo el servicio. Toda la
logica vive en `ExtendedService`, de modo que REST y MCP (fase 7c) la compartan
sin divergir.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .capabilities import FORWARDED_CAPABILITIES
from .config import ExtendedConfig
from .errors import ExtendedError
from .identity import resolve_identity
from .service import ExtendedService

PROG = "ianest-extended"


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
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


# --- parser ---------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Ejecuta el contrato del ente enriquecido con memoria y "
            "conocimiento. Reenvia sin alterar lo que esta capa no enriquece."
        ),
        epilog=(
            f"Usa '{PROG} GRUPO --help' para ver sus acciones y "
            f"'{PROG} GRUPO ACCION --help' para ver todas sus opciones."
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

    prompt_group = group(
        "prompt",
        "ejecuta inferencias",
        "Ejecuta prompts contra el core, con o sin enriquecimiento.",
    )
    run_parser = prompt_group.add_parser(
        "run",
        help="ejecuta un prompt enriquecido",
        description=(
            "Sobreescritura de prompt.run: recupera contexto, compone dentro "
            "del presupuesto, llama al core y persiste el write-back. La forma "
            "de la respuesta es la del core."
        ),
    )
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

    memory_group = group(
        "memory",
        "capacidades propias de memoria",
        "Recuperacion y mantenimiento del sustrato de memoria de la capa.",
    )
    recall_parser = memory_group.add_parser(
        "recall",
        help="muestra lo que se inyectaria, sin ejecutar inferencia",
        description="Ejecuta memory.recall sin llamar a la inferencia del core.",
    )
    recall_parser.add_argument("--prompt", required=True, metavar="TEXTO")
    recall_parser.add_argument(
        "--use-memory",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    recall_parser.add_argument(
        "--use-rag",
        action=argparse.BooleanOptionalAction,
        default=None,
    )
    _add_identity_arguments(recall_parser)
    _add_json_argument(recall_parser)
    recall_parser.set_defaults(handler=_memory_recall)

    maintain_parser = memory_group.add_parser(
        "maintain",
        help="archiva y promociona memoria estricta por umbrales",
        description=(
            "Barrido mecanico: archiva dialog fuera de ventana y promociona "
            "episodic elegible. No necesita el core ni Ollama."
        ),
    )
    maintain_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="muestra el resumen sin mutar engramas ni lineage",
    )
    _add_json_argument(maintain_parser)
    maintain_parser.set_defaults(handler=_memory_maintain)

    memory_type_group = group(
        "memory_type",
        "registro de tipos de memoria",
        "Consulta el roster de tipos declarados por la capa.",
    )
    memory_type_list = memory_type_group.add_parser(
        "list",
        help="lista los tipos declarados",
        description="Namespaces, tier, scopes y writer_principal declarados.",
    )
    _add_json_argument(memory_type_list)
    memory_type_list.set_defaults(handler=_memory_type_list)

    knowledge_group = group(
        "knowledge",
        "conocimiento por dominio",
        "Ingesta curada y curacion de vinculos dominio-corpus.",
    )
    ingest_parser = knowledge_group.add_parser(
        "ingest",
        help="ingiere texto curado en un corpus",
        description="Ingiere ficheros .txt/.md de una ruta local en un corpus.",
    )
    ingest_parser.add_argument("--corpus", required=True)
    ingest_parser.add_argument(
        "--domain",
        action="append",
        default=[],
        help="dominio del core; se puede repetir",
    )
    ingest_parser.add_argument("--source-ref")
    ingest_parser.add_argument("path", type=Path)
    _add_json_argument(ingest_parser)
    ingest_parser.set_defaults(handler=_knowledge_ingest)

    status_parser = knowledge_group.add_parser(
        "status",
        help="cobertura de conocimiento por dominio",
        description="Compara los dominios del core con los corpus confirmados.",
    )
    _add_json_argument(status_parser)
    status_parser.set_defaults(handler=_knowledge_status)

    suggest_parser = knowledge_group.add_parser(
        "suggest",
        help="propone dominios para un corpus",
        description="Propone vinculos via domain.route, sin confirmarlos.",
    )
    suggest_parser.add_argument("--corpus", required=True)
    _add_json_argument(suggest_parser)
    suggest_parser.set_defaults(handler=_knowledge_suggest)

    confirm_parser = knowledge_group.add_parser(
        "confirm",
        help="confirma un vinculo dominio-corpus",
        description="Confirma un vinculo y habilita el gate de recuperacion.",
    )
    confirm_parser.add_argument("--corpus", required=True)
    confirm_parser.add_argument("--domain", required=True)
    _add_json_argument(confirm_parser)
    confirm_parser.set_defaults(handler=_knowledge_confirm)

    reject_parser = knowledge_group.add_parser(
        "reject",
        help="retira una propuesta de vinculo",
        description="Retira una propuesta automatica no confirmada.",
    )
    reject_parser.add_argument("--corpus", required=True)
    reject_parser.add_argument("--domain", required=True)
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

    _add_forwarded_commands(group)
    return parser


def _add_forwarded_commands(group) -> None:
    """Construye las acciones reenviadas a partir del dato declarado.

    INTERINO: la lista viene de `capabilities.py` porque el core aun no ofrece
    catalogo (`extended CR-0002`). El reenvio del servicio ya es generico.
    """
    summaries = {
        "prompt": ("ejecuta inferencias", "Ejecuta prompts contra el core."),
        "domain": ("dominios del core", "Reenvia las capacidades de dominio."),
        "model": ("modelos del core", "Reenvia el catalogo de modelos."),
        "runtime": (
            "operacion local de la capa",
            "Estado del runtime y migracion explicita del esquema local.",
        ),
        "config": (
            "configuracion del core",
            "Reenvia la validacion de configuracion.",
        ),
        "eval": ("evaluacion del core", "Reenvia la bateria de evaluacion."),
    }
    for capability in FORWARDED_CAPABILITIES:
        summary, description = summaries.get(
            capability.group,
            ("capacidad reenviada", "Capacidad reenviada al core sin alterar."),
        )
        actions = group(capability.group, summary, description)
        parser = actions.add_parser(
            capability.action,
            help=capability.summary,
            description=(
                f"Reenvia {capability.name} al core SIN alterar su respuesta. "
                "Esta capa no la enriquece en esta fase."
            ),
        )
        if capability.method != "GET":
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
        parser.set_defaults(handler=_forward, capability=capability)


def _add_enrichment_arguments(parser: argparse.ArgumentParser) -> None:
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
    for name, helptext in (
        ("use-memory", "usa o no la memoria de la capa"),
        ("use-rag", "usa o no el conocimiento RAG"),
        ("write-back", "persiste o no lo aprendido en la interaccion"),
        ("auto-domain", "resuelve el dominio con domain.route"),
    ):
        extension.add_argument(
            f"--{name}",
            action=argparse.BooleanOptionalAction,
            default=None,
            help=f"{helptext}; sin indicar, default de configuracion",
        )


def _add_identity_arguments(parser: argparse.ArgumentParser) -> None:
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
            "dominio unico: gatea el conocimiento, rutea el modelo y etiqueta "
            "la memoria"
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


def _forward(service, config, args) -> int:
    capability = args.capability
    payload = None
    if capability.method != "GET":
        payload = _forward_payload(config, args)
    result = service.forward(capability.name, payload, method=capability.method)
    if hasattr(result, "payload"):
        _print_json(result.payload, compact=args.json)
        return 0
    try:
        for event in result:
            if args.json:
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


def _identity(config, args):
    return resolve_identity(
        config,
        user_id=getattr(args, "user_id", None),
        session_id=getattr(args, "session_id", None),
        service=getattr(args, "service", None),
        namespace=getattr(args, "namespace", None),
        domain=getattr(args, "domain", None),
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
