from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.errors import RaiseException

from ianest_extended import RagChunkWrite
from ianest_extended.ingest import ingest_path


def _chunks(*items):
    return [
        RagChunkWrite(content=content, source_ref=source_ref, ordinal=ordinal)
        for source_ref, ordinal, content in items
    ]


def _stored_chunks(store, corpus_id):
    with store._connect() as connection:
        rows = connection.execute(
            """
            SELECT source_ref, ordinal, content
            FROM rag_chunks
            WHERE corpus_id = %s
            ORDER BY source_ref, ordinal
            """,
            (corpus_id,),
        ).fetchall()
    return [
        (row["source_ref"], row["ordinal"], row["content"])
        for row in rows
    ]


def test_reingest_prunes_chunks_when_corpus_shrinks(postgres_rag_store):
    corpus = f"d9-shrink-{uuid4()}"
    first = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=_chunks(
            ("manual.md", 0, "fragmento cero"),
            ("manual.md", 1, "fragmento uno"),
            ("manual.md", 2, "fragmento dos"),
        ),
    )

    second = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=_chunks(("manual.md", 0, "fragmento cero nuevo")),
    )

    assert second.deleted == 2
    assert _stored_chunks(postgres_rag_store, first.corpus_id) == [
        ("manual.md", 0, "fragmento cero nuevo")
    ]


def test_reingest_prunes_removed_file_from_directory(
    postgres_rag_store,
    tmp_path,
):
    first_file = tmp_path / "primero.md"
    second_file = tmp_path / "segundo.md"
    first_file.write_text("contenido primero", encoding="utf-8")
    second_file.write_text("contenido segundo", encoding="utf-8")
    corpus = f"d9-directory-{uuid4()}"

    first = ingest_path(
        store=postgres_rag_store,
        core=object(),
        path=tmp_path,
        corpus_name=corpus,
        domains=(),
        source_ref=None,
        chunk_tokens=20,
        overlap=0.15,
    )
    second_file.unlink()
    second = ingest_path(
        store=postgres_rag_store,
        core=object(),
        path=tmp_path,
        corpus_name=corpus,
        domains=(),
        source_ref=None,
        chunk_tokens=20,
        overlap=0.15,
    )

    assert second.deleted == 1
    assert _stored_chunks(postgres_rag_store, first.corpus_id) == [
        ("primero.md", 0, "contenido primero")
    ]


def test_pruning_one_corpus_does_not_touch_another(postgres_rag_store):
    marker = str(uuid4())
    first = postgres_rag_store.ingest(
        corpus_name=f"d9-isolated-a-{marker}",
        domains=[],
        chunks=_chunks(
            ("a.md", 0, "a cero"),
            ("a.md", 1, "a uno"),
        ),
    )
    other = postgres_rag_store.ingest(
        corpus_name=f"d9-isolated-b-{marker}",
        domains=[],
        chunks=_chunks(("b.md", 0, "b intacto")),
    )

    result = postgres_rag_store.ingest(
        corpus_name=f"d9-isolated-a-{marker}",
        domains=[],
        chunks=_chunks(("a.md", 0, "a cero")),
    )

    assert result.deleted == 1
    assert _stored_chunks(postgres_rag_store, first.corpus_id) == [
        ("a.md", 0, "a cero")
    ]
    assert _stored_chunks(postgres_rag_store, other.corpus_id) == [
        ("b.md", 0, "b intacto")
    ]


def test_failed_upsert_rolls_back_before_pruning(postgres_rag_store):
    marker = uuid4().hex
    corpus = f"d9-atomic-{marker}"
    original = _chunks(
        ("manual.md", 0, "original cero"),
        ("manual.md", 1, "original uno"),
        ("retirado.md", 0, "no debe podarse"),
    )
    first = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=original,
    )
    expected = _stored_chunks(postgres_rag_store, first.corpus_id)
    function_name = f"d9_fail_upsert_{marker}"
    trigger_name = f"d9_fail_upsert_{marker}"

    with postgres_rag_store._connect() as connection:
        connection.execute(
            sql.SQL(
                """
                CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN
                    IF NEW.content = 'fallo deliberado' THEN
                        RAISE EXCEPTION 'fallo deliberado de upsert';
                    END IF;
                    RETURN NEW;
                END
                $$
                """
            ).format(sql.Identifier(function_name))
        )
        connection.execute(
            sql.SQL(
                "CREATE TRIGGER {} BEFORE INSERT OR UPDATE ON rag_chunks "
                "FOR EACH ROW EXECUTE FUNCTION {}()"
            ).format(
                sql.Identifier(trigger_name),
                sql.Identifier(function_name),
            )
        )

    try:
        with pytest.raises(RaiseException, match="fallo deliberado de upsert"):
            postgres_rag_store.ingest(
                corpus_name=corpus,
                domains=[],
                chunks=_chunks(
                    ("manual.md", 0, "cambio que debe revertirse"),
                    ("manual.md", 1, "fallo deliberado"),
                ),
            )
    finally:
        with postgres_rag_store._connect() as connection:
            connection.execute(
                sql.SQL("DROP TRIGGER {} ON rag_chunks").format(
                    sql.Identifier(trigger_name)
                )
            )
            connection.execute(
                sql.SQL("DROP FUNCTION {}()").format(
                    sql.Identifier(function_name)
                )
            )

    assert _stored_chunks(postgres_rag_store, first.corpus_id) == expected


def test_reingest_same_content_is_idempotent(postgres_rag_store):
    corpus = f"d9-idempotent-{uuid4()}"
    chunks = _chunks(("manual.md", 0, "contenido estable"))

    first = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=chunks,
    )
    second = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=chunks,
    )

    assert (first.inserted, first.updated, first.deleted) == (1, 0, 0)
    assert (second.inserted, second.deleted) == (0, 0)


def test_empty_reingest_prunes_every_chunk(postgres_rag_store):
    corpus = f"d9-empty-{uuid4()}"
    first = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=_chunks(("manual.md", 0, "contenido retirado")),
    )

    second = postgres_rag_store.ingest(
        corpus_name=corpus,
        domains=[],
        chunks=[],
    )

    assert second.deleted == 1
    assert _stored_chunks(postgres_rag_store, first.corpus_id) == []
