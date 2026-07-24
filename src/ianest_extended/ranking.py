"""Formula de ranking compartida por pruebas y adaptadores."""

from __future__ import annotations

import math

from .errors import InvalidMemoryTypeError
from .models import MemoryType, RetrievalMode


def calculate_relevance(
    memory_type: MemoryType,
    *,
    age_seconds: float,
    similarity: float,
    stability: int,
    score: float,
) -> float:
    """Aplica la formula reconciliada a senales ya normalizadas."""

    if memory_type.retrieval_mode is not RetrievalMode.RANKED:
        raise InvalidMemoryTypeError("calculate_relevance exige un tipo ranked")
    if age_seconds < 0:
        age_seconds = 0.0
    if memory_type.half_life_seconds is None:
        recency = 1.0
    else:
        recency = math.pow(
            0.5,
            age_seconds / memory_type.half_life_seconds,
        )
    normalized_stability = min(max(stability, 0), 10) / 10.0
    normalized_similarity = min(max(similarity, -1.0), 1.0)
    normalized_score = min(max(score, 0.0), 1.0)
    weights = memory_type.weight_vector
    assert all(weight is not None for weight in weights)
    w_recency, w_similarity, w_stability, w_score = weights
    assert w_recency is not None
    assert w_similarity is not None
    assert w_stability is not None
    assert w_score is not None
    return (
        w_recency * recency
        + w_similarity * normalized_similarity
        + w_stability * normalized_stability
        + w_score * normalized_score
    )
