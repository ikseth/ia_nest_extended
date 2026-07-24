"""Adaptadores de embedding disponibles en fase 2."""

from __future__ import annotations

import hashlib
import math

from .errors import InvalidEmbeddingDimensionError


class FakeEmbedder:
    """Embedding determinista para desarrollo y pruebas."""

    def __init__(self, dimension: int = 16) -> None:
        if dimension <= 0:
            raise InvalidEmbeddingDimensionError(
                "embedding_dimension debe ser mayor que cero"
            )
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed(self, text: str) -> tuple[float, ...]:
        values: list[float] = []
        counter = 0
        while len(values) < self._dimension:
            payload = f"{counter}:{text}".encode()
            digest = hashlib.sha256(payload).digest()
            for byte in digest:
                values.append((byte / 127.5) - 1.0)
                if len(values) == self._dimension:
                    break
            counter += 1

        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            values[0] = 1.0
            norm = 1.0
        return tuple(value / norm for value in values)
