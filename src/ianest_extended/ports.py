"""Puertos intercambiables del sustrato de memoria."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol
from uuid import UUID

from .models import (
    ConsolidationEvent,
    ConsolidationResult,
    Engram,
    EngramWrite,
    EntityProfile,
    MemoryIdentity,
    MemoryType,
    Principal,
    RecallItem,
    RecallQuery,
    RagChunk,
    RagChunkWrite,
    RagIngestResult,
    Session,
    SessionStatus,
    ThreadSynthesisResult,
)


class Embedder(Protocol):
    @property
    def dimension(self) -> int:
        """Dimension fija del vector producido."""

    def embed(self, text: str) -> tuple[float, ...]:
        """Convierte texto en un vector normalizado."""


class MemoryStore(Protocol):
    def migrate(self) -> None:
        """Crea o actualiza el esquema versionado."""

    def verify_schema(self) -> None:
        """Comprueba el esquema sin mutarlo; falla si falta migrar."""

    def register_type(self, memory_type: MemoryType) -> None:
        """Valida y registra un tipo."""

    def list_types(self) -> Sequence[MemoryType]:
        """Devuelve las declaraciones registradas."""

    def write(self, principal: Principal, request: EngramWrite) -> Engram:
        """Escribe un engrama si el principal tiene autoridad."""

    def write_entity(
        self,
        principal: Principal,
        type_name: str,
        entity: EntityProfile,
    ) -> EntityProfile:
        """Crea o versiona un perfil delegado."""

    def recall(self, query: RecallQuery) -> Sequence[RecallItem]:
        """Recupera segun el modo declarado por cada tipo."""

    def archive(
        self,
        principal: Principal,
        engram_id: UUID,
        reason: str,
    ) -> Engram:
        """Archiva sin borrar fisicamente."""

    def get_engram(self, engram_id: UUID) -> Engram:
        """Obtiene un engrama por identificador."""

    def get_session(self, user_id: str, session_id: str) -> Session | None:
        """Obtiene la entidad de sesion por su clave compuesta."""

    def list_sessions(
        self,
        user_id: str,
        status: SessionStatus | None = SessionStatus.ACTIVE,
    ) -> Sequence[Session]:
        """Lista solo las sesiones del usuario, con titulo derivado."""

    def create_session(self, user_id: str, session_id: str) -> Session:
        """Declara una sesion activa nueva o falla si la clave ya existe."""

    def find_similar(
        self,
        *,
        user_id: str,
        namespace: str,
        text: str,
        threshold: float,
    ) -> Engram | None:
        """Busca el episodico activo mas similar en el mismo scope."""

    def reinforce(
        self,
        principal: Principal,
        engram_id: UUID,
    ) -> Engram:
        """Refuerza un engrama sin crear un duplicado."""

    def record_contradiction(
        self,
        principal: Principal,
        *,
        stated_by_user: Engram,
        conflict_threshold: float,
        dedup_threshold: float,
    ) -> Sequence[Engram]:
        """Anota los candidatos del modelo sobre los que el usuario dijo otra cosa.

        No cambia su estado: deja el enlace para que el recall los despriorice
        y los etiquete (ADR 0013).
        """

    def find_thread_synthesis_window(
        self,
        *,
        identity: MemoryIdentity,
        window_turns: int,
    ) -> Sequence[Engram]:
        """Devuelve el hilo acumulado cuando hay N turnos nuevos que sintetizar."""

    def write_thread_summary(
        self,
        principal: Principal,
        *,
        identity: MemoryIdentity,
        content: str,
        source_ids: Sequence[UUID],
        source_trace_id: str | None,
    ) -> ThreadSynthesisResult:
        """Crea una sintesis anclada y sustituye la sintesis activa anterior."""

    def archive_thread_summaries(
        self,
        principal: Principal,
        *,
        sessions: Sequence[tuple[str, str]],
        reason: str,
    ) -> Sequence[Engram]:
        """Archiva sintesis activas cuando muere el dialogo de su sesion."""

    def find_dialogs_to_archive(
        self,
        *,
        now: datetime,
        inactivity_seconds: int,
    ) -> Sequence[Engram]:
        """Lista dialogos de sesiones activas cuyo reloj ha vencido."""

    def archive_inactive_sessions(
        self,
        *,
        now: datetime,
        inactivity_seconds: int,
        reason: str,
    ) -> Sequence[Engram]:
        """Archiva sesiones inactivas y sus dialogos/sintesis atomicamente."""

    def find_episodic_to_promote(
        self,
        *,
        now: datetime,
        recency_max: float,
        min_stability: int,
        min_score: float,
    ) -> Sequence[Engram]:
        """Lista episodicos activos que cumplen recencia y merito."""

    def execute_consolidation(
        self,
        event: ConsolidationEvent,
    ) -> ConsolidationResult:
        """Aplica destino, lineage y archivo en una sola transaccion."""


class RagStore(Protocol):
    def migrate(self) -> None:
        """Crea el esquema RAG sin modificar las tablas de memoria."""

    def verify_schema(self) -> None:
        """Comprueba el esquema RAG sin mutarlo; falla si falta migrar."""

    def ingest(
        self,
        *,
        corpus_name: str,
        domains: Sequence[str],
        chunks: Sequence[RagChunkWrite],
        description: str = "",
    ) -> RagIngestResult:
        """Crea corpus, vinculos manuales y hace upsert de chunks."""

    def retrieve(
        self,
        query_text: str,
        *,
        domain: str | None = None,
        top_k: int = 3,
        min_score: float = 0.0,
    ) -> Sequence[RagChunk]:
        """Recupera chunks activos por similitud y gate opcional de dominio.

        `min_score` es el suelo de similitud (D1): un chunk por debajo no se
        devuelve aunque quede sitio en `top_k`. El default `0.0` es solo para
        llamadas que deliberadamente no quieren suelo (p. ej. pruebas); los
        caminos de produccion deben pasar el suelo resuelto por
        `ExtendedConfig.rag_score_floor` de forma explicita.
        """

    def confirmed_corpus_counts(self, domains: Sequence[str]) -> dict[str, int]:
        """Cuenta corpus activos con vinculo confirmado por dominio."""

    def sample_corpus(self, corpus_name: str, max_chars: int) -> str:
        """Concatena una muestra estable de chunks del corpus."""

    def propose_domain(
        self,
        corpus_name: str,
        domain: str,
        confidence: float,
    ) -> bool:
        """Crea o refresca una propuesta sin pisar curacion protegida."""

    def confirm_domain(self, corpus_name: str, domain: str) -> bool:
        """Confirma un vinculo existente; devuelve si cambio de estado."""

    def reject_domain(self, corpus_name: str, domain: str) -> bool:
        """Elimina solo una propuesta auto no confirmada."""
