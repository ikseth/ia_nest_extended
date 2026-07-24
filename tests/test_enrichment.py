import json

from ianest_extended import (
    CoreClient,
    ExtendedConfig,
    MemoryEnricher,
    TelemetryWriter,
)
from ianest_extended.enrichment import (
    _extraction_prompt,
    _parse_extraction,
    _validate_item,
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


def test_extraction_prompt_uses_concrete_values_and_json_only():
    prompt = _extraction_prompt("hola", "hola")

    assert '"namespace":"preferences"' in prompt
    assert '"confidence":0.9' in prompt
    assert '{"items":[]}' in prompt
    assert "facts|preferences|tasks" not in prompt
    assert "no markdown fences or text outside the JSON" in prompt


def test_parse_extraction_tolerates_real_qwen_output_defects():
    copied_confidence = (
        '{"items":[{"namespace":"preferences","content":'
        '"mi color favorito es el verde","confidence":0.0,"mentions":[]}]}'
    )
    copied_namespace = (
        '{"items":[{"namespace":"facts|preferences","content":'
        '"trabajo con openSUSE","confidence":0.9,"mentions":["openSUSE"]}]}'
    )
    fenced_with_trailing_text = (
        '```json\n{"items":[{"namespace":"facts","content":'
        '"trabajo con openSUSE","confidence":0.9,"mentions":["openSUSE"]}]}\n'
        "```\nTexto colgante."
    )

    low_confidence_item = _parse_extraction(copied_confidence)[0]
    invalid_namespace_item = _parse_extraction(copied_namespace)[0]
    fenced_item = _parse_extraction(fenced_with_trailing_text)[0]

    assert _validate_item(low_confidence_item)["confidence"] == 0.0
    assert _validate_item(invalid_namespace_item) is None
    assert _validate_item(fenced_item) == {
        "namespace": "facts",
        "content": "trabajo con openSUSE",
        "confidence": 0.9,
        "mentions": ("openSUSE",),
    }
