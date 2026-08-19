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


def _pin_episodic_similarity(store, *, user, content, query_text):
    """Fija a mano la similitud entre un engrama episodic y una consulta.

    `FakeEmbedder` deriva el vector de un hash del texto: la similitud entre
    "the user prefers blue" (el hecho escrito por write-back) y "smalltalk"
    (la consulta de la sesion B) es practicamente aleatoria, y en la
    practica cae por debajo del suelo D4 -no por un conflicto de diseno, sino
    porque esta prueba no controla la similitud (docs/handoff/
    deuda_d4_brief.md)-. Esta prueba es de CONTINUIDAD entre sesiones, no del
    suelo, asi que se fija el embedding del engrama ya escrito para que su
    similitud con la consulta de la sesion B sea 1.0, y el suelo deja de
    interferir con lo que la prueba en realidad verifica.
    """
    target_vector = store._embedder.embed(query_text)
    literal = "[" + ",".join(str(value) for value in target_vector) + "]"
    with store._connect() as connection:
        connection.execute(
            """
            UPDATE engrams SET embedding = %s::vector
            WHERE user_id = %s AND type_name = 'episodic' AND content = %s
            """,
            (literal, user, content),
        )


def test_phase3_a_continuity_across_sessions(
    postgres_store,
    local_service_stub,
    tmp_path,
):
    user = f"phase3-a-{uuid4()}"
    enricher = _enricher(postgres_store, local_service_stub, tmp_path)

    enricher.enrich(_identity(user, "A"), "remember-blue")
    _pin_episodic_similarity(
        postgres_store,
        user=user,
        content="the user prefers blue",
        query_text="smalltalk",
    )
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
