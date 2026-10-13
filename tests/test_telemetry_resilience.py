from __future__ import annotations

import json

import pytest

from ianest_extended import MemoryIdentity, TelemetryWriter


def _identity() -> MemoryIdentity:
    return MemoryIdentity(
        user_id="sensitive-user",
        session_id="sensitive-session",
        service="sensitive-service",
    )


def _record(writer: TelemetryWriter, *, details=None, request_id="secret-request"):
    writer.record(
        event="prompt.run",
        request_id=request_id,
        downstream_request_id="secret-downstream",
        identity=_identity(),
        counters={"secret-counter": 1},
        latency_ms=1,
        status="ok",
        details=details,
    )


def test_record_contains_write_failure_and_warns_once_without_event_content(
    tmp_path,
    capsys,
):
    regular_parent = tmp_path / "regular-parent"
    regular_parent.write_text("not a directory", encoding="ascii")
    telemetry_dir = regular_parent / "telemetry"

    for index in range(100):
        writer = TelemetryWriter(telemetry_dir)
        _record(
            writer,
            details={"secret-detail": "never-print-this"},
            request_id=f"secret-request-{index}",
        )

    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert str(telemetry_dir) in lines[0]
    assert "extended-" in lines[0]
    assert "NotADirectoryError" in lines[0]
    assert "Not a directory" in lines[0]
    assert "secret-request" not in lines[0]
    assert "sensitive-user" not in lines[0]
    assert "sensitive-session" not in lines[0]
    assert "sensitive-service" not in lines[0]
    assert "secret-detail" not in lines[0]
    assert "never-print-this" not in lines[0]


def test_record_contains_serialization_failure_and_warns(tmp_path, capsys):
    writer = TelemetryWriter(tmp_path / "telemetry")

    _record(writer, details={"secret-detail": object()})

    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    assert str(tmp_path / "telemetry") in lines[0]
    assert "extended-" in lines[0]
    assert "TypeError" in lines[0]
    assert "not JSON serializable" in lines[0]
    assert "secret-request" not in lines[0]
    assert "sensitive-user" not in lines[0]
    assert "sensitive-service" not in lines[0]
    assert "secret-detail" not in lines[0]


def test_record_recovers_without_restart_and_does_not_replay_lost_line(
    tmp_path,
    capsys,
):
    regular_parent = tmp_path / "regular-parent"
    regular_parent.write_text("not a directory", encoding="ascii")
    telemetry_dir = regular_parent / "telemetry"
    writer = TelemetryWriter(telemetry_dir)

    _record(writer, request_id="lost-request")
    assert len(capsys.readouterr().err.splitlines()) == 1
    regular_parent.unlink()
    regular_parent.mkdir()

    _record(writer, request_id="written-request")

    path = next(telemetry_dir.glob("extended-*.jsonl"))
    lines = path.read_text(encoding="ascii").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["request_id"] == "written-request"
    assert "lost-request" not in lines[0]


def test_record_does_not_contain_base_exception(tmp_path, monkeypatch):
    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(json, "dumps", interrupt)

    with pytest.raises(KeyboardInterrupt):
        _record(TelemetryWriter(tmp_path / "telemetry"))
