from pathlib import Path

import psycopg
import pytest

from ianest_extended import (
    EntityWriteAuthorityError,
    InvalidEntityError,
    InvalidEntitySeedError,
    Principal,
)
from ianest_extended.entities import read_seed


def _seed(path: Path, text: str, ceiling=("casa_ha",)):
    path.write_text(text, encoding="ascii")
    return read_seed(path, ceiling)


def test_closed_facts_and_part_owners(postgres_store):
    with pytest.raises(InvalidEntityError):
        postgres_store.put_entity(
            Principal.OPERATOR,
            "provider:casa_ha",
            "provider",
            curated={"unknown": True},
        )
    with pytest.raises(EntityWriteAuthorityError):
        postgres_store.put_entity(
            Principal.EXTENDED,
            "provider:casa_ha",
            "provider",
            curated={"trusted": True},
        )
    with pytest.raises(EntityWriteAuthorityError):
        postgres_store.put_entity(
            Principal.OPERATOR,
            "provider:casa_ha",
            "provider",
            observed={"name": "casa_ha"},
        )


def test_refresh_versions_is_idempotent_and_retires(postgres_store):
    first = postgres_store.refresh_providers(("casa_ha", "otro"))
    second = postgres_store.refresh_providers(("casa_ha", "otro"))
    postgres_store.put_entity(
        Principal.OPERATOR,
        "provider:otro",
        "provider",
        curated={"trusted": True},
    )
    retired = postgres_store.refresh_providers(("casa_ha",))

    assert first["created"] == ["provider:casa_ha", "provider:otro"]
    assert second == {"created": [], "changed": [], "retired": []}
    assert retired["retired"] == ["provider:otro"]
    entity = postgres_store.get_entity("provider:otro")
    assert entity.status == "retired"
    assert entity.retired_at is not None
    assert postgres_store.entity_history("provider:otro")[-1].status == "retired"
    assert postgres_store.trusted_providers(("casa_ha",)) == ()


def test_seed_is_atomic_owned_and_restores_cli_changes(postgres_store, tmp_path):
    postgres_store.refresh_providers(("casa_ha",))
    seed = _seed(
        tmp_path / "entities.toml",
        '[[entity]]\nkey = "provider:casa_ha"\nkind = "provider"\ntrusted = true\n',
    )
    plan = postgres_store.apply_entity_seed(seed, plan=True)
    assert plan == {
        "create": [],
        "change": [{"key": "provider:casa_ha"}],
        "retire": [],
    }
    postgres_store.apply_entity_seed(seed)
    version_count = len(postgres_store.entity_history("provider:casa_ha"))
    assert postgres_store.apply_entity_seed(seed, plan=True) == {
        "create": [], "change": [], "retire": []
    }
    postgres_store.apply_entity_seed(seed)
    assert len(postgres_store.entity_history("provider:casa_ha")) == version_count

    postgres_store.put_entity(
        Principal.OPERATOR,
        "provider:casa_ha",
        "provider",
        curated={"trusted": False},
    )
    assert postgres_store.apply_entity_seed(seed, plan=True)["change"] == [
        {"key": "provider:casa_ha"}
    ]
    postgres_store.apply_entity_seed(seed)
    assert postgres_store.get_entity("provider:casa_ha").curated == {
        "trusted": True
    }

    bad_path = tmp_path / "bad.toml"
    bad_path.write_text(
        '[[entity]]\nkey="provider:casa_ha"\nkind="provider"\ntrusted=false\n'
        '[[entity]]\nkey="provider:fuera"\nkind="provider"\ntrusted=true\n',
        encoding="ascii",
    )
    before = len(postgres_store.entity_history("provider:casa_ha"))
    with pytest.raises(InvalidEntitySeedError, match="entrada 1.*provider:fuera"):
        read_seed(bad_path, ("casa_ha",))
    assert len(postgres_store.entity_history("provider:casa_ha")) == before

    unknown_path = tmp_path / "unknown.toml"
    unknown_path.write_text(
        '[[entity]]\nkey="provider:casa_ha"\nkind="provider"\nunknown=true\n',
        encoding="ascii",
    )
    with pytest.raises(InvalidEntitySeedError, match="entrada 0.*unknown"):
        read_seed(unknown_path, ("casa_ha",))

    duplicate_path = tmp_path / "duplicate.toml"
    duplicate_path.write_text(
        '[[entity]]\nkey="provider:casa_ha"\nkind="provider"\ntrusted=true\n'
        '[[entity]]\nkey="provider:casa_ha"\nkind="provider"\ntrusted=false\n',
        encoding="ascii",
    )
    with pytest.raises(InvalidEntitySeedError, match="entrada 1.*clave repetida"):
        read_seed(duplicate_path, ("casa_ha",))


def test_seed_removal_retires_only_seed_created(postgres_store, tmp_path):
    declared = _seed(
        tmp_path / "declared.toml",
        '[[entity]]\nkey="provider:casa_ha"\nkind="provider"\ntrusted=true\n',
    )
    empty = _seed(tmp_path / "empty.toml", "", ceiling=("casa_ha",))
    postgres_store.apply_entity_seed(declared)
    postgres_store.apply_entity_seed(empty)
    assert postgres_store.get_entity("provider:casa_ha").status == "retired"

    postgres_store.refresh_providers(("casa_ha", "otro"))
    external_seed = _seed(
        tmp_path / "external.toml",
        '[[entity]]\nkey="provider:otro"\nkind="provider"\ntrusted=true\n',
        ceiling=("casa_ha", "otro"),
    )
    postgres_store.apply_entity_seed(external_seed)
    postgres_store.apply_entity_seed(empty)
    entity = postgres_store.get_entity("provider:otro")
    assert entity.status == "active"
    assert entity.curated == {}


def test_entity_versions_reject_update_and_delete(postgres_store):
    postgres_store.refresh_providers(("casa_ha",))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with postgres_store._connect() as connection:
            connection.execute("UPDATE entity_versions SET origin = 'cli'")
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with postgres_store._connect() as connection:
            connection.execute("DELETE FROM entity_versions")
