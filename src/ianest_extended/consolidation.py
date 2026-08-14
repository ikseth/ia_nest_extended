"""Ejecucion trazable de eventos de consolidacion."""

from __future__ import annotations

import time
from uuid import uuid4

from .models import (
    ConsolidationEvent,
    ConsolidationResult,
    MemoryIdentity,
)
from .ports import MemoryStore
from .telemetry import TelemetryWriter


class ConsolidationExecutor:
    """Unico punto de servicio para aplicar y trazar consolidaciones."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        telemetry: TelemetryWriter,
    ) -> None:
        self._store = store
        self._telemetry = telemetry

    def execute(self, event: ConsolidationEvent) -> ConsolidationResult:
        request_id = str(uuid4())
        started = time.monotonic()
        try:
            result = self._store.execute_consolidation(event)
        except Exception:
            self._telemetry.record(
                event="memory.consolidation",
                request_id=request_id,
                downstream_request_id=None,
                identity=MemoryIdentity(),
                counters={
                    "sources_archived": 0,
                    "targets_created": 0,
                    "links_created": 0,
                },
                latency_ms=_latency_ms(started),
                status="error",
            )
            raise
        self._telemetry.record(
            event="memory.consolidation",
            request_id=request_id,
            downstream_request_id=None,
            identity=result.identity,
            counters={
                "sources_archived": len(result.archived_sources),
                "targets_created": int(result.target is not None),
                "links_created": result.links_created,
            },
            latency_ms=_latency_ms(started),
            status="ok",
        )
        return result


def _latency_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
