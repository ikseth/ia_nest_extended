import json
from uuid import uuid4

import pytest

from ianest_extended import (
    CoreClient,
    calculate_relevance,
    EngramStatus,
    EngramWrite,
    EntityProfile,
    ExtendedConfig,
    MemoryEnricher,
    MemoryIdentity,
    Principal,
    RecallQuery,
    TelemetryWriter,
    WriteAuthorityError,
)


def _set_embedding(store, engram_id, vector):
    literal = "[" + ",".join(str(value) for value in vector) + "]"
    with store._connect() as connection:
        connection.execute(
            "UPDATE engrams SET embedding = %s::vector WHERE id = %s",
            (literal, engram_id),
        )


def _opposite_embedding(store, text):
    return tuple(-value for value in store._embedder.embed(text))


def _orthogonal_embedding(store, text):
    query = store._embedder.embed(text)
    index = min(range(len(query)), key=lambda current: abs(query[current]))
    vector = [-query[index] * value for value in query]
    vector[index] += 1.0
    norm = sum(value * value for value in vector) ** 0.5
    return tuple(value / norm for value in vector)


def test_a1_continuity_and_session_isolation(postgres_store):
    unique_user = f"u-{uuid4()}"
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="el usuario prefiere respuestas concisas",
            identity=MemoryIdentity(unique_user, "A"),
            namespace="facts",
            score=0.8,
        ),
    )
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="turno privado de la sesion A",
            identity=MemoryIdentity(unique_user, "A"),
        ),
    )

    episodic = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=MemoryIdentity(unique_user, "B"),
            text="preferencias de respuesta",
            namespace="facts",
        )
    )
    dialog = postgres_store.recall(
        RecallQuery(
            type_names=("dialog",),
            identity=MemoryIdentity(unique_user, "B"),
            text="turno",
        )
    )

    assert [item.engram.content for item in episodic] == [
        "el usuario prefiere respuestas concisas"
    ]
    assert dialog == ()


def test_a2_delegated_authority_is_enforced(postgres_store):
    request = EngramWrite(
        type_name="identity",
        content="soy una entidad en evolucion",
        namespace="persona",
    )

    with pytest.raises(WriteAuthorityError):
        postgres_store.write(Principal.EXTENDED, request)

    stored = postgres_store.write(Principal.CONSCIENCE, request)
    assert stored.type_name == "identity"


def test_always_inject_is_not_limited_by_top_k(postgres_store):
    for content in ("principio uno", "principio dos"):
        postgres_store.write(
            Principal.CONSCIENCE,
            EngramWrite(
                type_name="principles",
                content=f"{content} {uuid4()}",
                namespace="principles",
            ),
        )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("principles",),
            top_k=1,
        )
    )

    assert len(recalled) >= 2


def test_entity_profile_uses_delegated_contract(postgres_store):
    profile = EntityProfile(
        id=uuid4(),
        kind="project",
        name="proyecto de prueba",
        profile={"state": "test"},
    )

    with pytest.raises(WriteAuthorityError):
        postgres_store.write_entity(
            Principal.EXTENDED,
            "entities",
            profile,
        )

    stored = postgres_store.write_entity(
        Principal.CONSCIENCE,
        "entities",
        profile,
    )
    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("entities",),
            entity_id=profile.id,
        )
    )

    assert stored.id == profile.id
    assert recalled[0].entity.id == profile.id


def test_gates_filter_domain_and_entity_reference(postgres_store):
    unique_user = f"u-{uuid4()}"
    selected_entity = uuid4()
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="hecho linux",
            identity=MemoryIdentity(unique_user, "A"),
            namespace="facts",
            domain_tag="linux.ops",
            entity_refs=(selected_entity,),
        ),
    )
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="hecho salud",
            identity=MemoryIdentity(unique_user, "A"),
            namespace="facts",
            domain_tag="chat.salud",
        ),
    )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=MemoryIdentity(unique_user, "B"),
            namespace="facts",
            domain_tag="linux.ops",
            entity_ref=selected_entity,
        )
    )

    assert [item.engram.content for item in recalled] == ["hecho linux"]


