"""Sustrato de memoria de ia_nest_extended."""

from .embedders import FakeEmbedder
from .errors import (
    AliasedDeclarationError,
    AliasedTierError,
    EngramNotFoundError,
    InvalidEmbeddingDimensionError,
    InvalidEngramError,
    InvalidMemoryTypeError,
    InvalidNamespaceError,
    ScopeViolationError,
    UnknownMemoryTypeError,
    UnsupportedWriteError,
    WriteAuthorityError,
)
from .models import (
    Engram,
    EngramStatus,
    EngramWrite,
    EntityProfile,
    MemoryClass,
    MemoryIdentity,
    MemoryKey,
    MemoryType,
    Principal,
    RecallItem,
    RecallQuery,
    RetrievalMode,
    Scope,
)
from .registry import MemoryTypeRegistry, seed_memory_types
from .ranking import calculate_relevance

__all__ = [
    "AliasedDeclarationError",
    "AliasedTierError",
    "Engram",
    "EngramNotFoundError",
    "EngramStatus",
    "EngramWrite",
    "EntityProfile",
    "FakeEmbedder",
    "InvalidEmbeddingDimensionError",
    "InvalidEngramError",
    "InvalidMemoryTypeError",
    "InvalidNamespaceError",
    "MemoryClass",
    "MemoryIdentity",
    "MemoryKey",
    "MemoryType",
    "MemoryTypeRegistry",
    "Principal",
    "RecallItem",
    "RecallQuery",
    "RetrievalMode",
    "Scope",
    "ScopeViolationError",
    "UnknownMemoryTypeError",
    "UnsupportedWriteError",
    "WriteAuthorityError",
    "calculate_relevance",
    "seed_memory_types",
]
