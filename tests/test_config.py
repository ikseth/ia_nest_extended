import pytest

from ianest_extended import ExtendedConfig, ExtendedConfigError


def test_config_reads_prefixed_environment(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_CORE_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("IANEST_EXTENDED_DIALOG_TOP_K", "9")
    monkeypatch.setenv("IANEST_EXTENDED_MEMORY_MIN_SIMILARITY", "0.15")
    monkeypatch.setenv("IANEST_EXTENDED_DEDUP_THRESHOLD", "0.88")
    monkeypatch.setenv("IANEST_EXTENDED_DIALOG_HOT_WINDOW", "7200")
    monkeypatch.setenv("IANEST_EXTENDED_PROMOTE_MIN_STABILITY", "4")
    monkeypatch.setenv("IANEST_EXTENDED_RAG_ENABLED", "false")
    monkeypatch.setenv("IANEST_EXTENDED_RAG_MIN_SCORE", "0.5")
    monkeypatch.setenv("IANEST_EXTENDED_RAG_CHUNK_OVERLAP", "0.2")
    monkeypatch.setenv("IANEST_EXTENDED_AUTO_DOMAIN", "yes")
    monkeypatch.setenv("IANEST_EXTENDED_RAG_SUGGEST_MIN_CONFIDENCE", "0.65")
    monkeypatch.setenv("IANEST_EXTENDED_RAG_SUGGEST_SAMPLE_CHARS", "2400")
    monkeypatch.setenv("IANEST_EXTENDED_TASK_TIMEOUT_SECONDS", "480")

    config = ExtendedConfig.from_env(env_file=None)

    assert config.core_url == "http://127.0.0.1:9000"
    assert config.dialog_top_k == 9
    assert config.memory_min_similarity == 0.15
    assert config.dedup_threshold == 0.88
    assert config.dialog_hot_window_seconds == 7200
    assert config.promote_min_stability == 4
    assert config.rag_enabled is False
    assert config.rag_min_score == 0.5
    assert config.rag_chunk_overlap == 0.2
    assert config.auto_domain is True
    assert config.rag_suggest_min_confidence == 0.65
    assert config.rag_suggest_sample_chars == 2400
    assert config.task_timeout_seconds == 480


def test_config_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_CONFIDENCE_THRESHOLD", "1.5")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)


def test_config_rejects_invalid_maintenance_values(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_PROMOTE_RECENCY_MAX", "1.1")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)


def test_config_rejects_invalid_rag_values(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_RAG_CHUNK_OVERLAP", "1.0")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)


def test_config_rag_min_score_defaults_to_the_measured_floor():
    """D1 criterio 2: la ausencia de la clave toma el default medido (0.50)."""
    config = ExtendedConfig.from_env(env_file=None)

    assert config.rag_min_score == 0.50


def test_config_rejects_out_of_range_rag_min_score(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_RAG_MIN_SCORE", "1.5")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)


def test_config_memory_min_similarity_defaults_to_provisional_floor():
    config = ExtendedConfig.from_env(env_file=None)

    assert config.memory_min_similarity == 0.10


def test_config_rejects_out_of_range_memory_min_similarity(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_MEMORY_MIN_SIMILARITY", "1.5")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)
