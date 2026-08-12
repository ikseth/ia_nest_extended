"""Telemetria JSONL diaria de la capa."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import MemoryIdentity


class TelemetryWriter:
    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._lock = threading.Lock()

    def record(
        self,
        *,
        event: str,
        request_id: str,
        core_request_id: str | None,
        identity: MemoryIdentity,
        counters: dict[str, int],
        latency_ms: int,
        status: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        payload = {
            "timestamp": now.isoformat(),
            "event": event,
            "request_id": request_id,
            "core_request_id": core_request_id,
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
        path = self._directory / f"extended-{now.date().isoformat()}.jsonl"
        line = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        with self._lock:
            self._directory.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="ascii") as stream:
                stream.write(line)
                stream.write("\n")
