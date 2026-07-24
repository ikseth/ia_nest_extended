import json

from ianest_extended import (
    CoreClient,
    ExtendedConfig,
    MemoryEnricher,
    TelemetryWriter,
)

from .fakes import InMemoryStore, identity


def _enricher(tmp_path, local_service_stub, store):
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
        embedding_dimension=2,
        memory_budget_tokens=1500,
    )
    return MemoryEnricher(
        store=store,
        core=CoreClient(local_service_stub.base_url, timeout_seconds=2),
        telemetry=TelemetryWriter(tmp_path),
        config=config,
    )


def _events(tmp_path):
    path = next(tmp_path.glob("extended-*.jsonl"))
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_vertical_continuity_antinoise_and_telemetry(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    first = enricher.enrich(identity(session="A"), "remember-blue")
    second = enricher.enrich(identity(session="B"), "smalltalk")

    assert "the user prefers blue" in second.context
    assert "remember-blue" not in second.context
    episodic = [item for item in store.engrams if item.type_name == "episodic"]
    dialog = [item for item in store.engrams if item.type_name == "dialog"]
    assert len(episodic) == 1
    assert len(dialog) == 4
    assert first.trace["finish_reason"] == "stop"

    events = _events(tmp_path)
    assert [event["event"] for event in events] == [
        "enrich.recall",
        "enrich.write_back",
        "enrich.recall",
        "enrich.write_back",
    ]
    assert events[0]["request_id"] == events[1]["request_id"]
    assert events[0]["core_request_id"] == events[1]["core_request_id"]
    assert events[3]["counters"]["items_written"] == 0


def test_write_back_reinforces_duplicate(tmp_path, local_service_stub):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(session="A"), "repeat-fact")
    enricher.enrich(identity(session="B"), "repeat-fact")

    episodic = [item for item in store.engrams if item.type_name == "episodic"]
    assert len(episodic) == 1
    assert episodic[0].stability == 1
    assert episodic[0].unresolved_mentions == ("PostgreSQL",)
    assert _events(tmp_path)[-1]["counters"]["items_reinforced"] == 1


def test_invalid_extraction_is_discarded_and_traced(
    tmp_path,
    local_service_stub,
):
    store = InMemoryStore()
    enricher = _enricher(tmp_path, local_service_stub, store)

    enricher.enrich(identity(), "invalid-json")

    assert not [item for item in store.engrams if item.type_name == "episodic"]
    event = _events(tmp_path)[-1]
    assert event["status"] == "invalid_extraction_json"
    assert event["counters"]["invalid_json"] == 1
