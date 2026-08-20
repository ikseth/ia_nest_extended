"""Fachada unica de la capa: reenvio generico, sobreescritura y lo propio.

Aplica meta ADR 0007 (contrato uniforme):

- REENVIA con un mecanismo GENERICO -uno, no uno por capacidad- lo que esta capa
  no enriquece, en JSON y en `text/event-stream`.
- SOBREESCRIBE `prompt.run`/`prompt.stream`, `reasoning.run`/
  `reasoning.stream` y `task.run`, conservando la forma del core; en tareas, el
  RAG se aplica por subtarea.
- ANADE las capacidades propias `memory_type.*`, `memory.*` y `knowledge.*`.

Todas las pieles (CLI hoy; REST y MCP en la fase 7c) usan esta superficie y no
tienen logica propia.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from .capabilities import (
    OVERRIDDEN_CAPABILITIES,
    OWN_CAPABILITIES,
    extended_version,
    local_catalog,
    merge_forwarded,
)
from .catalog_cache import write_catalog_cache
from .clients import CoreResult, ForwardedJson, ForwardedStream
from .composition import ExtendedComposition
from .config import ExtendedConfig
from .errors import EnrichmentParameterError, ExtendedError, ExtendedRequestError
from .enrichment import compose_prompt
from .identity import resolve_identity
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
    ConsolidationTrigger,
    EngramWrite,
    MemoryClass,
    MemoryIdentity,
    MemoryType,
    Principal,
    RetrievalMode,
    Scope,
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


class _ObservedStream:
    """Observa un SSE sin cambiar ningun evento ni retrasar su entrega."""

    def __init__(
        self,
        downstream: ForwardedStream,
        *,
        capability: str,
        on_complete: Callable[[str, str | None], None],
        on_finish: Callable[[str, str | None], None],
    ) -> None:
        self._downstream = downstream
        self._capability = capability
        self._on_complete = on_complete
        self._on_finish = on_finish
        self._parts: list[str] = []
        self._response: str | None = None
        self._downstream_request_id: str | None = None
        self._done = False
        self._error_event = False
        self._cancelled = False
        self._finished = False
        self.content_type = downstream.content_type
        self.status_code = downstream.status_code

    def __iter__(self) -> Iterator:
        try:
            for event in self._downstream:
                self._observe(event.event, event.data)
                # El evento se entrega inmediatamente. El write-back ocurre
                # solo cuando el iterador del core termina despues de `done`.
                yield event
            if (
                self._done
                and not self._error_event
                and not self._cancelled
                and self._response is not None
            ):
                try:
                    self._on_complete(
                        self._response,
                        self._downstream_request_id,
                    )
                except BaseException:
                    self._finish("error")
                    raise
                self._finish("ok")
            else:
                self._finish("error" if self._error_event else "interrupted")
        except GeneratorExit:
            self._cancelled = True
            self._finish("interrupted")
            raise
        except BaseException:
            self._finish("error")
            raise
        finally:
            self._downstream.close()

    def close(self) -> None:
        # REST llama aqui cuando el cliente se desconecta; si el iterador no
        # llego al cierre limpio no se ejecuta nunca `on_complete`.
        self._cancelled = True
        if not self._finished:
            self._finish("interrupted")
        self._downstream.close()

    def _observe(self, event_name: str | None, raw_data: str) -> None:
        try:
            envelope = json.loads(raw_data)
        except (TypeError, json.JSONDecodeError):
            return
        if not isinstance(envelope, dict):
            return
        event_type = event_name or envelope.get("type")
        data = envelope.get("data", envelope)
        if not isinstance(data, dict):
            return
        if event_type == "error":
            self._error_event = True
            return
        if self._capability == "prompt.stream" and event_type == "token":
            text = data.get("text")
            if isinstance(text, str):
                self._parts.append(text)
            return
        if event_type != "done":
            return
        if self._capability == "prompt.stream":
            text = data.get("text")
            self._response = text if isinstance(text, str) else "".join(self._parts)
            # Limitacion conocida: prompt.stream no emite la traza del core.
            self._downstream_request_id = None
        else:
            output = data.get("output")
            trace = data.get("trace")
            if not isinstance(output, str) or not isinstance(trace, dict):
                return
            request_id = trace.get("request_id")
            if not isinstance(request_id, str) or not request_id:
                return
            self._response = output
            self._downstream_request_id = request_id
        self._done = True

    def _finish(self, status: str) -> None:
        if self._finished:
            return
        self._finished = True
        self._on_finish(status, self._downstream_request_id)


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
        payload: Any = None,
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

    def invoke(
        self,
        capability: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        """Invoca una capacidad local desde cualquier piel.

        La traduccion del payload publico a los modelos del servicio vive aqui,
        no en REST. La CLI llama a los mismos metodos de esta fachada.
        """
        body = {} if payload is None else payload
        if not isinstance(body, dict):
            raise ExtendedRequestError(
                "el cuerpo de la peticion debe ser un objeto JSON",
                "body",
            )
        if capability == "capability.list":
            return self.capability_list()
        if capability == "prompt.run":
            result = self.prompt_run(
                _required_text(body, "prompt"),
                self._request_identity(body),
                enrich=_optional_bool(body, "enrich"),
                use_memory=_optional_bool(body, "use_memory"),
                use_rag=_optional_bool(body, "use_rag"),
                write_back=_optional_bool(body, "write_back"),
                domain=_optional_text(body, "domain"),
                auto_domain=_optional_bool(body, "auto_domain"),
                model=_optional_text(body, "model"),
                dry_run=_bool(body, "dry_run", False),
            )
            return _run_payload(result)
        if capability == "prompt.stream":
            return self.prompt_stream(
                _required_text(body, "prompt"),
                self._request_identity(body),
                enrich=_optional_bool(body, "enrich"),
                use_memory=_optional_bool(body, "use_memory"),
                use_rag=_optional_bool(body, "use_rag"),
                write_back=_optional_bool(body, "write_back"),
                domain=_optional_text(body, "domain"),
                auto_domain=_optional_bool(body, "auto_domain"),
                model=_optional_text(body, "model"),
            )
        if capability == "reasoning.run":
            result = self.reasoning_run(
                _required_text(body, "prompt"),
                self._request_identity(body),
                enrich=_optional_bool(body, "enrich"),
                use_memory=_optional_bool(body, "use_memory"),
                use_rag=_optional_bool(body, "use_rag"),
                write_back=_optional_bool(body, "write_back"),
                domain=_optional_text(body, "domain"),
                auto_domain=_optional_bool(body, "auto_domain"),
                model=_optional_text(body, "model"),
                dry_run=_bool(body, "dry_run", False),
            )
            return _run_payload(result)
        if capability == "reasoning.stream":
            return self.reasoning_stream(
                _required_text(body, "prompt"),
                self._request_identity(body),
                enrich=_optional_bool(body, "enrich"),
                use_memory=_optional_bool(body, "use_memory"),
                use_rag=_optional_bool(body, "use_rag"),
                write_back=_optional_bool(body, "write_back"),
                domain=_optional_text(body, "domain"),
                auto_domain=_optional_bool(body, "auto_domain"),
                model=_optional_text(body, "model"),
            )
        if capability == "task.run":
            result = self.task_run(
                _required_text(body, "prompt"),
                self._request_identity(body),
                enrich=_optional_bool(body, "enrich"),
                use_memory=_optional_bool(body, "use_memory"),
                use_rag=_optional_bool(body, "use_rag"),
                write_back=_optional_bool(body, "write_back"),
                domain=_optional_text(body, "domain"),
                effort=_optional_text(body, "effort"),
                plan_payload=_task_plan_payload(body),
            )
            return result.payload
        if capability == "memory_type.list":
            return self.memory_type_list()
        if capability == "memory_type.validate":
            return self.memory_type_validate(
                _memory_type(_required_object(body, "memory_type"))
            )
        if capability == "memory.recall":
            return self.memory_recall(
                self._request_identity(body),
                _required_text(body, "prompt"),
                use_memory=_optional_bool(body, "use_memory"),
                use_rag=_optional_bool(body, "use_rag"),
            )
        if capability == "memory.write":
            return self.memory_write(
                _principal(_required_text(body, "principal")),
                _engram_write(_required_object(body, "request")),
            )
        if capability == "memory.consolidate":
            return self.memory_consolidate(
                _consolidation_event(_required_object(body, "event"))
            )
        if capability == "memory.maintain":
            return self.memory_maintain(dry_run=_bool(body, "dry_run", False))
        if capability == "knowledge.ingest":
            return self.knowledge_ingest(
                path=Path(_required_text(body, "path")),
                corpus_name=_required_text(body, "corpus"),
                domains=_text_tuple(body.get("domain", ()), "domain"),
                source_ref=_optional_text(body, "source_ref"),
            )
        if capability == "knowledge.status":
            return self.knowledge_status()
        if capability == "knowledge.suggest":
            return self.knowledge_suggest(_required_text(body, "corpus"))
        if capability == "knowledge.confirm":
            return self.knowledge_confirm(
                _required_text(body, "corpus"),
                _required_text(body, "domain"),
            )
        if capability == "knowledge.reject":
            return self.knowledge_reject(
                _required_text(body, "corpus"),
                _required_text(body, "domain"),
            )
        raise ExtendedRequestError(
            f"la capacidad local '{capability}' no esta implementada",
            "capability",
        )

    def _request_identity(self, body: dict[str, Any]) -> MemoryIdentity:
        raw = body.get("identity", {})
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            raise ExtendedRequestError("identity debe ser un objeto", "identity")
        return resolve_identity(
            self.config,
            user_id=_identity_text(raw, "user_id"),
            session_id=_identity_text(raw, "session_id"),
            service=_identity_text(raw, "service"),
            namespace=_identity_text(raw, "namespace"),
            domain=_identity_text(raw, "domain_tag"),
        )

    # --- capacidad sobreescrita -------------------------------------------

    def capability_list(self) -> dict[str, Any]:
        """Compone el catalogo local con el obtenido del core en ejecucion.

        Las entradas ajenas son opacas: solo se usa su nombre para resolver una
        sobreescritura y se anade `provenance`. Si el core no responde, el
        catalogo local sigue disponible junto al error tipado que explica la
        degradacion.

        Efecto secundario, y es el punto: deja la cache local del catalogo
        remoto actualizada. Es la unica via de refresco -el parser SOLO la
        lee, nunca consulta la red (docs/handoff/herencia_parametros_retrabajo.md).
        """
        local = local_catalog()
        try:
            downstream = self._composition.core().list_capabilities()
        except ExtendedError as exc:
            return {
                "extended_version": extended_version(),
                "core_version": None,
                "capabilities": local,
                "error": exc.to_dict(),
            }

        write_catalog_cache(
            self.config.catalog_cache_path,
            core_url=self.config.core_url,
            core_version=downstream["core_version"],
            capabilities=downstream["capabilities"],
        )
        return {
            "extended_version": extended_version(),
            "core_version": downstream["core_version"],
            "capabilities": merge_forwarded(local, downstream["capabilities"]),
        }

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

    def prompt_stream(
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
    ) -> _ObservedStream:
        return self._inference_stream(
            "prompt.stream",
            prompt,
            identity,
            enrich=enrich,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            domain=domain,
            auto_domain=auto_domain,
            model=model,
        )

    def reasoning_stream(
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
    ) -> _ObservedStream:
        return self._inference_stream(
            "reasoning.stream",
            prompt,
            identity,
            enrich=enrich,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            domain=domain,
            auto_domain=auto_domain,
            model=model,
        )

    def _inference_stream(
        self,
        capability: str,
        prompt: str,
        identity: MemoryIdentity,
        *,
        enrich: bool | None,
        use_memory: bool | None,
        use_rag: bool | None,
        write_back: bool | None,
        domain: str | None,
        auto_domain: bool | None,
        model: str | None,
    ) -> _ObservedStream:
        plan = self.plan_enrichment(
            enrich=enrich,
            use_memory=use_memory,
            use_rag=use_rag,
            write_back=write_back,
            domain=domain,
            auto_domain=auto_domain,
            model=model,
        )
        request_identity = (
            replace(identity, domain_tag=plan.domain)
            if plan.domain is not None
            else identity
        )
        request_id = str(uuid4())
        started = time.monotonic()
        enricher = None
        prepared = None
        try:
            if plan.enrich:
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
                prepared = enricher.prepare(
                    request_identity,
                    prompt,
                    use_memory=plan.use_memory,
                    use_rag=plan.use_rag,
                    auto_domain=plan.auto_domain,
                    request_id=request_id,
                )
                request_identity = prepared.identity
                outbound_prompt = prepared.enriched_prompt
            else:
                outbound_prompt = prompt

            core = self._composition.core()
            open_stream = (
                core.prompt_stream
                if capability == "prompt.stream"
                else core.reasoning_stream
            )
            downstream = open_stream(
                outbound_prompt,
                request_identity,
                model=plan.model,
                domain=request_identity.domain_tag,
            )
        except Exception:
            if enricher is not None and prepared is not None:
                enricher.record_recall(prepared, status="error")
            self._record_run(
                event=capability,
                request_id=request_id,
                downstream_request_id=None,
                identity=request_identity,
                plan=plan,
                started=started,
                status="error",
            )
            raise

        if enricher is not None and prepared is not None:
            enricher.record_recall(prepared, status="ok")

        def complete(response: str, downstream_request_id: str | None) -> None:
            if not plan.write_back:
                return
            assert enricher is not None
            trace = (
                {"request_id": downstream_request_id}
                if downstream_request_id is not None
                else {}
            )
            enricher.write_back(
                request_id=request_id,
                identity=request_identity,
                prompt=prompt,
                core_result=CoreResult(response=response, trace=trace),
                # prompt.stream no emite trace; el nulo es deliberado y nunca
                # se sustituye por el request_id propio de esta capa.
                source_trace_id=downstream_request_id,
            )

        def finish(status: str, downstream_request_id: str | None) -> None:
            self._record_run(
                event=capability,
                request_id=request_id,
                downstream_request_id=downstream_request_id,
                identity=request_identity,
                plan=plan,
                started=started,
                status=status,
            )

        return _ObservedStream(
            downstream,
            capability=capability,
            on_complete=complete,
            on_finish=finish,
        )

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
        plan_payload: dict[str, object] | None = None,
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
                    plan_payload=plan_payload,
                    effort=None if plan_payload is not None else effort,
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
            if plan_payload is None:
                planned = self._composition.core().task_plan(
                    prompt,
                    identity,
                    effort=effort,
                )
                supplied_plan = dict(planned.payload)
            else:
                supplied_plan = dict(plan_payload)
            supplied_plan.pop("params", None)
            plan_payload = supplied_plan
            enriched_plan = []
            raw_plan = plan_payload.get("plan")
            if not isinstance(raw_plan, list):
                raise EnrichmentParameterError(
                    "el plan suministrado debe contener una lista 'plan'",
                    "plan",
                )
            for original in raw_plan:
                if not isinstance(original, dict):
                    raise EnrichmentParameterError(
                        "el plan suministrado contiene una subtarea invalida",
                        "plan",
                    )
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
                    min_score=config.rag_min_score,
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


def _run_payload(result: PromptRunResult | ReasoningRunResult) -> dict[str, Any]:
    if not result.dry_run:
        return result.payload
    return {
        "request_id": result.request_id,
        "enriched_prompt": result.enriched_prompt,
        "context": result.context,
        "dry_run": True,
    }


def _required_object(body: dict[str, Any], name: str) -> dict[str, Any]:
    value = body.get(name)
    if not isinstance(value, dict):
        raise ExtendedRequestError(f"'{name}' debe ser un objeto", name)
    return value


def _required_text(body: dict[str, Any], name: str) -> str:
    value = body.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ExtendedRequestError(f"'{name}' debe ser texto no vacio", name)
    return value


def _optional_text(body: dict[str, Any], name: str) -> str | None:
    value = body.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ExtendedRequestError(f"'{name}' debe ser texto", name)
    return value


def _identity_text(body: dict[str, Any], name: str) -> str | None:
    return _optional_text(body, name)


def _optional_bool(body: dict[str, Any], name: str) -> bool | None:
    if name not in body or body[name] is None:
        return None
    return _bool(body, name, False)


def _bool(body: dict[str, Any], name: str, default: bool) -> bool:
    value = body.get(name, default)
    if not isinstance(value, bool):
        raise ExtendedRequestError(f"'{name}' debe ser booleano", name)
    return value


def _text_tuple(value: Any, name: str) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise ExtendedRequestError(
            f"'{name}' debe ser texto o una lista de textos",
            name,
        )
    return tuple(value)


def _enum(enum_type, value: Any, name: str):
    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ExtendedRequestError(f"'{name}' tiene un valor invalido", name) from exc


def _principal(value: str) -> Principal:
    return _enum(Principal, value, "principal")


def _uuid_tuple(value: Any, name: str) -> tuple[UUID, ...]:
    raw = _text_tuple(value, name)
    try:
        return tuple(UUID(item) for item in raw)
    except ValueError as exc:
        raise ExtendedRequestError(f"'{name}' contiene un UUID invalido", name) from exc


def _memory_identity(raw: Any) -> MemoryIdentity:
    if raw is None:
        return MemoryIdentity()
    if not isinstance(raw, dict):
        raise ExtendedRequestError("'identity' debe ser un objeto", "identity")
    return MemoryIdentity(
        user_id=_identity_text(raw, "user_id"),
        session_id=_identity_text(raw, "session_id"),
        service=_identity_text(raw, "service"),
        domain_tag=_identity_text(raw, "domain_tag"),
        namespace=_identity_text(raw, "namespace"),
    )


def _memory_type(raw: dict[str, Any]) -> MemoryType:
    try:
        return MemoryType(
            name=_required_text(raw, "name"),
            memory_class=_enum(MemoryClass, raw.get("memory_class"), "memory_class"),
            writer_principal=_enum(Principal, raw.get("writer_principal"), "writer_principal"),
            retrieval_mode=_enum(RetrievalMode, raw.get("retrieval_mode"), "retrieval_mode"),
            scope=_enum(Scope, raw.get("scope"), "scope"),
            namespaces=_text_tuple(raw.get("namespaces", ()), "namespaces"),
            w_recency=raw.get("w_recency"),
            w_similarity=raw.get("w_similarity"),
            w_stability=raw.get("w_stability"),
            w_score=raw.get("w_score"),
            half_life_seconds=raw.get("half_life_seconds"),
            status=raw.get("status", "active"),
            version=raw.get("version", 1),
        )
    except TypeError as exc:
        raise ExtendedRequestError("declaracion memory_type invalida", "memory_type") from exc


def _engram_write(raw: dict[str, Any]) -> EngramWrite:
    try:
        return EngramWrite(
            type_name=_required_text(raw, "type_name"),
            content=_required_text(raw, "content"),
            identity=_memory_identity(raw.get("identity")),
            namespace=_optional_text(raw, "namespace"),
            score=raw.get("score", 0.0),
            stability=raw.get("stability", 0),
            service=_optional_text(raw, "service"),
            domain_tag=_optional_text(raw, "domain_tag"),
            entity_refs=_uuid_tuple(raw.get("entity_refs", ()), "entity_refs"),
            unresolved_mentions=_text_tuple(
                raw.get("unresolved_mentions", ()), "unresolved_mentions"
            ),
            source_trace_id=_optional_text(raw, "source_trace_id"),
            entity_id=(
                None
                if raw.get("entity_id") is None
                else UUID(_required_text(raw, "entity_id"))
            ),
        )
    except (TypeError, ValueError) as exc:
        raise ExtendedRequestError("peticion memory.write invalida", "request") from exc


def _consolidation_event(raw: dict[str, Any]) -> ConsolidationEvent:
    try:
        return ConsolidationEvent(
            trigger=_enum(ConsolidationTrigger, raw.get("trigger"), "trigger"),
            principal=_enum(Principal, raw.get("principal"), "principal"),
            source_ids=_uuid_tuple(raw.get("source_ids", ()), "source_ids"),
            target_type=_optional_text(raw, "target_type"),
            content=_optional_text(raw, "content"),
            target_namespace=_optional_text(raw, "target_namespace"),
            reason=_required_text(raw, "reason"),
        )
    except TypeError as exc:
        raise ExtendedRequestError(
            "evento memory.consolidate invalido",
            "event",
        ) from exc


def _task_plan_payload(body: dict[str, Any]) -> dict[str, Any] | None:
    if "plan" not in body:
        return None
    extension_fields = {
        "prompt",
        "identity",
        "enrich",
        "use_memory",
        "use_rag",
        "write_back",
        "domain",
    }
    # El objeto de task.plan es opaco salvo por plan[].prompt: conserva tambien
    # campos hermanos que una version futura del core pueda anadir.
    return {
        name: value
        for name, value in body.items()
        if name not in extension_fields
    }
