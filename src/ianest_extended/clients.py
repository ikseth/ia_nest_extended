"""Clientes HTTP para los servicios locales consumidos por la capa."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import (
    CoreConnectionError,
    CoreResponseError,
    InvalidEmbeddingDimensionError,
    OllamaConnectionError,
    OllamaResponseError,
)
from .models import MemoryIdentity


@dataclass(frozen=True, slots=True)
class CoreResult:
    response: str
    trace: dict[str, Any]
    model: str | None = None
    domain: str | None = None
    params: dict[str, Any] | None = None

    @property
    def request_id(self) -> str:
        return str(self.trace["request_id"])

    @property
    def finish_reason(self) -> str:
        return str(self.trace["finish_reason"])


class CoreClient:
    """Cliente del contrato REST publico prompt.run del core."""

    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def prompt_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        model: str | None = None,
    ) -> CoreResult:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "identity": identity.to_core_dict(),
        }
        if model is not None:
            payload["model"] = model
        data = _post_json(
            f"{self._base_url}/prompt/run",
            payload,
            self._timeout_seconds,
            connection_error=CoreConnectionError,
            response_error=CoreResponseError,
        )
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
        timeout_seconds: float = 30.0,
    ) -> None:
        if dimension <= 0:
            raise InvalidEmbeddingDimensionError(
                "embedding_dimension debe ser mayor que cero"
            )
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension
        self._timeout_seconds = timeout_seconds

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> tuple[float, ...]:
        data = _post_json(
            f"{self._base_url}/api/embed",
            {"model": self._model, "input": text},
            self._timeout_seconds,
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


def _post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
    *,
    connection_error,
    response_error,
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise response_error(
            f"HTTP {exc.code} desde {url}: {detail[:500]}"
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise connection_error(f"no se pudo conectar con {url}: {exc}") from exc
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise response_error(f"{url} no devolvio JSON valido") from exc
    if not isinstance(data, dict):
        raise response_error(f"{url} no devolvio un objeto JSON")
    return data


def _optional_text(value: Any) -> str | None:
    return None if value is None else str(value)
