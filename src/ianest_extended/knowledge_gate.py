"""Paso cero del RAG: decide si un turno pide conocimiento."""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from .ports import Embedder

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GateDecision:
    """Resultado sustituible de decidir antes de recuperar conocimiento."""

    decision: str
    score: float | None
    threshold: float | None
    nearest: str | None
    embedding: tuple[float, ...] | None = None

    def public_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "score": self.score,
            "threshold": self.threshold,
            "nearest": self.nearest,
        }


class KnowledgeGate:
    """Compara un turno con una senal de cortesia embebida una sola vez."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        enabled: bool,
        threshold: float,
        phrases_file: Path | None = None,
    ) -> None:
        self._embedder = embedder
        self._enabled = enabled
        self._threshold = threshold
        self._phrases_file = phrases_file
        self._phrases: tuple[str, ...] | None = None
        self._phrase_embeddings: tuple[tuple[float, ...], ...] | None = None
        self._lock = threading.Lock()
        self._warned = False

    def decide(self, prompt: str) -> GateDecision:
        """Devuelve `skip` solo con evidencia; cualquier fallo conserva search."""
        if not self._enabled:
            return _not_applied()
        try:
            phrases, phrase_embeddings = self._embedded_phrases()
            embedding = self._embedder.embed(prompt)
            score, nearest = max(
                (
                    _cosine_similarity(embedding, phrase_embedding),
                    phrase,
                )
                for phrase, phrase_embedding in zip(
                    phrases, phrase_embeddings, strict=True
                )
            )
        except Exception as exc:
            self._warn_once(exc)
            return GateDecision(
                decision="error",
                score=None,
                threshold=self._threshold,
                nearest=None,
            )
        return GateDecision(
            decision="skip" if score >= self._threshold else "search",
            score=score,
            threshold=self._threshold,
            nearest=nearest,
            embedding=embedding,
        )

    def _embedded_phrases(
        self,
    ) -> tuple[tuple[str, ...], tuple[tuple[float, ...], ...]]:
        with self._lock:
            if self._phrases is not None and self._phrase_embeddings is not None:
                return self._phrases, self._phrase_embeddings
            phrases = _read_phrases(self._phrases_file)
            embeddings = self._embedder.embed_many(phrases)
            if len(embeddings) != len(phrases):
                raise ValueError("el embedder no devolvio un vector por frase")
            self._phrases = phrases
            self._phrase_embeddings = embeddings
            return phrases, embeddings

    def _warn_once(self, exc: Exception) -> None:
        with self._lock:
            if self._warned:
                return
            self._warned = True
        LOGGER.warning("knowledge gate failed; RAG search will continue: %s", exc)


def not_applied_decision() -> GateDecision:
    """Valor comun cuando el paso cero no participa en una recuperacion."""
    return _not_applied()


def _not_applied() -> GateDecision:
    return GateDecision(
        decision="not_applied",
        score=None,
        threshold=None,
        nearest=None,
    )


def _read_phrases(phrases_file: Path | None) -> tuple[str, ...]:
    path = phrases_file
    if path is None:
        path = Path(files("ianest_extended").joinpath("data/courtesy_es.txt"))
    phrases = tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not phrases:
        raise ValueError("knowledge gate phrases file has no usable phrases")
    return phrases


def _cosine_similarity(
    left: tuple[float, ...],
    right: tuple[float, ...],
) -> float:
    if len(left) != len(right):
        raise ValueError("knowledge gate embeddings have different dimensions")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("knowledge gate embedding is not normalizable")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
