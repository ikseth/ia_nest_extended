"""Clientes HTTP para los servicios locales consumidos por la capa.

Regla de la fase 7a: TIPADO donde esta capa sobreescribe (necesita interpretar
la respuesta) y OPACO donde reenvia. El reenvio generico no parsea, no valida y
no reescribe: devuelve lo que el core devolvio.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.client import HTTPConnection, HTTPException, HTTPSConnection
from typing import Any
from urllib.parse import urlsplit

from .errors import (
    CoreConnectionError,
    CoreResponseError,
    DownstreamError,
    InvalidEmbeddingDimensionError,
    OllamaConnectionError,
    OllamaResponseError,
)
from .models import MemoryIdentity

DEFAULT_CONNECT_TIMEOUT_SECONDS = 30.0
DEFAULT_INACTIVITY_TIMEOUT_SECONDS = 30.0

# Identidad de la capa inmediatamente inferior. Se usa SOLO para completar el
# `origin` que el core no emite (meta ADR 0009, punto 2, excepcion acotada).
CORE_ORIGIN = "ia_nest_core"


@dataclass(frozen=True, slots=True)
class Timeouts:
    """Modelo de timeout de la fase 7a: conexion e inactividad entre eventos."""

    connect_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS
    inactivity_seconds: float = DEFAULT_INACTIVITY_TIMEOUT_SECONDS


@dataclass(frozen=True, slots=True)
class CoreResult:
    response: str
    trace: dict[str, Any]
    payload: dict[str, Any] = field(default_factory=dict)
    model: str | None = None
    domain: str | None = None
    params: dict[str, Any] | None = None

    @property
    def request_id(self) -> str:
        return str(self.trace["request_id"])

    @property
    def finish_reason(self) -> str:
        return str(self.trace["finish_reason"])


@dataclass(frozen=True, slots=True)
class DomainRouteResult:
    domain: str
    confidence: float
    reason: str
    alternatives: tuple[dict[str, Any], ...]
    trace: dict[str, Any]


@dataclass(frozen=True, slots=True)
class TaskPlanResult:
    """Respuesta tipada solo en los campos que la capa debe interpretar."""

    payload: dict[str, Any]
    plan: tuple[dict[str, Any], ...]
    trace: dict[str, Any]

    @property
    def request_id(self) -> str:
        return str(self.trace["request_id"])


@dataclass(frozen=True, slots=True)
class SseEvent:
    """Un evento del flujo `text/event-stream`, tal como llego."""

    event: str | None
    data: str
    raw: str


@dataclass(frozen=True, slots=True)
class ForwardedJson:
    """Respuesta JSON reenviada sin parsear campo a campo."""

    payload: dict[str, Any]
    content_type: str = "application/json"


class ForwardedStream:
    """Respuesta `text/event-stream` retransmitida evento a evento."""

    content_type = "text/event-stream"

    def __init__(self, events: Iterator[SseEvent], close) -> None:
        self._events = events
        self._close = close

    def __iter__(self) -> Iterator[SseEvent]:
        return self._events

    def close(self) -> None:
        self._close()


def capability_route(capability: str) -> str:
    """Deriva la ruta del core a partir del nombre de capacidad.

    Mecanismo GENERICO: `prompt.run` -> `/prompt/run`. No hay tabla por
    capacidad, de modo que una capacidad que el core anada es alcanzable sin
    tocar el codigo de esta capa. Un valor que ya sea una ruta se respeta.
    """
    value = capability.strip()
    if not value:
        raise CoreResponseError("la capacidad reenviada no puede estar vacia")
    if value.startswith("/"):
        return value
    return "/" + value.replace(".", "/")


class CoreClient:
    """Cliente del contrato REST del core: reenvio generico y llamadas tipadas."""

    def __init__(
        self,
        base_url: str,
        *,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        inactivity_timeout_seconds: float = DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
        task_timeout_seconds: float = 600.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeouts = Timeouts(
            connect_seconds=connect_timeout_seconds,
            inactivity_seconds=inactivity_timeout_seconds,
        )
        self._task_timeouts = Timeouts(
            connect_seconds=connect_timeout_seconds,
            inactivity_seconds=task_timeout_seconds,
        )
        self._domain_ids: tuple[str, ...] | None = None

    # --- reenvio generico (opaco) -----------------------------------------

    def forward(
        self,
        capability: str,
        payload: dict[str, Any] | None = None,
        *,
        method: str | None = None,
    ) -> ForwardedJson | ForwardedStream:
        """Reenvia una capacidad cualquiera del core sin conocerla.

        Sin payload el metodo por defecto es GET; con payload, POST. La forma
        de la respuesta la decide el `Content-Type` que devuelve el core.
        """
        route = capability_route(capability)
        verb = method or ("GET" if payload is None else "POST")
        connection, response = _open(
            f"{self._base_url}{route}",
            verb,
            payload,
            self._timeouts,
            connection_error=CoreConnectionError,
        )
        try:
            _raise_for_status(
                response,
                f"{self._base_url}{route}",
                downstream_origin=CORE_ORIGIN,
            )
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                return ForwardedStream(
                    _iter_sse(connection, response),
                    connection.close,
                )
            data = _decode_json(
                response.read(),
                f"{self._base_url}{route}",
                CoreResponseError,
            )
        except BaseException:
            connection.close()
            raise
        connection.close()
        return ForwardedJson(payload=data, content_type=content_type)

    # --- llamadas tipadas (lo que esta capa interpreta) --------------------

    def prompt_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        model: str | None = None,
        domain: str | None = None,
    ) -> CoreResult:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "identity": identity.to_core_dict(),
        }
        if model is not None:
            payload["model"] = model
        if domain is not None:
            payload["domain"] = domain
        data = self._post_json("/prompt/run", payload)
        if not isinstance(data.get("response"), str):
            raise CoreResponseError("el core no devolvio response como texto")
        trace = data.get("trace")
        if not isinstance(trace, dict):
            raise CoreResponseError("el core no devolvio una traza")
        if not trace.get("request_id"):
            raise CoreResponseError("la traza del core no incluye request_id")
        if trace.get("finish_reason") is None:
            raise CoreResponseError(
                "la traza del core no incluye finish_reason"
            )
        params = data.get("params")
        if params is not None and not isinstance(params, dict):
            raise CoreResponseError("params del core no es un objeto")
        return CoreResult(
            response=data["response"],
            trace=trace,
            payload=data,
            model=_optional_text(data.get("model")),
            domain=_optional_text(data.get("domain")),
            params=params,
        )

    def reasoning_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        model: str | None = None,
        domain: str | None = None,
    ) -> CoreResult:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "identity": identity.to_core_dict(),
        }
        if model is not None:
            payload["model"] = model
        if domain is not None:
            payload["domain"] = domain
        data = self._post_json("/reasoning/run", payload)
        return _typed_core_result(data, text_field="output")

    def task_plan(
        self,
        prompt: str,
        identity: MemoryIdentity,
        *,
        effort: str | None = None,
    ) -> TaskPlanResult:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "identity": identity.to_core_dict(),
        }
        if effort is not None:
            payload["effort"] = effort
        data = self._post_json(
            "/task/plan",
            payload,
            timeouts=self._task_timeouts,
        )
        plan = data.get("plan")
        if not isinstance(plan, list):
            raise CoreResponseError("task.plan no devolvio plan como lista")
        for item in plan:
            if not isinstance(item, dict):
                raise CoreResponseError("task.plan devolvio una subtarea invalida")
            if not isinstance(item.get("prompt"), str):
                raise CoreResponseError(
                    "task.plan devolvio una subtarea sin prompt de texto"
                )
            if not isinstance(item.get("domain"), str):
                raise CoreResponseError(
                    "task.plan devolvio una subtarea sin dominio resuelto"
                )
        trace = _required_trace(data, "task.plan")
        return TaskPlanResult(
            payload=data,
            plan=tuple(plan),
            trace=trace,
        )

    def task_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        *,
        plan_payload: dict[str, Any] | None = None,
        effort: str | None = None,
    ) -> CoreResult:
        payload = dict(plan_payload or {})
        payload.pop("params", None)
        payload["prompt"] = prompt
        payload["identity"] = identity.to_core_dict()
        if effort is not None:
            payload["effort"] = effort
        data = self._post_json(
            "/task/run",
            payload,
            timeouts=self._task_timeouts,
        )
        return _typed_core_result(data, text_field="response")

    def domain_route(
        self,
        prompt: str,
        identity: MemoryIdentity,
    ) -> DomainRouteResult:
        data = self._post_json(
            "/domain/route",
            {"prompt": prompt, "identity": identity.to_core_dict()},
        )
        domain = data.get("domain")
        confidence = data.get("confidence")
        reason = data.get("reason")
        alternatives = data.get("alternatives", [])
        trace = data.get("trace", {})
        if not isinstance(domain, str) or not domain.strip():
            raise CoreResponseError("domain.route no devolvio un dominio")
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.0 <= float(confidence) <= 1.0
        ):
            raise CoreResponseError("domain.route devolvio confianza invalida")
        if not isinstance(reason, str):
            raise CoreResponseError("domain.route no devolvio un motivo")
        if not isinstance(alternatives, list) or not all(
            isinstance(item, dict) for item in alternatives
        ):
            raise CoreResponseError("domain.route devolvio alternativas invalidas")
        if not isinstance(trace, dict):
            raise CoreResponseError("domain.route devolvio una traza invalida")
        return DomainRouteResult(
            domain=domain.strip(),
            confidence=float(confidence),
            reason=reason,
            alternatives=tuple(alternatives),
            trace=trace,
        )

    def list_domains(self) -> tuple[str, ...]:
        if self._domain_ids is not None:
            return self._domain_ids
        data = self._get_json("/domain/list")
        domains = data.get("domains")
        if not isinstance(domains, list):
            raise CoreResponseError("domain.list no devolvio una lista de dominios")
        domain_ids: list[str] = []
        for domain in domains:
            if not isinstance(domain, dict):
                raise CoreResponseError("domain.list devolvio un dominio invalido")
            domain_id = domain.get("id")
            if not isinstance(domain_id, str) or not domain_id.strip():
                raise CoreResponseError("domain.list devolvio un dominio sin id")
            domain_ids.append(domain_id.strip())
        self._domain_ids = tuple(domain_ids)
        return self._domain_ids

    def _post_json(
        self,
        route: str,
        payload: dict[str, Any],
        *,
        timeouts: Timeouts | None = None,
    ) -> dict[str, Any]:
        return _request_json(
            f"{self._base_url}{route}",
            "POST",
            payload,
            timeouts or self._timeouts,
            connection_error=CoreConnectionError,
            response_error=CoreResponseError,
            downstream_origin=CORE_ORIGIN,
        )

    def _get_json(self, route: str) -> dict[str, Any]:
        return _request_json(
            f"{self._base_url}{route}",
            "GET",
            None,
            self._timeouts,
            connection_error=CoreConnectionError,
            response_error=CoreResponseError,
            downstream_origin=CORE_ORIGIN,
        )


def _required_trace(data: dict[str, Any], capability: str) -> dict[str, Any]:
    trace = data.get("trace")
    if not isinstance(trace, dict):
        raise CoreResponseError(f"{capability} no devolvio una traza")
    if not trace.get("request_id"):
        raise CoreResponseError(
            f"la traza de {capability} no incluye request_id"
        )
    return trace


def _typed_core_result(
    data: dict[str, Any],
    *,
    text_field: str,
) -> CoreResult:
    value = data.get(text_field)
    if not isinstance(value, str):
        raise CoreResponseError(
            f"el core no devolvio {text_field} como texto"
        )
    trace = _required_trace(data, text_field)
    params = data.get("params")
    if params is not None and not isinstance(params, dict):
        raise CoreResponseError("params del core no es un objeto")
    return CoreResult(
        response=value,
        trace=trace,
        payload=data,
        model=_optional_text(data.get("model")),
        domain=_optional_text(data.get("domain")),
        params=params,
    )


class OllamaEmbedder:
    """Adaptador del endpoint /api/embed de Ollama."""

    def __init__(
        self,
        base_url: str,
        model: str,
        dimension: int,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        inactivity_timeout_seconds: float = DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
    ) -> None:
        if dimension <= 0:
            raise InvalidEmbeddingDimensionError(
                "embedding_dimension debe ser mayor que cero"
            )
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension
        self._timeouts = Timeouts(
            connect_seconds=connect_timeout_seconds,
            inactivity_seconds=inactivity_timeout_seconds,
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> tuple[float, ...]:
        data = _request_json(
            f"{self._base_url}/api/embed",
            "POST",
            {"model": self._model, "input": text},
            self._timeouts,
            connection_error=OllamaConnectionError,
            response_error=OllamaResponseError,
        )
        embeddings = data.get("embeddings")
        if (
            not isinstance(embeddings, list)
            or len(embeddings) != 1
            or not isinstance(embeddings[0], list)
        ):
            raise OllamaResponseError(
                "Ollama no devolvio exactamente un embedding"
            )
        try:
            vector = tuple(float(value) for value in embeddings[0])
        except (TypeError, ValueError) as exc:
            raise OllamaResponseError(
                "el embedding de Ollama contiene valores no numericos"
            ) from exc
        if len(vector) != self._dimension:
            raise InvalidEmbeddingDimensionError(
                f"Ollama devolvio dimension {len(vector)}; "
                f"se esperaba {self._dimension}"
            )
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isfinite(norm) or norm == 0.0:
            raise OllamaResponseError("Ollama devolvio un vector no normalizable")
        return tuple(value / norm for value in vector)


def _open(
    url: str,
    method: str,
    payload: dict[str, Any] | None,
    timeouts: Timeouts,
    *,
    connection_error,
):
    parts = urlsplit(url)
    factory = HTTPSConnection if parts.scheme == "https" else HTTPConnection
    connection = factory(
        parts.hostname or "",
        parts.port,
        timeout=timeouts.connect_seconds,
    )
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json, text/event-stream"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    target = parts.path or "/"
    if parts.query:
        target = f"{target}?{parts.query}"
    try:
        connection.request(method, target, body=body, headers=headers)
        if connection.sock is not None:
            connection.sock.settimeout(timeouts.inactivity_seconds)
        response = connection.getresponse()
    except (OSError, TimeoutError, HTTPException) as exc:
        connection.close()
        raise connection_error(f"no se pudo conectar con {url}: {exc}") from exc
    return connection, response


def _request_json(
    url: str,
    method: str,
    payload: dict[str, Any] | None,
    timeouts: Timeouts,
    *,
    connection_error,
    response_error,
    downstream_origin: str | None = None,
) -> dict[str, Any]:
    connection, response = _open(
        url,
        method,
        payload,
        timeouts,
        connection_error=connection_error,
    )
    try:
        _raise_for_status(
            response,
            url,
            response_error=response_error,
            downstream_origin=downstream_origin,
        )
        raw = response.read()
    except (OSError, TimeoutError, HTTPException) as exc:
        raise connection_error(f"no se pudo leer de {url}: {exc}") from exc
    finally:
        connection.close()
    return _decode_json(raw, url, response_error)


def _raise_for_status(
    response,
    url: str,
    *,
    response_error=None,
    downstream_origin: str | None = None,
) -> None:
    if response.status < 400:
        return
    raw = response.read()
    error = _core_error_payload(raw) if downstream_origin else None
    if error is not None:
        # Un error de una capa inferior se propaga TAL CUAL, completando solo
        # el `origin` ausente (meta ADR 0009, punto 2).
        raise DownstreamError(error, downstream_origin)
    detail = raw.decode("utf-8", errors="replace")
    factory = response_error or CoreResponseError
    raise factory(f"HTTP {response.status} desde {url}: {detail[:500]}")


def _core_error_payload(raw: bytes) -> dict[str, Any] | None:
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    error = data.get("error")
    if isinstance(error, dict) and error.get("type"):
        return error
    if data.get("type") and "message" in data:
        return data
    return None


def _decode_json(raw: bytes, url: str, response_error) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise response_error(f"{url} no devolvio JSON valido") from exc
    if not isinstance(data, dict):
        raise response_error(f"{url} no devolvio un objeto JSON")
    return data


def _iter_sse(connection, response) -> Iterator[SseEvent]:
    """Retransmite evento a evento; no acumula el flujo ni lo convierte."""
    block: list[str] = []
    try:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").rstrip("\n").rstrip("\r")
            if line:
                block.append(line)
                continue
            if block:
                yield _parse_sse_block(block)
                block = []
        if block:
            yield _parse_sse_block(block)
    finally:
        connection.close()


def _parse_sse_block(lines: list[str]) -> SseEvent:
    name: str | None = None
    data: list[str] = []
    for line in lines:
        if line.startswith(":"):
            continue
        field_name, _, value = line.partition(":")
        value = value[1:] if value.startswith(" ") else value
        if field_name == "event":
            name = value
        elif field_name == "data":
            data.append(value)
    return SseEvent(event=name, data="\n".join(data), raw="\n".join(lines))


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)
