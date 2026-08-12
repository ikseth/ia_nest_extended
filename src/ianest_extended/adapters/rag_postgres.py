"""Adaptador postgres+pgvector del sustrato RAG."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from ..errors import InvalidRagInputError, RagSchemaError
from ..models import RagChunk, RagChunkWrite, RagIngestResult
from ..ports import Embedder


class PostgresRagStore:
    """Catalogo curado y recuperacion vectorial, separado de memoria."""

    def __init__(
        self,
        dsn: str,
        embedder: Embedder,
        migration_path: Path | None = None,
    ) -> None:
        self._dsn = dsn
        self._embedder = embedder
        self._migration_path = migration_path or _default_migration_path()

    def migrate(self) -> None:
        template = self._migration_path.read_text(encoding="ascii")
        sql = template.replace(
            "{{embedding_dimension}}",
            str(self._embedder.dimension),
        )
        if "{{" in sql or "}}" in sql:
            raise RagSchemaError("la migracion RAG contiene parametros sin resolver")
        with self._connect() as connection:
            connection.execute(sql)
            row = connection.execute(
                """
                SELECT format_type(attribute.atttypid, attribute.atttypmod)
                       AS data_type
                FROM pg_attribute attribute
                WHERE attribute.attrelid = 'rag_chunks'::regclass
                  AND attribute.attname = 'embedding'
                  AND NOT attribute.attisdropped
                """
            ).fetchone()
        if row is None:
            raise RagSchemaError("no se encontro rag_chunks.embedding")
        match = re.fullmatch(r"vector\((\d+)\)", row["data_type"])
        if match is None or int(match.group(1)) != self._embedder.dimension:
            current = row["data_type"]
            raise RagSchemaError(
                "rag_chunks.embedding usa "
                f"{current}; se esperaba vector({self._embedder.dimension}). "
                "El reindexado de dimension queda fuera de fase 5"
            )

    def ingest(
        self,
        *,
        corpus_name: str,
        domain: str,
        chunks: tuple[RagChunkWrite, ...] | list[RagChunkWrite],
        description: str = "",
    ) -> RagIngestResult:
        corpus_name = corpus_name.strip()
        domain = domain.strip()
        if not corpus_name or not domain:
            raise InvalidRagInputError("corpus_name y domain no pueden estar vacios")
        _validate_chunks(chunks)

        with self._connect() as connection:
            corpus = connection.execute(
                """
                INSERT INTO rag_corpora (id, name, domain, description)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (name, domain) DO UPDATE SET
                    description = CASE
                        WHEN EXCLUDED.description = '' THEN rag_corpora.description
                        ELSE EXCLUDED.description
                    END,
                    status = 'active',
                    version = CASE
                        WHEN rag_corpora.status <> 'active'
                          OR (EXCLUDED.description <> ''
                              AND EXCLUDED.description <> rag_corpora.description)
                        THEN rag_corpora.version + 1
                        ELSE rag_corpora.version
                    END
                RETURNING id
                """,
                (uuid4(), corpus_name, domain, description.strip()),
            ).fetchone()
            corpus_id = corpus["id"]
            existing = {
                (row["source_ref"], row["ordinal"])
                for row in connection.execute(
                    """
                    SELECT source_ref, ordinal
                    FROM rag_chunks
                    WHERE corpus_id = %s
                    """,
                    (corpus_id,),
                ).fetchall()
            }
            for chunk in chunks:
                embedding = self._embedder.embed(chunk.content)
                connection.execute(
                    """
                    INSERT INTO rag_chunks (
                        id, corpus_id, content, embedding, source_ref, ordinal
                    )
                    VALUES (%s, %s, %s, %s::vector, %s, %s)
                    ON CONFLICT (corpus_id, source_ref, ordinal) DO UPDATE SET
                        content = EXCLUDED.content,
                        embedding = EXCLUDED.embedding
                    """,
                    (
                        uuid4(),
                        corpus_id,
                        chunk.content,
                        _vector_literal(embedding),
                        chunk.source_ref,
                        chunk.ordinal,
                    ),
                )
        updated = sum(
            (chunk.source_ref, chunk.ordinal) in existing for chunk in chunks
        )
        return RagIngestResult(
            corpus_id=corpus_id,
            corpus_name=corpus_name,
            domain=domain,
            inserted=len(chunks) - updated,
            updated=updated,
        )

    def retrieve(
        self,
        query_text: str,
        *,
        domain: str | None = None,
        top_k: int = 3,
    ) -> tuple[RagChunk, ...]:
        if not query_text.strip():
            raise InvalidRagInputError("query_text no puede estar vacio")
        if top_k <= 0:
            raise InvalidRagInputError("top_k debe ser mayor que cero")
        if domain is not None and not domain.strip():
            raise InvalidRagInputError("domain no puede estar vacio")
        embedding = self._embedder.embed(query_text)
        vector = _vector_literal(embedding)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT chunk.*, corpus.name AS corpus_name,
                       corpus.domain,
                       1 - (chunk.embedding <=> %s::vector) AS score
                FROM rag_chunks chunk
                JOIN rag_corpora corpus ON corpus.id = chunk.corpus_id
                WHERE corpus.status = 'active'
                  AND (%s::text IS NULL OR corpus.domain = %s)
                ORDER BY chunk.embedding <=> %s::vector,
                         chunk.created_at,
                         chunk.id
                LIMIT %s
                """,
                (vector, domain, domain, vector, top_k),
            ).fetchall()
        return tuple(
            RagChunk(
                id=row["id"],
                corpus_id=row["corpus_id"],
                corpus_name=row["corpus_name"],
                domain=row["domain"],
                content=row["content"],
                source_ref=row["source_ref"],
                ordinal=row["ordinal"],
                score=float(row["score"]),
                created_at=row["created_at"],
            )
            for row in rows
        )

    def _connect(self):
        return psycopg.connect(self._dsn, row_factory=dict_row)


def _validate_chunks(chunks) -> None:
    seen: set[tuple[str, int]] = set()
    for chunk in chunks:
        if not chunk.content.strip() or not chunk.source_ref.strip():
            raise InvalidRagInputError(
                "content y source_ref de cada chunk no pueden estar vacios"
            )
        if chunk.ordinal < 0:
            raise InvalidRagInputError("ordinal no puede ser negativo")
        key = (chunk.source_ref, chunk.ordinal)
        if key in seen:
            raise InvalidRagInputError(
                "la ingesta contiene source_ref+ordinal duplicado"
            )
        seen.add(key)


def _vector_literal(vector) -> str:
    return "[" + ",".join(format(float(value), ".17g") for value in vector) + "]"


def _default_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "migrations"
        / "0002_rag.sql"
    )
