from dataclasses import replace

import pytest

from ianest_extended import (
    AliasedDeclarationError,
    AliasedTierError,
    InvalidMemoryTypeError,
    InvalidNamespaceError,
    MemoryClass,
    MemoryIdentity,
    MemoryType,
    MemoryTypeRegistry,
    Principal,
    RetrievalMode,
    Scope,
    ScopeViolationError,
    seed_memory_types,
)
from ianest_extended.registry import derive_memory_key


def _seeds_by_name():
    return {item.name: item for item in seed_memory_types()}


def test_seed_roster_is_valid():
    registry = MemoryTypeRegistry(seed_memory_types())

    assert tuple(item.name for item in registry.list()) == (
        "dialog",
        "episodic",
        "semantic",
        "entities",
        "identity",
        "principles",
        "safety",
    )


def test_v1_rejects_declaration_with_all_axes_aliased():
    identity = _seeds_by_name()["identity"]
    duplicate_axes = replace(identity, name="identity_copy")
    registry = MemoryTypeRegistry((identity,))

    with pytest.raises(AliasedDeclarationError):
        registry.register(duplicate_axes)


def test_v2_rejects_ranked_tier_with_same_scope_weights_and_half_life():
    episodic = _seeds_by_name()["episodic"]
    duplicate_tier = replace(
        episodic,
        name="episodic_copy",
        namespaces=("other",),
    )
    registry = MemoryTypeRegistry((episodic,))

    with pytest.raises(AliasedTierError):
        registry.register(duplicate_tier)


def test_user_scope_uses_same_key_across_sessions():
    episodic = _seeds_by_name()["episodic"]

    first = derive_memory_key(
        episodic,
        MemoryIdentity(user_id="u1", session_id="A"),
        "facts",
    )
    second = derive_memory_key(
        episodic,
        MemoryIdentity(user_id="u1", session_id="B"),
        "facts",
    )

    assert first == second
    assert first.session_id is None


def test_session_scope_keeps_session_and_requires_identity():
    dialog = _seeds_by_name()["dialog"]
    key = derive_memory_key(
        dialog,
        MemoryIdentity(user_id="u1", session_id="A"),
        None,
    )

    assert key.user_id == "u1"
    assert key.session_id == "A"

    with pytest.raises(ScopeViolationError):
        derive_memory_key(
            dialog,
            MemoryIdentity(user_id="u1"),
            None,
        )


def test_v3_rejects_inconsistent_namespace():
    episodic = _seeds_by_name()["episodic"]

    with pytest.raises(InvalidNamespaceError):
        derive_memory_key(
            episodic,
            MemoryIdentity(user_id="u1"),
            "persona",
        )


def test_delegated_type_requires_conscience_principal():
    with pytest.raises(InvalidMemoryTypeError):
        MemoryTypeRegistry(
            (
                MemoryType(
                    name="invalid",
                    memory_class=MemoryClass.DELEGATED,
                    writer_principal=Principal.EXTENDED,
                    retrieval_mode=RetrievalMode.ALWAYS_INJECT,
                    scope=Scope.GLOBAL,
                    namespaces=("invalid",),
                ),
            )
        )
