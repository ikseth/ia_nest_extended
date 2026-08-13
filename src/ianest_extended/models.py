"""Modelos de dominio del registro y los engramas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class MemoryClass(StrEnum):
    STRICT = "strict"
    DELEGATED = "delegated"


class Principal(StrEnum):
    EXTENDED = "extended"
    CONSCIENCE = "conscience"


class RetrievalMode(StrEnum):
    RANKED = "ranked"
    ALWAYS_INJECT = "always_inject"
    PROFILE_LOOKUP = "profile_lookup"


class Scope(StrEnum):
    SESSION = "session"
    USER = "user"
    ENTITY = "entity"
    GLOBAL = "global"


class EngramStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class ConsolidationTrigger(StrEnum):
    DECAY = "decay"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class MemoryType:
    name: str
    memory_class: MemoryClass
    writer_principal: Principal
    retrieval_mode: RetrievalMode
    scope: Scope
    namespaces: tuple[str, ...] = ()
    w_recency: float | None = None
    w_similarity: float | None = None
    w_stability: float | None = None
    w_score: float | None = None
    half_life_seconds: int | None = None
    status: str = "active"
    version: int = 1

    @property
    def weight_vector(self) -> tuple[float | None, ...]:
        return (
            self.w_recency,
            self.w_similarity,
            self.w_stability,
            self.w_score,
        )

    @property
    def declaration_axes(self) -> tuple[object, ...]:
        return (
            self.retrieval_mode,
            self.writer_principal,
            self.scope,
            tuple(sorted(self.namespaces)),
        )


@dataclass(frozen=True, slots=True)
class MemoryIdentity:
    user_id: str | None = None
    session_id: str | None = None
    service: str | None = None
    domain_tag: str | None = None
    namespace: str | None = None

    def to_core_dict(self) -> dict[str, str]:
        return {
            key: value
            for key, value in (
                ("user_id", self.user_id),
                ("service", self.service),
                ("session_id", self.session_id),
                ("domain_tag", self.domain_tag),
                ("namespace", self.namespace),
            )
            if value is not None
        }


@dataclass(frozen=True, slots=True)
class MemoryKey:
    user_id: str | None
    session_id: str | None
    entity_id: UUID | None
    namespace: str | None


@dataclass(frozen=True, slots=True)
class EngramWrite:
    type_name: str
    content: str
    identity: MemoryIdentity = field(default_factory=MemoryIdentity)
    namespace: str | None = None
    score: float = 0.0
    stability: int = 0
    service: str | None = None
    domain_tag: str | None = None
    entity_refs: tuple[UUID, ...] = ()
    unresolved_mentions: tuple[str, ...] = ()
    source_trace_id: str | None = None
    entity_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class Engram:
    id: UUID
    type_name: str
    user_id: str | None
    session_id: str | None
    namespace: str | None
    content: str
    embedding: tuple[float, ...]
    score: float
    stability: int
    service: str | None
    domain_tag: str | None
    entity_refs: tuple[UUID, ...]
    unresolved_mentions: tuple[str, ...]
    status: EngramStatus
    archived_at: datetime | None
    archived_reason: str | None
    source_trace_id: str | None
    version: int
    created_at: datetime
    last_reinforced_at: datetime | None


@dataclass(frozen=True, slots=True)
class EntityProfile:
    id: UUID
    kind: str
    name: str
    aliases: tuple[str, ...] = ()
    profile: dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecallQuery:
    type_names: tuple[str, ...]
    identity: MemoryIdentity = field(default_factory=MemoryIdentity)
    text: str = ""
    namespace: str | None = None
    domain_tag: str | None = None
    entity_ref: UUID | None = None
    entity_id: UUID | None = None
    top_k: int = 10
    now: datetime | None = None


@dataclass(frozen=True, slots=True)
class RecallItem:
    type_name: str
    relevance: float
    engram: Engram | None = None
    entity: EntityProfile | None = None


@dataclass(frozen=True, slots=True)
class ConsolidationEvent:
    trigger: ConsolidationTrigger | str
    principal: Principal
    source_ids: tuple[UUID, ...]
    target_type: str | None
    content: str | None
    target_namespace: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class ConsolidationResult:
    target: Engram | None
    archived_sources: tuple[Engram, ...]
    links_created: int
    identity: MemoryIdentity


@dataclass(frozen=True, slots=True)
class RagChunkWrite:
    content: str
    source_ref: str
    ordinal: int


@dataclass(frozen=True, slots=True)
class RagChunk:
    id: UUID
    corpus_id: UUID
    corpus_name: str
    domains: tuple[str, ...]
    content: str
    source_ref: str
    ordinal: int
    score: float
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RagIngestResult:
    corpus_id: UUID
    corpus_name: str
    domains: tuple[str, ...]
    inserted: int
    updated: int


@dataclass(frozen=True, slots=True)
class KnowledgeDomainStatus:
    domain: str
    confirmed_corpora: int


@dataclass(frozen=True, slots=True)
class KnowledgeSuggestion:
    domain: str
    confidence: float
    stored: bool
