from uuid import uuid4

import pytest

from ianest_extended import (
    EngramStatus,
    EngramWrite,
    EntityProfile,
    MemoryIdentity,
    Principal,
    RecallQuery,
    WriteAuthorityError,
)


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
