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
    MemoryType,
    Principal,
    RecallItem,
    RecallQuery,
    RagChunk,
    RagChunkWrite,
    RagIngestResult,
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

    def find_dialogs_to_archive(
        self,
        *,
        now: datetime,
        hot_window_seconds: int,
    ) -> Sequence[Engram]:
        """Lista dialogos activos fuera de la ventana caliente."""

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
    ) -> Sequence[RagChunk]:
        """Recupera chunks activos por similitud y gate opcional de dominio."""

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