def test_d2_domain_filter_treats_memory_without_domain_as_neutral(postgres_store):
    """D2: pedido=X incluye X y sin-dominio; excluye solo un dominio distinto.

    docs/PLAN.md D2 / docs/handoff/deudas_d1_d2_brief.md: una memoria sin
    `domain_tag` no es incompatible con el dominio pedido, es neutra, y debe
    seguir siendo candidata (a diferencia del filtro estricto anterior).
    """
    unique_user = f"u-{uuid4()}"
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="hecho del dominio pedido",
            identity=MemoryIdentity(unique_user, "A"),
            namespace="facts",
            domain_tag="linux",
        ),
    )
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="hecho sin dominio, neutro",
            identity=MemoryIdentity(unique_user, "A"),
            namespace="facts",
        ),
    )
    postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="hecho de otro dominio",
            identity=MemoryIdentity(unique_user, "A"),
            namespace="facts",
            domain_tag="matematicas",
        ),
    )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=MemoryIdentity(unique_user, "B"),
            namespace="facts",
            domain_tag="linux",
        )
    )

    contents = {item.engram.content for item in recalled}
    assert contents == {"hecho del dominio pedido", "hecho sin dominio, neutro"}
    assert "hecho de otro dominio" not in contents


def test_d4_similarity_floor_gates_episodic_before_composite_relevance(
    postgres_store,
):
    """D4 criterio 1: similitud baja no pasa aunque recencia y merito sumen."""
    user = f"u-{uuid4()}"
    prompt = "consulta sobre semillas"
    stored = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="engrama reciente y estable",
            identity=MemoryIdentity(user, "A"),
            namespace="facts",
            score=1.0,
            stability=10,
        ),
    )
    _set_embedding(
        postgres_store,
        stored.id,
        _orthogonal_embedding(postgres_store, prompt),
    )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=MemoryIdentity(user, "B"),
            text=prompt,
            namespace="facts",
            min_similarity=0.10,
        )
    )

    episodic = next(
        memory_type
        for memory_type in postgres_store.list_types()
        if memory_type.name == "episodic"
    )
    assert calculate_relevance(
        episodic,
        age_seconds=0,
        similarity=0.0,
        stability=10,
        score=1.0,
    ) > 0.6
    assert recalled == ()


def test_d4_passing_memories_keep_composite_relevance_order(postgres_store):
    """D4 criterio 2: el suelo gatea; no sustituye el orden compuesto."""
    user = f"u-{uuid4()}"
    prompt = "preferencias de respuesta"
    lower = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content=prompt,
            identity=MemoryIdentity(user, "A"),
            namespace="facts",
            score=0.0,
            stability=0,
        ),
    )
    higher = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content=prompt,
            identity=MemoryIdentity(user, "A"),
            namespace="facts",
            score=1.0,
            stability=10,
        ),
    )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("episodic",),
            identity=MemoryIdentity(user, "B"),
            text=prompt,
            namespace="facts",
            min_similarity=0.10,
            top_k=2,
        )
    )

    assert [item.engram.id for item in recalled] == [higher.id, lower.id]


def test_d4_semantic_is_not_gated_even_when_query_carries_a_floor(postgres_store):
    """D4 criterio 3: semantic ya paso un juicio de promocion; sin suelo."""
    user = f"u-{uuid4()}"
    prompt = "consulta sin relacion"
    stored = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="semantic",
            content="hecho consolidado del interlocutor",
            identity=MemoryIdentity(user, "A"),
            namespace="facts",
        ),
    )
    _set_embedding(
        postgres_store,
        stored.id,
        _opposite_embedding(postgres_store, prompt),
    )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("semantic",),
            identity=MemoryIdentity(user, "B"),
            text=prompt,
            namespace="facts",
            min_similarity=1.0,
        )
    )

    assert [item.engram.id for item in recalled] == [stored.id]


