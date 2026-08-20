"""Piel REST fina del contrato uniforme de ia_nest_extended.

Las capacidades locales llaman a :class:`ExtendedService`. Cualquier otra ruta
se reenvia al core derivando la capacidad de la propia ruta, sin consultar el
catalogo fusionado ni su cache.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from .capabilities import LOCAL_CAPABILITIES
from .clients import ForwardedJson, ForwardedStream
from .config import ExtendedConfig
from .errors import DownstreamError, ExtendedError, ExtendedRequestError
from .service import ExtendedService


def create_app(
    config: ExtendedConfig | None = None,
    service: ExtendedService | None = None,
):
    """Construye la aplicacion sin tocar el core ni el catalogo remoto."""
    try:
        from starlette.applications import Starlette
        from starlette.requests import Request
        from starlette.responses import JSONResponse, Response, StreamingResponse
        from starlette.routing import Route
    except ImportError as exc:  # pragma: no cover - depende del extra instalado
        raise RuntimeError(
            "REST extra no instalado; instala ianest-extended[rest]"
        ) from exc

    active_config = config or ExtendedConfig.from_env()
    active_service = service or ExtendedService.from_config(active_config)
    local_paths = {
        capability.rest.path: capability
        for capability in LOCAL_CAPABILITIES
        if capability.rest is not None
    }

    def local_endpoint(capability_name: str, expected_method: str):
        async def endpoint(request: Request):
            if request.method != expected_method:
                return Response(status_code=405, headers={"allow": expected_method})
            payload = await _request_payload(request)
            return JSONResponse(active_service.invoke(capability_name, payload))

        return endpoint

    async def forward_route(request: Request):
        path = request.url.path
        if path in local_paths:
            expected = local_paths[path].rest.method
            return Response(status_code=405, headers={"allow": expected})
        route = path
        if request.url.query:
            route = f"{route}?{request.url.query}"
        payload = await _request_payload(request)
        result = active_service.forward(route, payload, method=request.method)
        return _forwarded_response(result)

    async def extended_error_handler(request: Request, exc: ExtendedError):
        status_code = exc.status_code if isinstance(exc, DownstreamError) else 400
        return JSONResponse({"error": exc.to_dict()}, status_code=status_code)

    routes = [
        Route(
            capability.rest.path,
            local_endpoint(capability.name, capability.rest.method),
            methods=["GET", "POST"],
        )
        for capability in LOCAL_CAPABILITIES
        if capability.rest is not None
    ]
    # Debe ir al final: es el reenvio generico de cualquier ruta no local.
    routes.append(
        Route("/{capability_path:path}", forward_route, methods=["GET", "POST"])
    )
    return Starlette(
        routes=routes,
        exception_handlers={ExtendedError: extended_error_handler},
    )


async def _request_payload(request) -> Any:
    raw = await request.body()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExtendedRequestError(
            "el cuerpo de la peticion no contiene JSON valido",
            "body",
        ) from exc


def _forwarded_response(result: ForwardedJson | ForwardedStream):
    from starlette.responses import JSONResponse, StreamingResponse

    if isinstance(result, ForwardedJson):
        headers = {}
        if result.content_type:
            headers["content-type"] = result.content_type
        return JSONResponse(
            result.payload,
            status_code=result.status_code,
            headers=headers,
        )

    return StreamingResponse(
        _stream_events(result),
        status_code=result.status_code,
        headers={"content-type": result.content_type},
    )


def _stream_events(stream: ForwardedStream) -> Iterator[bytes]:
    """Entrega cada evento recibido antes de pedir el siguiente."""
    try:
        for event in stream:
            yield f"{event.raw}\n\n".encode("utf-8")
    finally:
        stream.close()


def main() -> None:
    """Arranca la REST con escucha configurable y loopback por defecto."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - depende del extra instalado
        raise RuntimeError(
            "REST extra no instalado; instala ianest-extended[rest]"
        ) from exc
    config = ExtendedConfig.from_env()
    uvicorn.run(create_app(config=config), host=config.rest_host, port=config.rest_port)


if __name__ == "__main__":
    main()
