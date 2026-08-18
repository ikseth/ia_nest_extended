"""Fachada unica de la capa: reenvio generico, sobreescritura y lo propio.

Aplica meta ADR 0007 (contrato uniforme):

- REENVIA con un mecanismo GENERICO -uno, no uno por capacidad- lo que esta capa
  no enriquece, en JSON y en `text/event-stream`.
- SOBREESCRIBE `prompt.run`, `reasoning.run` y `task.run`, conservando la forma
  de respuesta del core; en tareas, el RAG se aplica por subtarea.
- ANADE las capacidades propias `memory_type.*`, `memory.*` y `knowledge.*`.

Todas las pieles (CLI hoy; REST y MCP en la fase 7c) usan esta superficie y no
tienen logica propia.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from .capabilities import OVERRIDDEN_CAPABILITIES, OWN_CAPABILITIES
from .clients import ForwardedJson, ForwardedStream
from .composition import ExtendedComposition
from .config import ExtendedConfig
from .errors import EnrichmentParameterError, ExtendedError
from .enrichment import compose_prompt
from .ingest import ingest_path
from .knowledge import (
    confirm_domain,
    knowledge_status,
    reject_domain,
    suggest_domains,
)
from .maintain import run_maintenance
from .models import (
    ConsolidationEvent,
    EngramWrite,
    MemoryIdentity,
    MemoryType,
    Principal,
)
from .registry import MemoryTypeRegistry


@dataclass(frozen=True, slots=True)
class PromptRunResult:
    """La respuesta del core, intacta, mas lo que solo la capa conoce."""

    payload: dict[str, Any]
    request_id: str
    context: str = ""
    enriched_prompt: str = ""
    enriched: bool = True
    dry_run: bool = False
    downstream_request_id: str | None = None

    @property
    def response(self) -> str:
        value = self.payload.get("response")
        return "" if value is None else str(value)


@dataclass(frozen=True, slots=True)
class ReasoningRunResult:
    """Respuesta intacta de `reasoning.run` y metadatos internos de capa."""

    payload: dict[str, Any]
    request_id: str
    context: str = ""
    enriched_prompt: str = ""
    enriched: bool = True
    dry_run: bool = False
    downstream_request_id: str | None = None

    @property
    def output(self) -> str:
        value = self.payload.get("output")
        return "" if value is None else str(value)


@dataclass(frozen=True, slots=True)
class TaskRunResult:
    """Respuesta intacta de `task.run` y contabilidad propia de enriquecimiento."""

    payload: dict[str, Any]
    request_id: str
    enriched: bool
    downstream_request_id: str | None = None
    subtasks_enriched: int = 0
    context: str = ""

    @property
    def response(self) -> str:
        value = self.payload.get("response")
        return "" if value is None else str(value)


@dataclass(frozen=True, slots=True)
class EnrichmentPlan:
    """Valores efectivos de las banderas de enriquecimiento de una peticion."""

    enrich: bool
    use_memory: bool
    use_rag: bool
    write_back: bool
    auto_domain: bool
    domain: str | None = None
    model: str | None = None
    counters: dict[str, int] = field(default_factory=dict)


class _UnavailableMemoryStore:
    """Sustituto explicito cuando la operacion no toca memoria."""

    def __getattr__(self, name: str):
        def _fail(*args, **kwargs):
            raise ExtendedError(
                "esta peticion no habilito memoria; "
                f"no puede invocar '{name}'",
                "use_memory",
            )

        return _fail


class ExtendedService:
    """Superficie unica que usan todas las pieles."""

    def __init__(self, composition: ExtendedComposition) -> None:
        self._composition = composition

    @classmethod
    def from_config(cls, config: ExtendedConfig) -> ExtendedService:
        return cls(ExtendedComposition(config))

    @property
    def config(self) -> ExtendedConfig:
        return self._composition.config

    # --- reenvio generico --------------------------------------------------

    def forward(
        self,
        capability: str,
        payload: dict[str, Any] | None = None,
        *,
        method: str | None = None,
    ) -> ForwardedJson | ForwardedStream:
        """Reenvia al core cualquier capacidad que esta capa no sobreescriba.

        Sin codigo por capacidad y sin `if` por nombre: una capacidad que el
        core anada es alcanzable a traves de esta capa sin tocar su codigo.
        """
        name = capability.strip()
        if name in OVERRIDDEN_CAPABILITIES:
            raise ExtendedError(
                f"'{name}' esta sobreescrita por esta capa; "
                "usa su metodo propio en lugar del reenvio",
                "capability",
            )
        if name in OWN_CAPABILITIES:
            raise ExtendedError(
                f"'{name}' es una capacidad propia de esta capa; no se reenvia",
                "capability",
            )
        return self._composition.core().forward(name, payload, method=method)

    # --- capacidad sobreescrita -------------------------------------------

    def prompt_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        *,
        enrich: bool | None = None,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
        write_back: bool | None = None,
        domain: str | None = None,
        auto_domain: bool | None = None,
        model: str | None = None,
        dry_run: bool = False,
    ) -> PromptRunResult:
        plan = self.plan_enrichment(
            enrich=enrich,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            domain=domain,
            auto_domain=auto_domain,
            model=model,
        )
        request_identity = identity
        if plan.domain is not None:
            request_identity = MemoryIdentity(
                user_id=identity.user_id,
                session_id=identity.session_id,
                service=identity.service,
                domain_tag=plan.domain,
                namespace=identity.namespace,
            )
        if not plan.enrich:
            return self._passthrough(request_identity, prompt, plan, dry_run)
        return self._enriched(request_identity, prompt, plan, dry_run)

    def reasoning_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        *,
        enrich: bool | None = None,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
        write_back: bool | None = None,
        domain: str | None = None,
        auto_domain: bool | None = None,
        model: str | None = None,
        dry_run: bool = False,
    ) -> ReasoningRunResult:
        plan = self.plan_enrichment(
            enrich=enrich,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            domain=domain,
            auto_domain=auto_domain,
            model=model,
        )
        request_identity = identity
        if plan.domain is not None:
            request_identity = replace(identity, domain_tag=plan.domain)
        request_id = str(uuid4())
        started = time.monotonic()
        if not plan.enrich:
            if dry_run:
                self._record_run(
                    event="reasoning.run",
                    request_id=request_id,
                    downstream_request_id=None,
                    identity=request_identity,
                    plan=plan,
                    started=started,
                    status="dry_run",
                )
                return ReasoningRunResult(
                    payload={},
                    request_id=request_id,
                    enriched_prompt=prompt,
                    enriched=False,
                    dry_run=True,
                )
            try:
                core_result = self._composition.core().reasoning_run(
                    prompt,
                    request_identity,
                    model=plan.model,
                    domain=request_identity.domain_tag,
                )
            except Exception:
                self._record_run(
                    event="reasoning.run",
                    request_id=request_id,
                    downstream_request_id=None,
                    identity=request_identity,
                    plan=plan,
                    started=started,
                    status="error",
                )
                raise
            result = ReasoningRunResult(
                payload=core_result.payload,
                request_id=request_id,
                enriched_prompt=prompt,
                enriched=False,
                downstream_request_id=core_result.request_id,
            )
        else:
            rag_store = self._composition.rag_store() if plan.use_rag else None
            memory_store = (
                self._composition.memory_store()
                if plan.use_memory or plan.write_back
                else _UnavailableMemoryStore()
            )
            enricher = self._composition.enricher(
                memory_store=memory_store,
                rag_store=rag_store,
            )
            try:
                enriched = enricher.enrich_reasoning(
                    request_identity,
                    prompt,
                    use_memory=plan.use_memory,
                    use_rag=plan.use_rag,
                    write_back=plan.write_back,
                    auto_domain=plan.auto_domain,
                    model=plan.model,
                    dry_run=dry_run,
                    request_id=request_id,
                )
            except Exception:
                self._record_run(
                    event="reasoning.run",
                    request_id=request_id,
                    downstream_request_id=None,
                    identity=request_identity,
                    plan=plan,
                    started=started,
                    status="error",
                )
                raise
            result = ReasoningRunResult(
                payload=enriched.payload,
                request_id=request_id,
                context=enriched.context,
                enriched_prompt=enriched.enriched_prompt,
                enriched=True,
                dry_run=dry_run,
                downstream_request_id=enriched.downstream_request_id,
            )
        self._record_run(
            event="reasoning.run",
            request_id=request_id,
            downstream_request_id=result.downstream_request_id,
            identity=request_identity,
            plan=plan,
            started=started,
            status="dry_run" if dry_run else "ok",
        )
        return result

    def task_run(
        self,
        prompt: str,
        identity: MemoryIdentity,
        *,
        enrich: bool | None = None,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
        write_back: bool | None = None,
        domain: str | None = None,
        effort: str | None = None,
    ) -> TaskRunResult:
        plan = self.plan_enrichment(
            enrich=enrich,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            domain=domain,
            auto_domain=False,
            model=None,
        )
        request_id = str(uuid4())
        started = time.monotonic()
        memory_identity = (
            replace(identity, domain_tag=domain) if domain is not None else identity
        )
        if not plan.enrich:
            try:
                core_result = self._composition.core().task_run(
                    prompt,
                    identity,
                    effort=effort,
                )
            except Exception:
                self._record_task_run(
                    request_id=request_id,
                    downstream_request_id=None,
                    identity=memory_identity,
                    plan=plan,
                    started=started,
                    status="error",
                    subtasks_enriched=0,
                )
                raise
            self._record_task_run(
                request_id=request_id,
                downstream_request_id=core_result.request_id,
                identity=memory_identity,
                plan=plan,
                started=started,
                status="ok",
                subtasks_enriched=0,
            )
            return TaskRunResult(
                payload=core_result.payload,
                request_id=request_id,
                enriched=False,
                downstream_request_id=core_result.request_id,
            )

        rag_store = self._composition.rag_store() if plan.use_rag else None
        memory_store = (
            self._composition.memory_store()
            if plan.use_memory or plan.write_back
            else _UnavailableMemoryStore()
        )
        enricher = self._composition.enricher(
            memory_store=memory_store,
            rag_store=rag_store,
        )
        subtasks_enriched = 0
        try:
            planned = self._composition.core().task_plan(
                prompt,
                identity,
                effort=effort,
            )
            plan_payload = dict(planned.payload)
            plan_payload.pop("params", None)
            enriched_plan = []
            for original in planned.plan:
                item = dict(original)
                if plan.use_rag:
                    subtask_domain = item["domain"]
                    rag_identity = replace(
                        identity,
                        domain_tag=(
                            None if subtask_domain == "general" else subtask_domain
                        ),
                    )
                    chunks = enricher.retrieve_rag(
                        request_id=request_id,
                        identity=rag_identity,
                        prompt=item["prompt"],
                    )
                    bundle = enricher.recall(
                        rag_identity,
                        item["prompt"],
                        rag=chunks,
                        include_memory=False,
                        token_budget=self.config.rag_max_tokens,
                        rag_token_budget=self.config.rag_max_tokens,
                    )
                    enriched_prompt = compose_prompt(bundle.context, item["prompt"])
                    if enriched_prompt != item["prompt"]:
                        item["prompt"] = enriched_prompt
                        subtasks_enriched += 1
                enriched_plan.append(item)
            plan_payload["plan"] = enriched_plan

            memory_bundle = enricher.recall(
                memory_identity,
                prompt,
                include_memory=plan.use_memory,
            )
            combined_prompt = compose_prompt(memory_bundle.context, prompt)
            core_result = self._composition.core().task_run(
                combined_prompt,
                identity,
                plan_payload=plan_payload,
            )
            if plan.write_back:
                enricher.write_back(
                    request_id=request_id,
                    identity=memory_identity,
                    prompt=prompt,
                    core_result=core_result,
                )
        except Exception:
            self._record_task_run(
                request_id=request_id,
                downstream_request_id=None,
                identity=memory_identity,
                plan=plan,
                started=started,
                status="error",
                subtasks_enriched=subtasks_enriched,
            )
            raise
        self._record_task_run(
            request_id=request_id,
            downstream_request_id=core_result.request_id,
            identity=memory_identity,
            plan=plan,
            started=started,
            status="ok",
            subtasks_enriched=subtasks_enriched,
        )
        return TaskRunResult(
            payload=core_result.payload,
            request_id=request_id,
            enriched=True,
            downstream_request_id=core_result.request_id,
            subtasks_enriched=subtasks_enriched,
            context=memory_bundle.context,
        )

    def plan_enrichment(
        self,
        *,
        enrich: bool | None,
        use_memory: bool | None,
        use_rag: bool | None,
        write_back: bool | None,
        domain: str | None,
        auto_domain: bool | None,
        model: str | None,
    ) -> EnrichmentPlan:
        """Resuelve las banderas: config da DEFAULTS, la peticion hace override.

        Una combinacion contradictoria es error tipado, nunca precedencia
        silenciosa.
        """
        config = self._composition.config
        if domain is not None and auto_domain:
            raise EnrichmentParameterError(
                "no se puede fijar un dominio explicito y pedir "
                "resolucion automatica a la vez",
                "auto_domain",
            )
        if enrich is False:
            for name, value in (
                ("use_memory", use_memory),
                ("use_rag", use_rag),
                ("write_back", write_back),
            ):
                if value is True:
                    raise EnrichmentParameterError(
                        "enriquecimiento desactivado junto a "
                        f"'{name}' activado",
                        name,
                    )
            return EnrichmentPlan(
                enrich=False,
                use_memory=False,
                use_rag=False,
                write_back=False,
                auto_domain=False,
                domain=domain,
                model=model,
            )
        enrich_effective = config.enrich_enabled if enrich is None else enrich
        if not enrich_effective:
            return EnrichmentPlan(
                enrich=False,
                use_memory=False,
                use_rag=False,
                write_back=False,
                auto_domain=False,
                domain=domain,
                model=model,
            )
        return EnrichmentPlan(
            enrich=True,
            use_memory=(
                config.memory_enabled if use_memory is None else use_memory
            ),
            use_rag=config.rag_enabled if use_rag is None else use_rag,
            write_back=(
                config.write_back_enabled if write_back is None else write_back
            ),
            auto_domain=(
                config.auto_domain if auto_domain is None else auto_domain
            ),
            domain=domain,
            model=model,
        )

    def _passthrough(
        self,
        identity: MemoryIdentity,
        prompt: str,
        plan: EnrichmentPlan,
        dry_run: bool,
    ) -> PromptRunResult:
        request_id = str(uuid4())
        started = time.monotonic()
        if dry_run:
            self._record_prompt_run(
                request_id=request_id,
                downstream_request_id=None,
                identity=identity,
                plan=plan,
                started=started,
                status="dry_run",
            )
            return PromptRunResult(
                payload={},
                request_id=request_id,
                enriched_prompt=prompt,
                enriched=False,
                dry_run=True,
            )
        try:
            result = self._composition.core().prompt_run(
                prompt,
                identity,
                model=plan.model,
                domain=identity.domain_tag,
            )
        except Exception:
            self._record_prompt_run(
                request_id=request_id,
                downstream_request_id=None,
                identity=identity,
                plan=plan,
                started=started,
                status="error",
            )
            raise
        self._record_prompt_run(
            request_id=request_id,
            downstream_request_id=result.request_id,
            identity=identity,
            plan=plan,
            started=started,
            status="ok",
        )
        return PromptRunResult(
            payload=result.payload,
            request_id=request_id,
            enriched_prompt=prompt,
            enriched=False,
            downstream_request_id=result.request_id,
        )

    def _enriched(
        self,
        identity: MemoryIdentity,
        prompt: str,
        plan: EnrichmentPlan,
        dry_run: bool,
    ) -> PromptRunResult:
        request_id = str(uuid4())
        started = time.monotonic()
        rag_store = self._composition.rag_store() if plan.use_rag else None
        if plan.use_memory or plan.write_back:
            memory_store = self._composition.memory_store()
        else:
            memory_store = _UnavailableMemoryStore()
        enricher = self._composition.enricher(
            memory_store=memory_store,
            rag_store=rag_store,
        )
        try:
            result = enricher.enrich(
                identity,
                prompt,
                use_memory=plan.use_memory,
                use_rag=plan.use_rag,
                write_back=plan.write_back,
                auto_domain=plan.auto_domain,
                model=plan.model,
                dry_run=dry_run,
                request_id=request_id,
            )
        except Exception:
            self._record_prompt_run(
                request_id=request_id,
                downstream_request_id=None,
                identity=identity,
                plan=plan,
                started=started,
                status="error",
            )
            raise
        self._record_prompt_run(
            request_id=request_id,
            downstream_request_id=result.downstream_request_id,
            identity=identity,
            plan=plan,
            started=started,
            status="dry_run" if dry_run else "ok",
        )
        return PromptRunResult(
            payload=result.payload,
            request_id=request_id,
            context=result.context,
            enriched_prompt=result.enriched_prompt,
            enriched=True,
            dry_run=dry_run,
            downstream_request_id=result.downstream_request_id,
        )

    def _record_prompt_run(
        self,
        *,
        request_id: str,
        downstream_request_id: str | None,
        identity: MemoryIdentity,
        plan: EnrichmentPlan,
        started: float,
        status: str,
    ) -> None:
        self._record_run(
            event="prompt.run",
            request_id=request_id,
            downstream_request_id=downstream_request_id,
            identity=identity,
            plan=plan,
            started=started,
            status=status,
        )

    def _record_run(
        self,
        *,
        event: str,
        request_id: str,
        downstream_request_id: str | None,
        identity: MemoryIdentity,
        plan: EnrichmentPlan,
        started: float,
        status: str,
    ) -> None:
        self._composition.telemetry().record(
            event=event,
            request_id=request_id,
            downstream_request_id=downstream_request_id,
            identity=identity,
            counters={
                "enrich": int(plan.enrich),
                "use_memory": int(plan.use_memory),
                "use_rag": int(plan.use_rag),
                "write_back": int(plan.write_back),
            },
            latency_ms=max(0, round((time.monotonic() - started) * 1000)),
            status=status,
        )

    def _record_task_run(
        self,
        *,
        request_id: str,
        downstream_request_id: str | None,
        identity: MemoryIdentity,
        plan: EnrichmentPlan,
        started: float,
        status: str,
        subtasks_enriched: int,
    ) -> None:
        self._composition.telemetry().record(
            event="task.run",
            request_id=request_id,
            downstream_request_id=downstream_request_id,
            identity=identity,
            counters={
                "enrich": int(plan.enrich),
                "use_memory": int(plan.use_memory),
                "use_rag": int(plan.use_rag),
                "write_back": int(plan.write_back),
                "subtasks_enriched": subtasks_enriched,
            },
            latency_ms=max(0, round((time.monotonic() - started) * 1000)),
            status=status,
        )

    # --- capacidades propias: memoria -------------------------------------

    def memory_type_list(self) -> dict[str, Any]:
        store = self._composition.memory_store()
        return {
            "types": [
                _memory_type_dict(memory_type) for memory_type in store.list_types()
            ]
        }

    def memory_type_validate(self, memory_type: MemoryType) -> dict[str, Any]:
        store = self._composition.memory_store()
        registry = MemoryTypeRegistry(
            declared
            for declared in store.list_types()
            if declared.name != memory_type.name
        )
        registry.register(memory_type)
        return {"valid": True, "name": memory_type.name}

    def memory_recall(
        self,
        identity: MemoryIdentity,
        prompt: str,
        *,
        use_memory: bool | None = None,
        use_rag: bool | None = None,
    ) -> dict[str, Any]:
        config = self._composition.config
        memory_on = config.memory_enabled if use_memory is None else use_memory
        rag_on = config.rag_enabled if use_rag is None else use_rag
        rag_store = self._composition.rag_store() if rag_on else None
        memory_store = (
            self._composition.memory_store()
            if memory_on
            else _UnavailableMemoryStore()
        )
        enricher = self._composition.enricher(
            memory_store=memory_store,
            rag_store=rag_store,
        )
        chunks = ()
        if rag_store is not None:
            chunks = tuple(
                rag_store.retrieve(
                    prompt,
                    domain=identity.domain_tag,
                    top_k=config.rag_top_k,
                )
            )
        bundle = enricher.recall(
            identity,
            prompt,
            rag=chunks,
            include_memory=memory_on,
        )
        return {
            "context": bundle.context,
            "counters": {
                "delegated": len(bundle.delegated),
                "rag": len(bundle.rag),
                "semantic": len(bundle.semantic),
                "episodic": len(bundle.episodic),
                "dialog": len(bundle.dialog),
            },
        }

    def memory_write(
        self,
        principal: Principal,
        request: EngramWrite,
    ) -> dict[str, Any]:
        store = self._composition.memory_store()
        engram = store.write(principal, request)
        return {
            "id": str(engram.id),
            "type_name": engram.type_name,
            "namespace": engram.namespace,
            "status": str(engram.status),
        }

    def memory_consolidate(self, event: ConsolidationEvent) -> dict[str, Any]:
        from .consolidation import ConsolidationExecutor

        executor = ConsolidationExecutor(
            store=self._composition.memory_store(),
            telemetry=self._composition.telemetry(),
        )
        result = executor.execute(event)
        return {
            "target_id": None if result.target is None else str(result.target.id),
            "archived_sources": len(result.archived_sources),
            "links_created": result.links_created,
        }

    def memory_maintain(self, *, dry_run: bool = False) -> dict[str, Any]:
        result = run_maintenance(
            store=self._composition.memory_store(),
            telemetry=self._composition.telemetry(),
            config=self._composition.config,
            dry_run=dry_run,
        )
        return {
            "dialog_archived": result.dialog_archived,
            "episodic_promoted": result.episodic_promoted,
            "candidates_seen": result.candidates_seen,
            "dry_run": result.dry_run,
        }

    # --- capacidades propias: conocimiento --------------------------------

    def knowledge_ingest(
        self,
        *,
        path: Path,
        corpus_name: str,
        domains: tuple[str, ...] = (),
        source_ref: str | None = None,
    ) -> dict[str, Any]:
        config = self._composition.config
        result = ingest_path(
            store=self._composition.rag_store(),
            core=self._composition.core(),
            path=path,
            corpus_name=corpus_name,
            domains=domains,
            source_ref=source_ref,
            chunk_tokens=config.rag_chunk_tokens,
            overlap=config.rag_chunk_overlap,
        )
        return {
            "corpus_name": result.corpus_name,
            "domains": list(result.domains),
            "chunks_new": result.inserted,
            "chunks_updated": result.updated,
        }

    def knowledge_status(self) -> dict[str, Any]:
        statuses = knowledge_status(
            store=self._composition.rag_store(),
            core=self._composition.core(),
        )
        return {
            "domains": [
                {
                    "domain": status.domain,
                    "confirmed_corpora": status.confirmed_corpora,
                }
                for status in statuses
            ]
        }

    def knowledge_suggest(self, corpus_name: str) -> dict[str, Any]:
        config = self._composition.config
        suggestions = suggest_domains(
            store=self._composition.rag_store(),
            core=self._composition.core(),
            corpus_name=corpus_name,
            min_confidence=config.rag_suggest_min_confidence,
            sample_chars=config.rag_suggest_sample_chars,
        )
        return {
            "corpus_name": corpus_name,
            "suggestions": [
                {
                    "domain": item.domain,
                    "confidence": item.confidence,
                    "stored": item.stored,
                }
                for item in suggestions
            ],
        }

    def knowledge_confirm(self, corpus_name: str, domain: str) -> dict[str, Any]:
        changed = confirm_domain(
            store=self._composition.rag_store(),
            core=self._composition.core(),
            corpus_name=corpus_name,
            domain=domain,
        )
        return {
            "corpus_name": corpus_name,
            "domain": domain,
            "confirmed": changed,
        }

    def knowledge_reject(self, corpus_name: str, domain: str) -> dict[str, Any]:
        removed = reject_domain(
            store=self._composition.rag_store(),
            core=self._composition.core(),
            corpus_name=corpus_name,
            domain=domain,
        )
        return {
            "corpus_name": corpus_name,
            "domain": domain,
            "rejected": removed,
        }

    # --- administracion de la capa ----------------------------------------

    def runtime_migrate(self) -> dict[str, Any]:
        return self._composition.migrate()


def _memory_type_dict(memory_type: MemoryType) -> dict[str, Any]:
    return {
        "name": memory_type.name,
        "memory_class": str(memory_type.memory_class),
        "writer_principal": str(memory_type.writer_principal),
        "retrieval_mode": str(memory_type.retrieval_mode),
        "scope": str(memory_type.scope),
        "namespaces": list(memory_type.namespaces),
        "status": memory_type.status,
        "version": memory_type.version,
    }
