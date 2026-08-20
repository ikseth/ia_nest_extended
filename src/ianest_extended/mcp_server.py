"""Piel MCP declarativa del contrato uniforme de ia_nest_extended.

MCP tiene que enumerar herramientas. Por eso esta piel se construye solo con
estado local: el catalogo propio y, si existe y pertenece al core configurado,
el catalogo ajeno cacheado. Arrancar nunca consulta al core.
"""

from __future__ import annotations

import argparse
import inspect
import json
from typing import Any, Literal

from .capabilities import local_catalog, merge_forwarded
from .catalog_cache import read_catalog_cache
from .clients import ForwardedJson, ForwardedStream
from .config import ExtendedConfig
from .errors import ExtendedError, ExtendedRequestError
from .service import ExtendedService


_TYPE_ANNOTATIONS: dict[str, Any] = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list[Any],
    "object": dict[str, Any],
}


class McpToolError(Exception):
    """Fallo de herramienta que conserva la forma tipada del ente."""

    def __init__(self, error: ExtendedError) -> None:
        self.payload = {"error": error.to_dict()}
        super().__init__(json.dumps(self.payload, ensure_ascii=True, sort_keys=True))


def create_server(
    config: ExtendedConfig | None = None,
    service: ExtendedService | None = None,
    *,
    host: str = "127.0.0.1",
    port: int = 8091,
):
    """Construye el servidor desde catalogos locales, sin tocar la red."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - depende del extra instalado
        raise RuntimeError(
            "MCP extra no instalado; instala ianest-extended[mcp]"
        ) from exc

    active_config = config or (
        service.config if service is not None else ExtendedConfig.from_env()
    )
    active_service = service or ExtendedService.from_config(active_config)
    catalog, cache_available = _startup_catalog(active_config)
    exposed, omitted = _mcp_exposures(catalog)
    instructions = _server_instructions(cache_available, omitted)
    server = FastMCP(
        "ia_nest_extended",
        instructions=instructions,
        host=host,
        port=port,
    )
    for capability in exposed:
        handler = _tool_handler(active_service, capability)
        server.add_tool(
            handler,
            name=capability["name"],
            description=str(capability.get("summary", "")),
            structured_output=True,
        )
    return server


def _startup_catalog(
    config: ExtendedConfig,
) -> tuple[list[dict[str, Any]], bool]:
    """Catalogo disponible al arrancar; esta funcion nunca consulta la red."""
    local = local_catalog()
    cached = read_catalog_cache(
        config.catalog_cache_path,
        core_url=config.core_url,
    )
    if cached is None:
        return local, False
    return merge_forwarded(local, cached["capabilities"]), True


def _mcp_exposures(
    catalog: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Separa herramientas bloqueantes de huecos MCP declarados."""
    exposed: list[dict[str, Any]] = []
    omitted: list[str] = []
    for capability in catalog:
        name = capability.get("name")
        if not isinstance(name, str):
            continue
        projection = capability.get("mcp")
        if capability.get("streaming") or not isinstance(projection, dict):
            omitted.append(name)
            continue
        # La proyeccion solo declara que MCP existe. El nombre de herramienta
        # es siempre el nombre canonico de capacidad, nunca el alias ajeno.
        exposed.append(capability)
    exposed.sort(key=lambda item: item["name"])
    return exposed, sorted(omitted)


def _server_instructions(cache_available: bool, omitted: list[str]) -> str:
    parts = [
        "Cada herramienta se llama exactamente como su capacidad. "
        "El streaming por MCP esta fuera de alcance; capability.list declara "
        "los huecos mediante una proyeccion MCP nula."
    ]
    if not cache_available:
        parts.append(
            "Catalogo ajeno no cacheado: este servidor enumera solo las "
            "capacidades propias y sobreescritas. capability.list declarara "
            "el hueco tipado si el core sigue inalcanzable."
        )
    if omitted:
        parts.append("No expuestas por MCP: " + ", ".join(omitted) + ".")
    return " ".join(parts)


