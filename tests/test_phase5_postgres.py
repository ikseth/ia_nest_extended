from pathlib import Path
from uuid import uuid4

from ianest_extended import FakeEmbedder, RagChunkWrite
from ianest_extended.adapters import PostgresRagStore


def _write(content):
    return [RagChunkWrite(content, "manual.md", 0)]


def test_phase5b_multi_domain_ingest_is_idempotent(postgres_rag_store):
    marker = str(uuid4())
    chunks = _write(f"systemd administra servicios linux {marker}")

    first = postgres_rag_store.ingest(
        corpus_name=f"phase5b-idempotent-{marker}",
        domains=["linux", "codigo"],
        chunks=chunks,
    )
    second = postgres_rag_store.ingest(
        corpus_name=f"phase5b-idempotent-{marker}",
        domains=["linux", "codigo"],
        chunks=chunks,
    )

    assert (first.inserted, first.updated) == (1, 0)
    assert (second.inserted, second.updated) == (0, 1)
    with postgres_rag_store._connect() as connection:
        links = connection.execute(
            """
            SELECT domain, source, confirmed
            FROM rag_corpus_domains
            WHERE corpus_id = %s
            ORDER BY domain
            """,
            (first.corpus_id,),
        ).fetchall()
    assert [(row["domain"], row["source"], row["confirmed"]) for row in links] == [
        ("codigo", "manual", True),
        ("linux", "manual", True),
    ]


def test_phase5b_corpus_is_retrieved_through_each_confirmed_domain(
    postgres_rag_store,
):
    marker = str(uuid4())
    content = f"unix shell scripting {marker}"
    postgres_rag_store.ingest(
        corpus_name=f"phase5b-nm-{marker}",
        domains=["linux", "codigo"],
        chunks=_write(content),
    )

    linux = postgres_rag_store.retrieve(content, domain="linux", top_k=1000)
    codigo = postgres_rag_store.retrieve(content, domain="codigo", top_k=1000)

    assert any(item.content == content for item in linux)
    assert any(item.content == content for item in codigo)


def test_phase5b_domain_gate_prevents_cross_domain_collision(
    postgres_rag_store,
):
    marker = str(uuid4())
    linux_content = f"linux kernel networking {marker}"
    codigo_content = f"python type checking {marker}"
    postgres_rag_store.ingest(
        corpus_name=f"phase5b-linux-{marker}",
        domains=["linux"],
        chunks=_write(linux_content),
    )
    postgres_rag_store.ingest(
        corpus_name=f"phase5b-codigo-{marker}",
        domains=["codigo"],
        chunks=_write(codigo_content),
    )

    codigo = postgres_rag_store.retrieve(
        linux_content,
        domain="codigo",
        top_k=1000,
    )
    global_items = postgres_rag_store.retrieve(linux_content, top_k=1000)

    assert all(item.content != linux_content for item in codigo)
    assert any(item.content == linux_content for item in global_items)


def test_phase5b_unconfirmed_link_does_not_gate_until_confirmed(
    postgres_rag_store,
):
    marker = str(uuid4())
    content = f"candidate domain knowledge {marker}"
    result = postgres_rag_store.ingest(
        corpus_name=f"phase5b-confirmation-{marker}",
        domains=[],
        chunks=_write(content),
    )
    with postgres_rag_store._connect() as connection:
        connection.execute(
            """
            INSERT INTO rag_corpus_domains (
                id, corpus_id, domain, source, confidence, confirmed
            )
            VALUES (%s, %s, 'linux', 'auto', 0.9, false)
            """,
            (uuid4(), result.corpus_id),
        )

    before = postgres_rag_store.retrieve(content, domain="linux", top_k=1000)
    assert all(item.content != content for item in before)

    with postgres_rag_store._connect() as connection:
        connection.execute(
            """
            UPDATE rag_corpus_domains
            SET confirmed = true
            WHERE corpus_id = %s AND domain = 'linux'
            """,
            (result.corpus_id,),
        )
    after = postgres_rag_store.retrieve(content, domain="linux", top_k=1000)
    assert any(item.content == content for item in after)


def test_phase5b_migrates_legacy_domain_without_losing_retrieval(
    postgres_rag_store,
):
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    schema = f"phase5b_{uuid4().hex}"
    parameters = conninfo_to_dict(postgres_rag_store._dsn)
    parameters["options"] = f"-c search_path={schema},public"
    isolated_dsn = make_conninfo(**parameters)
    dimension = postgres_rag_store._embedder.dimension
    migration = (
        Path(__file__).resolve().parents[1] / "db" / "migrations" / "0002_rag.sql"
    ).read_text(encoding="ascii").replace(
        "{{embedding_dimension}}",
        str(dimension),
    )
    content = f"legacy linux knowledge {uuid4()}"
    embedded = postgres_rag_store._embedder.embed(content)
    vector = "[" + ",".join(str(value) for value in embedded) + "]"

    with psycopg.connect(postgres_rag_store._dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    try:
        with psycopg.connect(isolated_dsn) as connection:
            connection.execute(migration)
            corpus_id = connection.execute(
                """
                INSERT INTO rag_corpora (name, domain)
                VALUES ('legacy', 'linux')
                RETURNING id
                """
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO rag_chunks (
                    corpus_id, content, embedding, source_ref, ordinal
                )
                VALUES (%s, %s, %s::vector, 'legacy.md', 0)
                """,
                (corpus_id, content, vector),
            )

        store = PostgresRagStore(isolated_dsn, FakeEmbedder(dimension))
        store.migrate()
        found = store.retrieve(content, domain="linux", top_k=10)
        with store._connect() as connection:
            link = connection.execute(
                """
                SELECT source, confidence, confirmed
                FROM rag_corpus_domains
                WHERE corpus_id = %s AND domain = 'linux'
                """,
                (corpus_id,),
            ).fetchone()
            old_column = connection.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'rag_corpora'
                  AND column_name = 'domain'
                """,
                (schema,),
            ).fetchone()

        assert (link["source"], link["confidence"], link["confirmed"]) == (
            "manual",
            None,
            True,
        )
        assert old_column is None
        assert any(item.content == content for item in found)
    finally:
        with psycopg.connect(
            postgres_rag_store._dsn,
            autocommit=True,
        ) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )
