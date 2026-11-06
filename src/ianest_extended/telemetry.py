"""Telemetria JSONL diaria de la capa.

`downstream_request_id` es el nombre generico del ente para el identificador de
la llamada hacia la capa inmediatamente inferior (meta ADR 0009, punto 4).
"""

from __future__ import annotations

import json
import re
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import MemoryIdentity
from .errors import ExtendedError, ORIGIN


class TelemetryWriter:
    _warning_lock = threading.Lock()
    _warned_failures: set[tuple[str, type[Exception]]] = set()

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        event: str,
        request_id: str,
        downstream_request_id: str | None,
        identity: MemoryIdentity,
        counters: dict[str, int],
        latency_ms: int,
        status: str,
        details: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        path = self._directory
        try:
            now = datetime.now(UTC)
            path = self._directory / f"extended-{now.date().isoformat()}.jsonl"
            payload = {
                "timestamp": now.isoformat(),
                "event": event,
                "request_id": request_id,
                "downstream_request_id": downstream_request_id,
                "identity": {
                    "user_id": identity.user_id,
                    "service": identity.service,
                    "session_id": identity.session_id,
                    "domain_tag": identity.domain_tag,
                    "namespace": identity.namespace,
                },
                "counters": counters,
                "latency_ms": latency_ms,
                "status": status,
            }
            if details:
                payload.update(details)
            if status == "error":
                recorded_error = error or sys.exception()
                if recorded_error is not None:
                    payload["error"] = _error_payload(recorded_error)
            line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
            with self._lock:
                self._directory.mkdir(parents=True, exist_ok=True)
                with path.open("a", encoding="ascii") as stream:
                    stream.write(line)
                    stream.write("\n")
        except Exception as exc:
            try:
                self._warn_once(path, exc)
            except Exception:
                return

    @classmethod
    def _warn_once(cls, path: Path, error: Exception) -> None:
        raw_path = str(path)
        key = (raw_path, type(error))
        with cls._warning_lock:
            if key in cls._warned_failures:
                return
            cls._warned_failures.add(key)
        path_text = raw_path.replace("\r", "\\r").replace("\n", "\\n")
        message = str(error).replace("\r", "\\r").replace("\n", "\\n")
        try:
            print(
                "telemetry line lost: "
                f"path={path_text} error={type(error).__name__}: {message}",
                file=sys.stderr,
            )
        except Exception:
            return


def _error_payload(error: Exception) -> dict[str, str | None]:
    if isinstance(error, ExtendedError):
        error_type = error.type
        origin = error.origin
        message = error.message
    else:
        error_type = type(error).__name__
        origin = ORIGIN
        message = str(error)
    return {
        "type": error_type,
        "origin": origin,
        "message": _safe_message(message),
    }


def _safe_message(message: str) -> str:
    """Recorta y oculta valores que no pertenecen a la telemetria."""
    without_body = re.sub(r"(HTTP \d+ desde [^:]+):.*", r"\1", message)
    redacted = re.sub(r"(?i)(password|token|secret|api[_-]?key)=([^\s&]+)", r"\1=[redacted]", without_body)
    return redacted[:300]