def _tool_handler(service: ExtendedService, capability: dict[str, Any]):
    """Crea un handler fino y generico a partir de una declaracion."""
    name = capability["name"]
    parameters = _declared_parameters(capability)

    def handler(**kwargs: Any) -> dict[str, Any]:
        payload = _payload_with_defaults(parameters, kwargs)
        try:
            if capability.get("provenance") == "forwarded":
                method = _forward_method(capability)
                result = service.forward(name, payload or None, method=method)
                if isinstance(result, ForwardedStream):
                    result.close()
                    raise ExtendedRequestError(
                        f"'{name}' devolvio streaming, que MCP no expone",
                        "capability",
                    )
                if not isinstance(result, ForwardedJson):
                    raise ExtendedRequestError(
                        f"'{name}' no devolvio una respuesta JSON reenviable",
                        "capability",
                    )
                return result.payload
            return service.invoke(name, payload)
        except ExtendedError as exc:
            raise McpToolError(exc) from exc

    handler.__name__ = name.replace(".", "_")
    handler.__doc__ = str(capability.get("summary", ""))
    signature = _tool_signature(parameters)
    handler.__signature__ = signature
    handler.__annotations__ = {
        parameter.name: parameter.annotation
        for parameter in signature.parameters.values()
    }
    handler.__annotations__["return"] = dict[str, Any]
    return handler


def _declared_parameters(capability: dict[str, Any]) -> list[dict[str, Any]]:
    parameters = [
        dict(item)
        for item in capability.get("params", [])
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    names = {item["name"] for item in parameters}
    if capability.get("identity") and "identity" not in names:
        parameters.append(
            {
                "name": "identity",
                "type": "object",
                "required": False,
                "choices": None,
                "default": None,
                "summary": "contexto de identidad del request",
            }
        )
    return parameters


def _tool_signature(parameters: list[dict[str, Any]]) -> inspect.Signature:
    required: list[inspect.Parameter] = []
    optional: list[inspect.Parameter] = []
    for declaration in parameters:
        parameter = _signature_parameter(declaration)
        (required if declaration.get("required") else optional).append(parameter)
    return inspect.Signature(
        [*required, *optional],
        return_annotation=dict[str, Any],
    )


def _signature_parameter(declaration: dict[str, Any]) -> inspect.Parameter:
    name = declaration["name"]
    type_name = declaration.get("type")
    annotation = _TYPE_ANNOTATIONS.get(type_name, Any)
    choices = declaration.get("choices")
    if isinstance(choices, (list, tuple)) and choices:
        annotation = Literal.__getitem__(tuple(choices))
    is_required = bool(declaration.get("required"))
    if not is_required:
        annotation = annotation | None
    default = (
        inspect.Parameter.empty
        if is_required
        else declaration.get("default")
    )
    return inspect.Parameter(
        name,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        default=default,
        annotation=annotation,
    )


def _payload_with_defaults(
    parameters: list[dict[str, Any]],
    supplied: dict[str, Any],
) -> dict[str, Any]:
    payload = dict(supplied)
    for declaration in parameters:
        name = declaration["name"]
        if name in payload or declaration.get("required"):
            continue
        default = declaration.get("default")
        if default is not None:
            payload[name] = default
    return payload


def _forward_method(capability: dict[str, Any]) -> str | None:
    projection = capability.get("rest")
    if not isinstance(projection, dict):
        return None
    method = projection.get("method")
    return method if isinstance(method, str) else None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ianest-extended-mcp")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument("--env-file", default=".env", metavar="RUTA")
    args = parser.parse_args(argv)
    config = ExtendedConfig.from_env(env_file=args.env_file)
    create_server(config, host=args.host, port=args.port).run(
        transport=args.transport
    )


if __name__ == "__main__":
    main()
