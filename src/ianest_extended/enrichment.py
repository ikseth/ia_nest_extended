"""Vertical minimo: recall, prompt.run y write-back."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, replace
from typing import Any
from uuid import uuid4

from .clients import CoreClient, CoreResult
from .config import ExtendedConfig
from .errors import InvalidCoreDomainError
from .models import (
    EngramWrite,
    MemoryIdentity,
    Principal,
    RagChunk,
    RecallItem,
    RecallQuery,
)
from .ports import MemoryStore, RagStore
from .telemetry import TelemetryWriter

DELEGATED_TYPES = (
    ("identity", "persona"),
    ("principles", "principles"),
    ("safety", "safety"),
)
SEMANTIC_NAMESPACES = ("facts", "preferences")
EPISODIC_NAMESPACES = ("facts", "tasks", "preferences")
CONTEXT_WRAPPER_CHARS = len("<enrichment_context>\n\n</enrichment_context>\n\n")
_CORE_RESULT_TRACE = object()


@dataclass(frozen=True, slots=True)
class RecallBundle:
    delegated: tuple[RecallItem, ...]
    rag: tuple[RagChunk, ...]
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
    payload: dict[str, Any] = field(default_factory=dict)
    enriched_prompt: str = ""
    downstream_request_id: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedEnrichment:
    """Resultado comun de recuperar y componer antes de llamar al core."""

    identity: MemoryIdentity
    prompt: str
    bundle: RecallBundle
    enriched_prompt: str
    request_id: str
    recall_latency_ms: int


@dataclass(frozen=True, slots=True)
class _ContextLine:
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
        rag_store: RagStore | None = None,
    ) -> None:
        self._store = store
        self._core = core
        self._telemetry = telemetry
        self._config = config
        self._rag_store = rag_store

    def enrich(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
        write_back: bool | None = None,
        auto_domain: bool | None = None,
        model: str | None = None,
        dry_run: bool = False,
        request_id: str | None = None,
    ) -> EnrichResult:
        """Sobreescritura de `prompt.run`: recall, composicion, core y write-back.

        Los tres estados de cada bandera importan: `None` toma el default de
        configuracion; `True`/`False` son override por peticion.
        """
        return self._enrich(
            identity,
            prompt,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            auto_domain=auto_domain,
            model=model,
            dry_run=dry_run,
            request_id=request_id,
            core_run=self._core.prompt_run,
        )

    def enrich_reasoning(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
        write_back: bool | None = None,
        auto_domain: bool | None = None,
        model: str | None = None,
        dry_run: bool = False,
        request_id: str | None = None,
    ) -> EnrichResult:
        """Mismo vertical de enriquecimiento para `reasoning.run`."""
        return self._enrich(
            identity,
            prompt,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            auto_domain=auto_domain,
            model=model,
            dry_run=dry_run,
            request_id=request_id,
            core_run=self._core.reasoning_run,
        )

    def _enrich(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        use_memory: bool | None,
        use_rag: bool | None,
        write_back: bool | None,
        auto_domain: bool | None,
        model: str | None,
        dry_run: bool,
        request_id: str | None,
        core_run,
    ) -> EnrichResult:
        write_back_on = (
            self._config.write_back_enabled if write_back is None else write_back
        )
        prepared = self.prepare(
            identity,
            prompt,
            use_memory=use_memory,
            use_rag=use_rag,
            auto_domain=auto_domain,
            request_id=request_id,
        )

        if dry_run:
            self.record_recall(prepared, status="dry_run")
            return EnrichResult(
                response="",
                trace={},
                context=prepared.bundle.context,
                request_id=prepared.request_id,
                payload={},
                enriched_prompt=prepared.enriched_prompt,
                downstream_request_id=None,
            )

        try:
            core_result = core_run(
                prepared.enriched_prompt,
                prepared.identity,
                model=model,
                domain=prepared.identity.domain_tag,
            )
        except Exception:
            self.record_recall(prepared, status="error")
            raise

        self.record_recall(
            prepared,
            downstream_request_id=core_result.request_id,
            status="ok",
        )

        if not write_back_on:
            return EnrichResult(
                response=core_result.response,
                trace=core_result.trace,
                context=prepared.bundle.context,
                request_id=prepared.request_id,
                payload=core_result.payload,
                enriched_prompt=prepared.enriched_prompt,
                downstream_request_id=core_result.request_id,
            )

        self.write_back(
            request_id=prepared.request_id,
            identity=prepared.identity,
            prompt=prompt,
            core_result=core_result,
        )
        return EnrichResult(
            response=core_result.response,
            trace=core_result.trace,
            context=prepared.bundle.context,
            request_id=prepared.request_id,
            payload=core_result.payload,
            enriched_prompt=prepared.enriched_prompt,
            downstream_request_id=core_result.request_id,
        )

    def prepare(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
        auto_domain: bool | None = None,
        request_id: str | None = None,
    ) -> PreparedEnrichment:
        """Reusa el preambulo de `prompt.run` para llamadas bloqueantes o SSE."""
        memory_on = (
            self._config.memory_enabled if use_memory is None else use_memory
        )
        rag_on = self._config.rag_enabled if use_rag is None else use_rag
        auto_domain_on = (
            self._config.auto_domain if auto_domain is None else auto_domain
        )
        request_id = request_id or str(uuid4())
        resolved_identity, auto_route, route_confidence = self._resolve_domain(
            identity,
            prompt,
            auto_domain=auto_domain_on,
        )
        recall_started = time.monotonic()
        try:
            rag = self._retrieve_rag(
                request_id=request_id,
                identity=resolved_identity,
                prompt=prompt,
                auto_route=auto_route,
                route_confidence=route_confidence,
                use_rag=rag_on,
            )
            bundle = self.recall(
                resolved_identity,
                prompt,
                rag=rag,
                include_memory=memory_on,
            )
        except Exception:
            self._telemetry.record(
                event="enrich.recall",
                request_id=request_id,
                downstream_request_id=None,
                identity=resolved_identity,
                counters=self._empty_recall_counters(),
                latency_ms=_latency_ms(recall_started),
                status="error",
            )
            raise
        return PreparedEnrichment(
            identity=resolved_identity,
            prompt=prompt,
            bundle=bundle,
            enriched_prompt=compose_prompt(bundle.context, prompt),
            request_id=request_id,
            recall_latency_ms=_latency_ms(recall_started),
        )

    def record_recall(
        self,
        prepared: PreparedEnrichment,
        *,
        downstream_request_id: str | None = None,
        status: str,
    ) -> None:
        self._telemetry.record(
            event="enrich.recall",
            request_id=prepared.request_id,
            downstream_request_id=downstream_request_id,
            identity=prepared.identity,
            counters=self._recall_counters(prepared.bundle),
            latency_ms=prepared.recall_latency_ms,
            status=status,
        )

    def recall(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        rag: tuple[RagChunk, ...] = (),
        include_memory: bool = True,
        token_budget: int | None = None,
        rag_token_budget: int | None = None,
    ) -> RecallBundle:
        delegated: list[RecallItem] = []
        semantic: tuple[RecallItem, ...] = ()
        episodic: tuple[RecallItem, ...] = ()
        dialog: tuple[RecallItem, ...] = ()
        if include_memory:
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
                # D4: el suelo de similitud NO alcanza a `semantic` (lo
                # consolidado ya paso un juicio de promocion; ver
                # docs/PLAN.md D4 y docs/handoff/deuda_d4_brief.md).
                min_similarity=None,
            )
            episodic = self._recall_ranked_namespaces(
                "episodic",
                EPISODIC_NAMESPACES,
                self._config.episodic_top_k,
                identity,
                prompt,
                min_similarity=self._config.memory_min_similarity,
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
            + _rag_lines(rag)
            + _lines("semantic", semantic)
            + _lines("episodic", episodic)
            + _lines("dialog", dialog)
        )
        context = _compose_context(
            lines,
            token_budget=(
                self._config.memory_budget_tokens
                if token_budget is None
                else token_budget
            ),
            rag_token_budget=(
                self._config.rag_max_tokens
                if rag_token_budget is None
                else rag_token_budget
            ),
        )
        return RecallBundle(
            delegated=tuple(delegated),
            rag=rag,
            semantic=semantic,
            episodic=episodic,
            dialog=dialog,
            context=context,
        )

    def _resolve_domain(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        auto_domain: bool,
    ) -> tuple[MemoryIdentity, bool, float | None]:
        if identity.domain_tag is not None:
            domain = identity.domain_tag
            valid_domains = self._core.list_domains()
            if domain not in valid_domains:
                valid = ", ".join(valid_domains) or "(ninguno)"
                raise InvalidCoreDomainError(
                    f"dominio del core no valido '{domain}'; "
                    f"dominios validos: {valid}"
                )
            if domain == "general":
                return replace(identity, domain_tag=None), False, None
            return identity, False, None
        if not auto_domain:
            return identity, False, None
        route = self._core.domain_route(prompt, identity)
        if route.confidence < self._config.auto_domain_min_confidence:
            return identity, True, route.confidence
        if route.domain == "general":
            return identity, True, route.confidence
        return replace(identity, domain_tag=route.domain), True, route.confidence

    def _retrieve_rag(
        self,
        *,
        request_id: str,
        identity: MemoryIdentity,
        prompt: str,
        auto_route: bool,
        route_confidence: float | None,
        use_rag: bool,
    ) -> tuple[RagChunk, ...]:
        if not use_rag or self._rag_store is None:
            return ()
        started = time.monotonic()
        try:
            chunks = tuple(
                self._rag_store.retrieve(
                    prompt,
                    domain=identity.domain_tag,
                    top_k=self._config.rag_top_k,
                    min_score=self._config.rag_min_score,
                )
            )
        except Exception:
            self._record_rag_retrieve(
                request_id=request_id,
                identity=identity,
                chunks=(),
                auto_route=auto_route,
                route_confidence=route_confidence,
                latency_ms=_latency_ms(started),
                status="error",
            )
            raise
        self._record_rag_retrieve(
            request_id=request_id,
            identity=identity,
            chunks=chunks,
            auto_route=auto_route,
            route_confidence=route_confidence,
            latency_ms=_latency_ms(started),
            status="ok",
        )
        return chunks

    def retrieve_rag(
        self,
        *,
        request_id: str,
        identity: MemoryIdentity,
        prompt: str,
    ) -> tuple[RagChunk, ...]:
        """Recupera RAG para un dominio ya resuelto, sin llamar al router."""
        return self._retrieve_rag(
            request_id=request_id,
            identity=identity,
            prompt=prompt,
            auto_route=False,
            route_confidence=None,
            use_rag=True,
        )

    def _record_rag_retrieve(
        self,
        *,
        request_id: str,
        identity: MemoryIdentity,
        chunks: tuple[RagChunk, ...],
        auto_route: bool,
        route_confidence: float | None,
        latency_ms: int,
        status: str,
    ) -> None:
        self._telemetry.record(
            event="rag.retrieve",
            request_id=request_id,
            downstream_request_id=None,
            identity=identity,
            counters={
                "k_requested": self._config.rag_top_k,
                "k_returned": len(chunks),
            },
            latency_ms=latency_ms,
            status=status,
            details={
                "domain": identity.domain_tag,
                "corpora": sorted({chunk.corpus_name for chunk in chunks}),
                "auto_route": auto_route,
                "auto_route_confidence": route_confidence,
            },
        )

    def _recall_ranked_namespaces(
        self,
        type_name: str,
        namespaces: tuple[str, ...],
        top_k: int,
        identity: MemoryIdentity,
        prompt: str,
        *,
        min_similarity: float | None,
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
                        min_similarity=min_similarity,
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
        source_trace_id: str | None,
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
            "source_trace_id": source_trace_id,
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

    def write_back(
        self,
        *,
        request_id: str,
        identity: MemoryIdentity,
        prompt: str,
        core_result: CoreResult,
        source_trace_id: str | None | object = _CORE_RESULT_TRACE,
    ) -> tuple[dict[str, int], str]:
        """Aplica la politica comun al par original/final de otra capacidad."""
        resolved_trace_id = (
            core_result.request_id
            if source_trace_id is _CORE_RESULT_TRACE
            else source_trace_id
        )
        assert resolved_trace_id is None or isinstance(resolved_trace_id, str)
        started = time.monotonic()
        try:
            counters, status = self._write_back(
                identity=identity,
                prompt=prompt,
                core_result=core_result,
                source_trace_id=resolved_trace_id,
            )
        except Exception:
            self._telemetry.record(
                event="enrich.write_back",
                request_id=request_id,
                downstream_request_id=resolved_trace_id,
                identity=identity,
                counters={
                    "dialog_written": 0,
                    "items_extracted": 0,
                    "items_written": 0,
                    "items_reinforced": 0,
                    "items_discarded": 0,
                    "invalid_json": 0,
                },
                latency_ms=_latency_ms(started),
                status="error",
            )
            raise
        self._telemetry.record(
            event="enrich.write_back",
            request_id=request_id,
            downstream_request_id=resolved_trace_id,
            identity=identity,
            counters=counters,
            latency_ms=_latency_ms(started),
            status=status,
        )
        return counters, status

    def _recall_counters(self, bundle: RecallBundle) -> dict[str, int]:
        return {
            "delegated_k_requested": 0,
            "delegated_returned": len(bundle.delegated),
            "rag_k_requested": self._config.rag_top_k,
            "rag_returned": len(bundle.rag),
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
            "rag_k_requested": self._config.rag_top_k,
            "rag_returned": 0,
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
        "<enrichment_context>\n"
        f"{context}\n"
        "</enrichment_context>\n\n"
        f"{prompt}"
    )


def _lines(
    tier: str,
    items,
    *,
    permanent: bool = False,
) -> list[_ContextLine]:
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
            _ContextLine(
                tier=tier,
                text=text,
                relevance=item.relevance,
                permanent=permanent,
            )
        )
    return result


def _rag_lines(chunks: tuple[RagChunk, ...]) -> list[_ContextLine]:
    return [
        _ContextLine(
            tier="rag",
            text=(
                f"[{chunk.corpus_name}/{','.join(chunk.domains) or 'global'}/"
                f"{chunk.source_ref}"
                f"#{chunk.ordinal}] {chunk.content}"
            ),
            relevance=chunk.score,
        )
        for chunk in chunks
    ]


def _compose_context(
    lines: list[_ContextLine],
    *,
    token_budget: int,
    rag_token_budget: int,
) -> str:
    selected = list(lines)
    _trim_tier_to_budget(selected, "rag", rag_token_budget)
    while (
        estimate_tokens(_render_context(selected), extra_chars=CONTEXT_WRAPPER_CHARS)
        > token_budget
    ):
        removable = _next_removable_tier(selected)
        if not removable:
            break
        worst_index, _ = min(
            removable,
            key=lambda pair: (pair[1].relevance, pair[0]),
        )
        selected.pop(worst_index)
    return _render_context(selected)


def _trim_tier_to_budget(
    lines: list[_ContextLine],
    tier: str,
    token_budget: int,
) -> None:
    while estimate_tokens(_render_tier(lines, tier)) > token_budget:
        candidates = [
            (index, line)
            for index, line in enumerate(lines)
            if line.tier == tier
        ]
        if not candidates:
            return
        worst_index, _ = min(
            candidates,
            key=lambda pair: (pair[1].relevance, pair[0]),
        )
        lines.pop(worst_index)


def _next_removable_tier(
    lines: list[_ContextLine],
) -> list[tuple[int, _ContextLine]]:
    for tier in ("rag", "episodic", "semantic", "dialog"):
        candidates = [
            (index, line)
            for index, line in enumerate(lines)
            if line.tier == tier and not line.permanent
        ]
        if candidates:
            return candidates
    return []


def _render_context(lines: list[_ContextLine]) -> str:
    sections: list[str] = []
    for tier in ("delegated", "rag", "semantic", "episodic", "dialog"):
        tier_lines = [line.text for line in lines if line.tier == tier]
        if tier_lines:
            sections.append(f"## {tier}\n" + "\n".join(tier_lines))
    return "\n\n".join(sections)


def _render_tier(lines: list[_ContextLine], tier: str) -> str:
    tier_lines = [line.text for line in lines if line.tier == tier]
    return "" if not tier_lines else f"## {tier}\n" + "\n".join(tier_lines)


def estimate_tokens(text: str, *, extra_chars: int = 0) -> int:
    return math.ceil((len(text) + extra_chars) / 3.5)


def _extraction_prompt(user_prompt: str, assistant_response: str) -> str:
    return (
        "Extract only literal, durable information stated in the conversation. "
        "Do not infer motives, identity, personality, or unstated facts. "
        "For each item, namespace must be exactly one of facts, preferences, "
        "or tasks. Confidence must express the actual certainty from 0 to 1. "
        "Smalltalk must produce zero items. Return only one JSON object, with "
        "no markdown fences or text outside the JSON. Example for durable "
        'information: {"items":[{"namespace":"preferences","content":'
        '"mi color favorito es el verde","confidence":0.9,'
        '"mentions":[]}]}. Example for smalltalk: {"items":[]}.\n\n'
        f"USER:\n{user_prompt}\n\nASSISTANT:\n{assistant_response}"
    )


def _parse_extraction(response: str) -> list[dict[str, Any]]:
    cleaned = response.replace("```json", "").replace("```JSON", "")
    cleaned = cleaned.replace("```", "")
    decoder = json.JSONDecoder()
    data = None
    offset = 0
    while True:
        start = cleaned.find("{", offset)
        if start < 0:
            break
        try:
            candidate, _ = decoder.raw_decode(cleaned, start)
        except json.JSONDecodeError:
            offset = start + 1
            continue
        if isinstance(candidate, dict):
            data = candidate
            break
        offset = start + 1
    if data is None:
        raise json.JSONDecodeError(
            "no se encontro un objeto JSON valido",
            cleaned,
            0,
        )
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
