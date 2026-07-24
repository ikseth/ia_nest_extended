import os
from urllib.parse import urlparse

import pytest


@pytest.fixture(scope="session")
def postgres_store():
    psycopg = pytest.importorskip(
        "psycopg",
        reason="psycopg no instalado; tests postgres omitidos",
    )
    dsn = os.environ.get("IANEST_EXTENDED_TEST_DSN")
    if not dsn:
        pytest.skip(
            "IANEST_EXTENDED_TEST_DSN no definido; tests postgres omitidos"
        )
    hostname = urlparse(dsn).hostname
    if hostname not in {"127.0.0.1", "localhost", "::1"}:
        pytest.skip(
            "el DSN no apunta a localhost; no se conectan hosts remotos"
        )

    from ianest_extended import FakeEmbedder
    from ianest_extended.adapters import PostgresMemoryStore

    dimension = int(
        os.environ.get("IANEST_EXTENDED_EMBEDDING_DIMENSION", "16")
    )
    store = PostgresMemoryStore(dsn, FakeEmbedder(dimension))
    try:
        store.migrate()
    except psycopg.OperationalError as exc:
        pytest.skip(f"postgres local no disponible: {exc}")
    return store