def test_d4_dialog_is_not_gated_even_when_query_carries_a_floor(postgres_store):
    """D4 criterio 4: dialog conserva continuidad aunque no sea similar."""
    user = f"u-{uuid4()}"
    prompt = "consulta sin relacion"
    stored = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="dialog",
            content="turno previo de la sesion",
            identity=MemoryIdentity(user, "A"),
        ),
    )
    _set_embedding(
        postgres_store,
        stored.id,
        _opposite_embedding(postgres_store, prompt),
    )

    recalled = postgres_store.recall(
        RecallQuery(
            type_names=("dialog",),
            identity=MemoryIdentity(user, "A"),
            text=prompt,
            min_similarity=1.0,
        )
    )

    assert [item.engram.id for item in recalled] == [stored.id]


def test_d4_delegates_ignore_arbitrarily_high_similarity_floor(postgres_store):
    """D4 criterio 5: ALWAYS_INJECT no entra en el mecanismo del suelo."""
    user = f"u-{uuid4()}"
    writes = (
        ("identity", "persona", MemoryIdentity()),
        ("principles", "principles", MemoryIdentity()),
        ("safety", "safety", MemoryIdentity(user, "A")),
    )
    stored = []
    for type_name, namespace, identity in writes:
        stored.append(
            postgres_store.write(
                Principal.CONSCIENCE,
                EngramWrite(
                    type_name=type_name,
                    content=f"{type_name} permanente",
                    identity=identity,
                    namespace=namespace,
                ),
            )
        )

    recalled = []
    for type_name, namespace, identity in writes:
        recalled.extend(
            postgres_store.recall(
                RecallQuery(
                    type_names=(type_name,),
                    identity=identity,
                    text="consulta sin relacion",
                    namespace=namespace,
                    min_similarity=1.0,
                )
            )
        )

    assert {item.engram.id for item in recalled} == {item.id for item in stored}


def test_d4_zero_passing_memories_complete_with_zero_telemetry(
    postgres_store,
    tmp_path,
):
    """D4 criterio 7: no pasar el suelo no es un error de recall."""
    user = f"u-{uuid4()}"
    prompt = "consulta sin relacion"
    stored = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="engrama ajeno",
            identity=MemoryIdentity(user, "A"),
            namespace="facts",
        ),
    )
    _set_embedding(
        postgres_store,
        stored.id,
        _opposite_embedding(postgres_store, prompt),
    )
    enricher = MemoryEnricher(
        store=postgres_store,
        core=CoreClient("http://127.0.0.1:1"),
        telemetry=TelemetryWriter(tmp_path),
        config=ExtendedConfig(
            telemetry_dir=tmp_path,
            rag_enabled=False,
        ),
    )

    result = enricher.enrich(
        MemoryIdentity(user, "B"),
        prompt,
        dry_run=True,
    )

    event = json.loads(next(tmp_path.glob("extended-*.jsonl")).read_text())
    assert result.context == ""
    assert event["status"] == "dry_run"
    assert all(
        value == 0
        for name, value in event["counters"].items()
        if name.endswith("_returned")
    )


def test_a5_archive_preserves_row(postgres_store):
    stored = postgres_store.write(
        Principal.EXTENDED,
        EngramWrite(
            type_name="episodic",
            content="engrama archivable",
            identity=MemoryIdentity(f"u-{uuid4()}", "A"),
            namespace="facts",
        ),
    )

    archived = postgres_store.archive(
        Principal.EXTENDED,
        stored.id,
        "prueba de retencion",
    )
    still_present = postgres_store.get_engram(stored.id)

    assert archived.status is EngramStatus.ARCHIVED
    assert still_present.id == stored.id
    assert still_present.archived_reason == "prueba de retencion"
