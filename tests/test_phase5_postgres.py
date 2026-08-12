from uuid import uuid4

from ianest_extended import RagChunkWrite


def test_phase5_ingest_is_idempotent(postgres_rag_store):
    corpus = f"phase5-idempotent-{uuid4()}"
    chunks = [
        RagChunkWrite(
            content="systemd administra servicios linux",
            source_ref="manual.md",
            ordinal=0,
        ),
        RagChunkWrite(
            content="journalctl consulta registros linux",
            source_ref="manual.md",
            ordinal=1,
        ),
    ]

    first = postgres_rag_store.ingest(
        corpus_name=corpus,
        domain="linux",
        chunks=chunks,
    )
    second = postgres_rag_store.ingest(
        corpus_name=corpus,
        domain="linux",
        chunks=chunks,
    )

    assert (first.inserted, first.updated) == (2, 0)
    assert (second.inserted, second.updated) == (0, 2)
    with postgres_rag_store._connect() as connection:
        count = connection.execute(
            "SELECT count(*) AS count FROM rag_chunks WHERE corpus_id = %s",
            (first.corpus_id,),
        ).fetchone()["count"]
    assert count == 2


def test_phase5_domain_gate_and_global_similarity(postgres_rag_store):
    marker = str(uuid4())
    linux_content = f"linux kernel networking {marker}"
    postgres_rag_store.ingest(
        corpus_name=f"phase5-linux-{marker}",
        domain="linux",
        chunks=[RagChunkWrite(linux_content, "linux.md", 0)],
    )
    postgres_rag_store.ingest(
        corpus_name=f"phase5-cocina-{marker}",
        domain="cocina",
        chunks=[RagChunkWrite(f"receta cocina {marker}", "cocina.md", 0)],
    )

    linux = postgres_rag_store.retrieve(
        linux_content,
        domain="linux",
        top_k=10,
    )
    cocina = postgres_rag_store.retrieve(
        linux_content,
        domain="cocina",
        top_k=10,
    )
    global_items = postgres_rag_store.retrieve(linux_content, top_k=1000)

    assert any(item.content == linux_content for item in linux)
    assert all(item.content != linux_content for item in cocina)
    assert any(item.content == linux_content for item in global_items)
