"""Vertical minimo: recall, prompt.run y write-back."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .clients import CoreClient, CoreResult
from .config import ExtendedConfig
from .models import (
    EngramWrite,
    MemoryIdentity,
    Principal,
    RecallItem,
    RecallQuery,
)
from .ports import MemoryStore
from .telemetry import TelemetryWriter

DELEGATED_TYPES = (
    ("identity", "persona"),
    ("principles", "principles"),
    ("safety", "safety"),
)
SEMANTIC_NAMESPACES = ("facts", "preferences")
EPISODIC_NAMESPACES = ("facts", "tasks", "preferences")


@dataclass(frozen=True, slots=True)
class RecallBundle:
    delegated: tuple[RecallItem, ...]
    semantic: tuple[RecallItem, ...]
    episodic: tuple[RecallItem, ...]
    dialog: tuple[RecallItem, ...]
    context: str


@dataclass(frozen=True, slots=True)
class EnrichResult:
    response: str
    trace: dict[str, Any]
    context: str
    request_id: str


@dataclass(frozen=True, slots=True)
class _MemoryLine:
    tier: str
    text: str
    relevance: float
    permanent: bool = False


class MemoryEnricher:
    def __init__(
        self,
        *,
        store: MemoryStore,
        core: CoreClient,
        telemetry: TelemetryWriter,
        config: ExtendedConfig,
    ) -> None:
        self._store = store
        self._core = core
        self._telemetry = telemetry
        self._config = config

    def enrich(
        self,
        identity: MemoryIdentity,
        prompt: str,
    ) -> EnrichResult:
        request_id = str(uuid4())
        recall_started = time.monotonic()
        try:
            bundle = self.recall(identity, prompt)
        except Exception:
            self._telemetry.record(
                event="enrich.recall",
                request_id=request_id,
                core_request_id=None,
                identity=identity,
                counters=self._empty_recall_counters(),
                latency_ms=_latency_ms(recall_started),
                status="error",
            )
            raise
        recall_latency = _latency_ms(recall_started)
        enriched_prompt = compose_prompt(bundle.context, prompt)

        try:
            core_result = self._core.prompt_run(enriched_prompt, identity)
        except Exception:
            self._telemetry.record(
                event="enrich.recall",
                request_id=request_id,
                core_request_id=None,
                identity=identity,
                counters=self._recall_counters(bundle),
                latency_ms=recall_latency,
                status="error",
            )
            raise

        self._telemetry.record(
            event="enrich.recall",
            request_id=request_id,
            core_request_id=core_result.request_id,
            identity=identity,
            counters=self._recall_counters(bundle),
            latency_ms=recall_latency,
            status="ok",
        )

        write_started = time.monotonic()
        try:
            counters, status = self._write_back(
                identity=identity,
                prompt=prompt,
                core_result=core_result,
            )
        except Exception:
            self._telemetry.record(
                event="enrich.write_back",
                request_id=request_id,
                core_request_id=core_result.request_id,
                identity=identity,
                counters={
                    "dialog_written": 0,
                    "items_extracted": 0,
                    "items_written": 0,
                    "items_reinforced": 0,
                    "items_discarded": 0,
                    "invalid_json": 0,
                },
                latency_ms=_latency_ms(write_started),
                status="error",
            )
            raise
        self._telemetry.record(
            event="enrich.write_back",
            request_id=request_id,
            core_request_id=core_result.request_id,
            identity=identity,
            counters=counters,
            latency_ms=_latency_ms(write_started),
            status=status,
        )
        return EnrichResult(
            response=core_result.response,
            trace=core_result.trace,
            context=bundle.context,
            request_id=request_id,
        )

    def recall(self, identity: MemoryIdentity, prompt: str) -> RecallBundle:
        delegated: list[RecallItem] = []
        for type_name, namespace in DELEGATED_TYPES:
            delegated.extend(
                self._store.recall(
                    RecallQuery(
                        type_names=(type_name,),
                        identity=identity,
                        text=prompt,
                        namespace=namespace,
                    )
                )
            )

        semantic = self._recall_ranked_namespaces(
            "semantic",
            SEMANTIC_NAMESPACES,
            self._config.semantic_top_k,
            identity,
            prompt,
        )
        episodic = self._recall_ranked_namespaces(
            "episodic",
            EPISODIC_NAMESPACES,
            self._config.episodic_top_k,
            identity,
            prompt,
        )
        dialog = tuple(
            self._store.recall(
                RecallQuery(
                    type_names=("dialog",),
                    identity=identity,
                    text=prompt,
                    domain_tag=identity.domain_tag,
                    top_k=self._config.dialog_top_k,
                )
            )
        )
        lines = (
            _lines("delegated", delegated, permanent=True)
            + _lines("semantic", semantic)
            + _lines("episodic", episodic)
            + _lines("dialog", dialog)
        )
        context = _compose_context(
            lines,
            self._config.memory_budget_tokens * 4,
        )
        return RecallBundle(
            delegated=tuple(delegated),
            semantic=semantic,
            episodic=episodic,
            dialog=dialog,
            context=context,
        )

    def _recall_ranked_namespaces(
        self,
        type_name: str,
        namespaces: tuple[str, ...],
        top_k: int,
        identity: MemoryIdentity,
        prompt: str,
    ) -> tuple[RecallItem, ...]:
        items: list[RecallItem] = []
        for namespace in namespaces:
            items.extend(
                self._store.recall(
                    RecallQuery(
                        type_names=(type_name,),
                        identity=identity,
                        text=prompt,
                        namespace=namespace,
                        domain_tag=identity.domain_tag,
                        top_k=top_k,
                    )
                )
            )
        items.sort(key=lambda item: item.relevance, reverse=True)
        return tuple(items[:top_k])

    def _write_back(
        self,
        *,
        identity: MemoryIdentity,
        prompt: str,
        core_result: CoreResult,
    ) -> tuple[dict[str, int], str]:
        counters = {
            "dialog_written": 0,
            "items_extracted": 0,
            "items_written": 0,
            "items_reinforced": 0,
            "items_discarded": 0,
            "invalid_json": 0,
        }
        common = {
            "identity": identity,
            "service": identity.service,
            "domain_tag": identity.domain_tag,
            "source_trace_id": core_result.request_id,
        }
        for content in (prompt, core_result.response):
            self._store.write(
                Principal.EXTENDED,
                EngramWrite(
                    type_name="dialog",
                    content=content,
                    **common,
                ),
            )
            counters["dialog_written"] += 1

        extraction = self._core.prompt_run(
            _extraction_prompt(prompt, core_result.response),
            identity,
            model=self._config.extraction_model,
        )
        try:
            items = _parse_extraction(extraction.response)
        except (json.JSONDecodeError, ValueError, TypeError):
            counters["invalid_json"] = 1
            counters["items_discarded"] = 1
            return counters, "invalid_extraction_json"

        counters["items_extracted"] = len(items)
        for item in items:
            parsed = _validate_item(item)
            if (
                parsed is None
                or parsed["confidence"] < self._config.confidence_threshold
            ):
                counters["items_discarded"] += 1
                continue
            existing = self._store.find_similar(
                user_id=identity.user_id or "",
                namespace=parsed["namespace"],
                text=parsed["content"],
                threshold=self._config.dedup_threshold,
            )
            if existing is not None:
                self._store.reinforce(Principal.EXTENDED, existing.id)
                counters["items_reinforced"] += 1
                continue
            self._store.write(
                Principal.EXTENDED,
                EngramWrite(
                    type_name="episodic",
                    content=parsed["content"],
                    namespace=parsed["namespace"],
                    score=parsed["confidence"],
                    unresolved_mentions=parsed["mentions"],
                    **common,
                ),
            )
            counters["items_written"] += 1
        return counters, "ok"

    def _recall_counters(self, bundle: RecallBundle) -> dict[str, int]:
        return {
            "delegated_k_requested": 0,
            "delegated_returned": len(bundle.delegated),
            "semantic_k_requested": self._config.semantic_top_k,
            "semantic_returned": len(bundle.semantic),
            "episodic_k_requested": self._config.episodic_top_k,
            "episodic_returned": len(bundle.episodic),
            "dialog_k_requested": self._config.dialog_top_k,
            "dialog_returned": len(bundle.dialog),
        }

    def _empty_recall_counters(self) -> dict[str, int]:
        return {
            "delegated_k_requested": 0,
            "delegated_returned": 0,
            "semantic_k_requested": self._config.semantic_top_k,
            "semantic_returned": 0,
            "episodic_k_requested": self._config.episodic_top_k,
            "episodic_returned": 0,
            "dialog_k_requested": self._config.dialog_top_k,
            "dialog_returned": 0,
        }


def compose_prompt(context: str, prompt: str) -> str:
    if not context:
        return prompt
    return (
        "<memory_context>\n"
        f"{context}\n"
        "</memory_context>\n\n"
        f"{prompt}"
    )


def _lines(
    tier: str,
    items,
    *,
    permanent: bool = False,
) -> list[_MemoryLine]:
    result = []
    for item in items:
        if item.engram is not None:
            namespace = item.engram.namespace or "raw"
            text = f"[{item.type_name}/{namespace}] {item.engram.content}"
        elif item.entity is not None:
            text = (
                f"[{item.type_name}/entities] {item.entity.name}: "
                f"{json.dumps(item.entity.profile, ensure_ascii=True)}"
            )
        else:
            continue
        result.append(
            _MemoryLine(
                tier=tier,
                text=text,
                relevance=item.relevance,
                permanent=permanent,
            )
        )
    return result


def _compose_context(lines: list[_MemoryLine], budget_chars: int) -> str:
    selected = list(lines)
    while _rendered_length(selected) > budget_chars:
        removable = [
            (index, line)
            for index, line in enumerate(selected)
            if not line.permanent
        ]
        if not removable:
            break
        worst_index, _ = min(
            removable,
            key=lambda pair: (pair[1].relevance, pair[0]),
        )
        selected.pop(worst_index)
    sections: list[str] = []
    for tier in ("delegated", "semantic", "episodic", "dialog"):
        tier_lines = [line.text for line in selected if line.tier == tier]
        if tier_lines:
            sections.append(f"## {tier}\n" + "\n".join(tier_lines))
    return "\n\n".join(sections)


def _rendered_length(lines: list[_MemoryLine]) -> int:
    return sum(len(line.text) + len(line.tier) + 8 for line in lines)


def _extraction_prompt(user_prompt: str, assistant_response: str) -> str:
    return (
        "Extract only literal, durable information stated in the conversation. "
        "Do not infer motives, identity, personality, or unstated facts. "
        "Smalltalk must produce zero items. Return only one JSON object with "
        'shape {"items":[{"namespace":"facts|preferences|tasks",'
        '"content":"literal concise item","confidence":0.0,'
        '"mentions":["literal name"]}]}. Use an empty items array when nothing '
        "qualifies.\n\n"
        f"USER:\n{user_prompt}\n\nASSISTANT:\n{assistant_response}"
    )


def _parse_extraction(response: str) -> list[dict[str, Any]]:
    data = json.loads(response)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("la extraccion no contiene items")
    return data["items"]


def _validate_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    namespace = item.get("namespace")
    content = item.get("content")
    confidence = item.get("confidence")
    mentions = item.get("mentions", [])
    if namespace not in EPISODIC_NAMESPACES:
        return None
    if not isinstance(content, str) or not content.strip():
        return None
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return None
    if not 0.0 <= float(confidence) <= 1.0:
        return None
    if not isinstance(mentions, list) or not all(
        isinstance(mention, str) and mention.strip() for mention in mentions
    ):
        return None
    return {
        "namespace": namespace,
        "content": content.strip(),
        "confidence": float(confidence),
        "mentions": tuple(mention.strip() for mention in mentions),
    }


def _latency_ms(started: float) -> int:
    return max(0, round((time.monotonic() - started) * 1000))
