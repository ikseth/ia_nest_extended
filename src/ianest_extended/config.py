"""Configuracion local de ia_nest_extended."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import ExtendedConfigError

PREFIX = "IANEST_EXTENDED_"


@dataclass(frozen=True, slots=True)
class ExtendedConfig:
    core_url: str = "http://127.0.0.1:8000"
    ollama_url: str = "http://127.0.0.1:11434"
    database_dsn: str = (
        "postgresql://ianest:ianest_local@127.0.0.1:55432/ianest_extended"
    )
    embedding_model: str = "bge-m3"
    embedding_dimension: int = 1024
    extraction_model: str = "qwen2.5:7b"
    telemetry_dir: Path = Path("telemetry")
    memory_budget_tokens: int = 1500
    dialog_top_k: int = 6
    episodic_top_k: int = 4
    semantic_top_k: int = 3
    dedup_threshold: float = 0.92
    confidence_threshold: float = 0.7
    request_timeout_seconds: float = 30.0

    @classmethod
    def from_env(
        cls,
        *,
        env_file: str | Path | None = ".env",
    ) -> ExtendedConfig:
        if env_file is not None:
            _load_env_file(Path(env_file))
        defaults = cls()
        values = {
            "core_url": _env("CORE_URL", defaults.core_url),
            "ollama_url": _env("OLLAMA_URL", defaults.ollama_url),
            "database_dsn": _env("DATABASE_DSN", defaults.database_dsn),
            "embedding_model": _env(
                "EMBEDDING_MODEL",
                defaults.embedding_model,
            ),
            "embedding_dimension": _env_int(
                "EMBEDDING_DIMENSION",
                defaults.embedding_dimension,
            ),
            "extraction_model": _env(
                "EXTRACTION_MODEL",
                defaults.extraction_model,
            ),
            "telemetry_dir": Path(
                _env("TELEMETRY_DIR", str(defaults.telemetry_dir))
            ),
            "memory_budget_tokens": _env_int(
                "MEMORY_BUDGET_TOKENS",
                defaults.memory_budget_tokens,
            ),
            "dialog_top_k": _env_int(
                "DIALOG_TOP_K",
                defaults.dialog_top_k,
            ),
            "episodic_top_k": _env_int(
                "EPISODIC_TOP_K",
                defaults.episodic_top_k,
            ),
            "semantic_top_k": _env_int(
                "SEMANTIC_TOP_K",
                defaults.semantic_top_k,
            ),
            "dedup_threshold": _env_float(
                "DEDUP_THRESHOLD",
                defaults.dedup_threshold,
            ),
            "confidence_threshold": _env_float(
                "CONFIDENCE_THRESHOLD",
                defaults.confidence_threshold,
            ),
            "request_timeout_seconds": _env_float(
                "REQUEST_TIMEOUT_SECONDS",
                defaults.request_timeout_seconds,
            ),
        }
        config = cls(**values)
        config.validate()
        return config

    def validate(self) -> None:
        for name in (
            "embedding_dimension",
            "memory_budget_tokens",
            "dialog_top_k",
            "episodic_top_k",
            "semantic_top_k",
        ):
            if getattr(self, name) <= 0:
                raise ExtendedConfigError(f"{name} debe ser mayor que cero")
        for name in ("dedup_threshold", "confidence_threshold"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ExtendedConfigError(f"{name} debe estar entre 0 y 1")
        if self.request_timeout_seconds <= 0:
            raise ExtendedConfigError(
                "request_timeout_seconds debe ser mayor que cero"
            )
        for name in (
            "core_url",
            "ollama_url",
            "database_dsn",
            "embedding_model",
            "extraction_model",
        ):
            if not str(getattr(self, name)).strip():
                raise ExtendedConfigError(f"{name} no puede estar vacio")


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith(PREFIX):
            os.environ.setdefault(key, value.strip().strip("'\""))


def _env(name: str, default):
    return os.environ.get(f"{PREFIX}{name}", default)


def _env_int(name: str, default: int) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError as exc:
        raise ExtendedConfigError(
            f"{PREFIX}{name} debe ser un entero"
        ) from exc


def _env_float(name: str, default: float) -> float:
    raw = _env(name, str(default))
    try:
        return float(raw)
    except ValueError as exc:
        raise ExtendedConfigError(
            f"{PREFIX}{name} debe ser numerico"
        ) from exc
