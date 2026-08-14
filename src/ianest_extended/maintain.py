"""Mantenimiento mecanico del gradiente estricto (capacidad memory.maintain)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from .config import ExtendedConfig
from .consolidation import ConsolidationExecutor
from .models import (
    ConsolidationEvent,
    ConsolidationTrigger,
    MemoryIdentity,
    Principal,
)
from .ports import MemoryStore
from .telemetry import TelemetryWriter


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    dialog_archived: int
    episodic_promoted: int
    candidates_seen: int
    dry_run: bool


def run_maintenance(
    *,
    store: MemoryStore,
    telemetry: TelemetryWriter,
    config: ExtendedConfig,
    dry_run: bool = False,
    now: datetime | None = None,
) -> MaintenanceResult:
    started = time.monotonic()
    request_id = str(uuid4())
    effective_now = now or datetime.now(UTC)
    old_dialogs = tuple(
        store.find_dialogs_to_archive(
            now=effective_now,
            hot_window_seconds=config.dialog_hot_window_seconds,
        )
    )
    candidates = tuple(
        store.find_episodic_to_promote(
            now=effective_now,
            recency_max=config.promote_recency_max,
            min_stability=config.promote_min_stability,
            min_score=config.promote_min_score,
        )
    )
    result = MaintenanceResult(
        dialog_archived=len(old_dialogs),
        episodic_promoted=len(candidates),
        candidates_seen=len(candidates),
        dry_run=dry_run,
    )
    status = "dry_run" if dry_run else "ok"
    try:
        if not dry_run:
            executor = ConsolidationExecutor(
                store=store,
                telemetry=telemetry,
            )
            for dialog in old_dialogs:
                executor.execute(
                    ConsolidationEvent(
                        trigger=ConsolidationTrigger.DECAY,
                        principal=Principal.EXTENDED,
                        source_ids=(dialog.id,),
                        target_type=None,
                        content=None,
                        target_namespace=None,
                        reason="dialog_hot_window_elapsed",
                    )
                )
            for episodic in candidates:
                executor.execute(
                    ConsolidationEvent(
                        trigger=ConsolidationTrigger.DECAY,
                        principal=Principal.EXTENDED,
                        source_ids=(episodic.id,),
                        target_type="semantic",
                        content=episodic.content,
                        target_namespace=episodic.namespace,
                        reason="promoted_to_semantic",
                    )
                )
    except Exception:
        _record_maintain(
            telemetry,
            request_id,
            result,
            started,
            "error",
        )
        raise
    _record_maintain(
        telemetry,
        request_id,
        result,
        started,
        status,
    )
    return result


def _record_maintain(
    telemetry: TelemetryWriter,
    request_id: str,
    result: MaintenanceResult,
    started: float,
    status: str,
) -> None:
    telemetry.record(
        event="memory.maintain",
        request_id=request_id,
        downstream_request_id=None,
        identity=MemoryIdentity(),
        counters={
            "dialog_archived": result.dialog_archived,
            "episodic_promoted": result.episodic_promoted,
            "candidates_seen": result.candidates_seen,
            "dry_run": int(result.dry_run),
        },
        latency_ms=max(0, round((time.monotonic() - started) * 1000)),
        status=status,
    )


