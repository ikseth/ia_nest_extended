import json
from uuid import uuid4

from ianest_extended import (
    CoreClient,
    ExtendedConfig,
    MemoryEnricher,
    MemoryIdentity,
    RecallQuery,
    TelemetryWriter,
)


def _identity(user, session):
    return MemoryIdentity(
        user_id=user,
        session_id=session,
        service="acceptance_stub",
        domain_tag="linux",
        namespace="preferences",
    )


def _enricher(postgres_store, local_service_stub, tmp_path):
    config = ExtendedConfig(
        telemetry_dir=tmp_path,
    )
    return MemoryEnricher(
        store=postgres_store,
        core=CoreClient(local_service_stub.base_url, connect_timeout_seconds=2),
        telemetry=TelemetryWriter(tmp_path),
        config=config,
    )


def test_phase3_a_continuity_across_sessions(
    postgres_store,
    local_service_stub,
    tmp_path,
):
    user = f"phase3-a-{uuid4()}"
    enricher = _enricher(postgres_store, local_service_stub, tmp_path)

    enricher.enrich(_identity(user, "A"), "remember-blue")
    result = enricher.enrich(_identity(user, "B"), "smalltalk")

    assert "the user prefers blue" in result.context
    assert "remember-blue" not in result.context


def test_phase3_b_smalltalk_writes_only_dialog(
    postgres_store,
    local_service_stub,
    tmp_path,
):
    user = f"phase3-b-{uuid4()}"
    identity = _identity(user, "A")
    enricher = _enricher(postgres_store, local_service_stub, tmp_path)

    enricher.enrich(identity, "smalltalk")

    dialog = postgres_store.recall(
        RecallQuery(
            type_names=("dialog",),
            identity=identity,
            text="smalltalk",
            domain_tag=identity.domain_tag,
            top_k=10,
        )
    )
    episodic = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=identity,
            text="smalltalk",
            namespace="facts",
            domain_tag=identity.domain_tag,
            top_k=10,
        )
    )
    assert len(dialog) == 2
    assert episodic == ()


def test_phase3_c_duplicate_reinforces_without_inserting(
    postgres_store,
    local_service_stub,
    tmp_path,
):
    user = f"phase3-c-{uuid4()}"
    enricher = _enricher(postgres_store, local_service_stub, tmp_path)

    enricher.enrich(_identity(user, "A"), "repeat-fact")
    enricher.enrich(_identity(user, "B"), "repeat-fact")

    items = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=_identity(user, "C"),
            text="the project uses PostgreSQL",
            namespace="facts",
            domain_tag="linux",
            top_k=10,
        )
    )
    assert len(items) == 1
    assert items[0].engram.stability == 1


def test_phase3_d_telemetry_events_share_request_id(
    postgres_store,
    local_service_stub,
    tmp_path,
):
    enricher = _enricher(postgres_store, local_service_stub, tmp_path)

    enricher.enrich(_identity(f"phase3-d-{uuid4()}", "A"), "smalltalk")

    path = next(tmp_path.glob("extended-*.jsonl"))
    events = [json.loads(line) for line in path.read_text().splitlines()]
    assert [event["event"] for event in events] == [
        "enrich.recall",
        "enrich.write_back",
    ]
    assert events[0]["request_id"] == events[1]["request_id"]
    assert events[0]["downstream_request_id"] == events[1]["downstream_request_id"]
