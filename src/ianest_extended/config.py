"""Configuracion local de ia_nest_extended."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .errors import ExtendedConfigError

PREFIX = "IANEST_EXTENDED_"


def default_session_state_path() -> Path:
    """Ruta del estado local de sesion, siguiendo la convencion XDG."""
    base = os.environ.get("XDG_STATE_HOME") or "~/.local/state"
    return Path(base).expanduser() / "ianest_extended" / "session_id"


@dataclass(frozen=True, slots=True)
class ExtendedConfig:
    core_url: str = "http://127.0.0.1:8000"
    ollama_url: str = "http://127.0.0.1:11434"
    database_dsn: str = (
        "postgresql://ianest:ianest_local@127.0.0.1:55432/ianest_extended"
    )
    embedding_model: str = "bge-m3"
    embedding_dimension: int = 1024
    extraction_model: str = "qwen_tech"
    telemetry_dir: Path = Path("telemetry")
    session_state_path: Path = field(default_factory=default_session_state_path)
    default_user_id: str = "local_operator"
    default_service: str = "local_cli"
    default_namespace: str = ""
    enrich_enabled: bool = True
    memory_enabled: bool = True
    write_back_enabled: bool = True
    memory_budget_tokens: int = 1500
    dialog_top_k: int = 6
    episodic_top_k: int = 4
    semantic_top_k: int = 3
    dedup_threshold: float = 0.92
    confidence_threshold: float = 0.7
    connect_timeout_seconds: float = 30.0
    inactivity_timeout_seconds: float = 30.0
    task_timeout_seconds: float = 600.0
    dialog_hot_window_seconds: int = 4 * 60 * 60
    promote_min_stability: int = 3
    promote_min_score: float = 0.8
    promote_recency_max: float = 0.1
    rag_enabled: bool = True
    rag_top_k: int = 3
    rag_max_tokens: int = 500
    rag_chunk_tokens: int = 300
    rag_chunk_overlap: float = 0.15
    auto_domain: bool = False
    auto_domain_min_confidence: float = 0.7
    rag_suggest_min_confidence: float = 0.6
    rag_suggest_sample_chars: int = 2000

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
            "session_state_path": Path(
                _env("SESSION_STATE_PATH", str(defaults.session_state_path))
            ).expanduser(),
            "default_user_id": _env("DEFAULT_USER_ID", defaults.default_user_id),
            "default_service": _env("DEFAULT_SERVICE", defaults.default_service),
            "default_namespace": _env(
                "DEFAULT_NAMESPACE",
                defaults.default_namespace,
            ),
            "enrich_enabled": _env_bool(
                "ENRICH_ENABLED",
                defaults.enrich_enabled,
            ),
            "memory_enabled": _env_bool(
                "MEMORY_ENABLED",
                defaults.memory_enabled,
            ),
            "write_back_enabled": _env_bool(
                "WRITE_BACK_ENABLED",
                defaults.write_back_enabled,
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
            "connect_timeout_seconds": _env_float(
                "CONNECT_TIMEOUT_SECONDS",
                defaults.connect_timeout_seconds,
            ),
            "inactivity_timeout_seconds": _env_float(
                "INACTIVITY_TIMEOUT_SECONDS",
                defaults.inactivity_timeout_seconds,
            ),
            "task_timeout_seconds": _env_float(
                "TASK_TIMEOUT_SECONDS",
                defaults.task_timeout_seconds,
            ),
            "dialog_hot_window_seconds": _env_int(
                "DIALOG_HOT_WINDOW",
                defaults.dialog_hot_window_seconds,
            ),
            "promote_min_stability": _env_int(
                "PROMOTE_MIN_STABILITY",
                defaults.promote_min_stability,
            ),
            "promote_min_score": _env_float(
                "PROMOTE_MIN_SCORE",
                defaults.promote_min_score,
            ),
            "promote_recency_max": _env_float(
                "PROMOTE_RECENCY_MAX",
                defaults.promote_recency_max,
            ),
            "rag_enabled": _env_bool("RAG_ENABLED", defaults.rag_enabled),
            "rag_top_k": _env_int("RAG_TOP_K", defaults.rag_top_k),
            "rag_max_tokens": _env_int(
                "RAG_MAX_TOKENS",
                defaults.rag_max_tokens,
            ),
            "rag_chunk_tokens": _env_int(
                "RAG_CHUNK_TOKENS",
                defaults.rag_chunk_tokens,
            ),
            "rag_chunk_overlap": _env_float(
                "RAG_CHUNK_OVERLAP",
                defaults.rag_chunk_overlap,
            ),
            "auto_domain": _env_bool(
                "AUTO_DOMAIN",
                defaults.auto_domain,
            ),
            "auto_domain_min_confidence": _env_float(
                "AUTO_DOMAIN_MIN_CONFIDENCE",
                defaults.auto_domain_min_confidence,
            ),
            "rag_suggest_min_confidence": _env_float(
                "RAG_SUGGEST_MIN_CONFIDENCE",
                defaults.rag_suggest_min_confidence,
            ),
            "rag_suggest_sample_chars": _env_int(
                "RAG_SUGGEST_SAMPLE_CHARS",
                defaults.rag_suggest_sample_chars,
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
            "dialog_hot_window_seconds",
            "rag_top_k",
            "rag_max_tokens",
            "rag_chunk_tokens",
            "rag_suggest_sample_chars",
        ):
            if getattr(self, name) <= 0:
                raise ExtendedConfigError(f"{name} debe ser mayor que cero")
        for name in (
            "dedup_threshold",
            "confidence_threshold",
            "auto_domain_min_confidence",
            "rag_suggest_min_confidence",
        ):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ExtendedConfigError(f"{name} debe estar entre 0 y 1")
        for name in (
            "connect_timeout_seconds",
            "inactivity_timeout_seconds",
            "task_timeout_seconds",
        ):
            if getattr(self, name) <= 0:
                raise ExtendedConfigError(f"{name} debe ser mayor que cero", name)
        if self.promote_min_stability < 0:
            raise ExtendedConfigError(
                "promote_min_stability no puede ser negativo"
            )
        for name in ("promote_min_score", "promote_recency_max"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ExtendedConfigError(f"{name} debe estar entre 0 y 1")
        if not 0.0 <= self.rag_chunk_overlap < 1.0:
            raise ExtendedConfigError(
                "rag_chunk_overlap debe estar entre 0 (incluido) y 1 (excluido)"
            )
        for name in (
            "core_url",
            "ollama_url",
            "database_dsn",
            "embedding_model",
            "extraction_model",
            "default_service",
        ):
            if not str(getattr(self, name)).strip():
                raise ExtendedConfigError(f"{name} no puede estar vacio", name)


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


def _env_bool(name: str, default: bool) -> bool:
    raw = str(_env(name, str(default))).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise ExtendedConfigError(
        f"{PREFIX}{name} debe ser booleano (true/false)"
    )
