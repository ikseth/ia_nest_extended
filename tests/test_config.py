import pytest

from ianest_extended import ExtendedConfig, ExtendedConfigError


def test_config_reads_prefixed_environment(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_CORE_URL", "http://127.0.0.1:9000")
    monkeypatch.setenv("IANEST_EXTENDED_DIALOG_TOP_K", "9")
    monkeypatch.setenv("IANEST_EXTENDED_DEDUP_THRESHOLD", "0.88")
    monkeypatch.setenv("IANEST_EXTENDED_DIALOG_HOT_WINDOW", "7200")
    monkeypatch.setenv("IANEST_EXTENDED_PROMOTE_MIN_STABILITY", "4")

    config = ExtendedConfig.from_env(env_file=None)

    assert config.core_url == "http://127.0.0.1:9000"
    assert config.dialog_top_k == 9
    assert config.dedup_threshold == 0.88
    assert config.dialog_hot_window_seconds == 7200
    assert config.promote_min_stability == 4


def test_config_rejects_invalid_values(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_CONFIDENCE_THRESHOLD", "1.5")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)


def test_config_rejects_invalid_maintenance_values(monkeypatch):
    monkeypatch.setenv("IANEST_EXTENDED_PROMOTE_RECENCY_MAX", "1.1")

    with pytest.raises(ExtendedConfigError):
        ExtendedConfig.from_env(env_file=None)
