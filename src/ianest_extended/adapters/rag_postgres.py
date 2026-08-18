"""Adaptador postgres+pgvector del sustrato RAG."""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from ..errors import (
    CorpusNotFoundError,
    InvalidRagInputError,
    KnowledgeLinkNotFoundError,
    ProtectedKnowledgeLinkError,
    RagSchemaError,
    SchemaMigrationRequiredError,
)
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
        self._domain_migration_path = _default_domain_migration_path()

    def verify_schema(self) -> None:
        """Comprueba el esquema RAG SIN mutarlo (migracion explicita)."""
        with self._connect() as connection:
            for relation in ("rag_corpora", "rag_chunks", "rag_corpus_domains"):
                exists = connection.execute(
                    "SELECT to_regclass(%s) AS relation",
                    (relation,),
                ).fetchone()["relation"]
                if exists is None:
                    raise SchemaMigrationRequiredError(
                        "el esquema RAG no esta migrado "
                        f"(falta '{relation}'); ejecuta "
                        "'ianest-extended runtime migrate'",
                        relation,
                    )

    def migrate(self) -> None:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT to_regclass('rag_corpora') AS relation"
            ).fetchone()["relation"]
            if exists is None:
                template = self._migration_path.read_text(encoding="ascii")
                sql = template.replace(
                    "{{embedding_dimension}}",
                    str(self._embedder.dimension),
                )
                if "{{" in sql or "}}" in sql:
                    raise RagSchemaError(
                        "la migracion RAG contiene parametros sin resolver"
                    )
                connection.execute(sql)
            connection.execute(
                self._domain_migration_path.read_text(encoding="ascii")
            )
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
        domains: tuple[str, ...] | list[str],
        chunks: tuple[RagChunkWrite, ...] | list[RagChunkWrite],
        description: str = "",
    ) -> RagIngestResult:
        corpus_name = corpus_name.strip()
        normalized_domains = _normalize_domains(domains)
        if not corpus_name:
            raise InvalidRagInputError("corpus_name no puede estar vacio")
        _validate_chunks(chunks)

        with self._connect() as connection:
            corpus = connection.execute(
                """
                SELECT id
                FROM rag_corpora
                WHERE name = %s
                ORDER BY created_at, id
                LIMIT 1
                """,
                (corpus_name,),
            ).fetchone()
            if corpus is None:
                corpus = connection.execute(
                    """
                    INSERT INTO rag_corpora (id, name, description)
                    VALUES (%s, %s, %s)
                    RETURNING id
                    """,
                    (uuid4(), corpus_name, description.strip()),
                ).fetchone()
            else:
                connection.execute(
                    """
                    UPDATE rag_corpora
                    SET description = CASE
                            WHEN %s = '' THEN description
                            ELSE %s
                        END,
                        status = 'active',
                        version = CASE
                            WHEN status <> 'active'
                              OR (%s <> '' AND %s <> description)
                            THEN version + 1
                            ELSE version
                        END
                    WHERE id = %s
                    """,
                    (
                        description.strip(),
                        description.strip(),
                        description.strip(),
                        description.strip(),
                        corpus["id"],
                    ),
                )
            corpus_id = corpus["id"]
            for domain in normalized_domains:
                connection.execute(
                    """
                    INSERT INTO rag_corpus_domains (
                        id, corpus_id, domain, source, confidence, confirmed
                    )
                    VALUES (%s, %s, %s, 'manual', NULL, true)
                    ON CONFLICT (corpus_id, domain) DO UPDATE SET
                        source = 'manual',
                        confidence = NULL,
                        confirmed = true
                    """,
                    (uuid4(), corpus_id, domain),
                )
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
            domains=normalized_domains,
            inserted=len(chunks) - updated,
            updated=updated,
        )

    def retrieve(
        self,
        query_text: str,
        *,
        domain: str | None = None,
        top_k: int = 3,
        min_score: float = 0.0,
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
                       ARRAY(
                           SELECT link.domain
                           FROM rag_corpus_domains link
                           WHERE link.corpus_id = corpus.id
                             AND link.confirmed
                           ORDER BY link.domain
                       ) AS domains,
                       1 - (chunk.embedding <=> %s::vector) AS score
                FROM rag_chunks chunk
                JOIN rag_corpora corpus ON corpus.id = chunk.corpus_id
                WHERE corpus.status = 'active'
                  AND (
                      %s::text IS NULL
                      OR EXISTS (
                          SELECT 1
                          FROM rag_corpus_domains gate
                          WHERE gate.corpus_id = corpus.id
                            AND gate.domain = %s
                            AND gate.confirmed
                      )
                  )
                  AND (1 - (chunk.embedding <=> %s::vector)) >= %s
                ORDER BY chunk.embedding <=> %s::vector,
                         chunk.created_at,
                         chunk.id
                LIMIT %s
                """,
                (vector, domain, domain, vector, min_score, vector, top_k),
            ).fetchall()
        return tuple(
            RagChunk(
                id=row["id"],
                corpus_id=row["corpus_id"],
                corpus_name=row["corpus_name"],
                domains=tuple(row["domains"]),
                content=row["content"],
                source_ref=row["source_ref"],
                ordinal=row["ordinal"],
                score=float(row["score"]),
                created_at=row["created_at"],
            )
            for row in rows
        )

    def confirmed_corpus_counts(
        self,
        domains: tuple[str, ...] | list[str],
    ) -> dict[str, int]:
        normalized = _normalize_domains(domains)
        if not normalized:
            return {}
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT link.domain, count(DISTINCT link.corpus_id) AS total
                FROM rag_corpus_domains link
                JOIN rag_corpora corpus ON corpus.id = link.corpus_id
                WHERE link.domain = ANY(%s)
                  AND link.confirmed
                  AND corpus.status = 'active'
                GROUP BY link.domain
                """,
                (list(normalized),),
            ).fetchall()
        found = {row["domain"]: int(row["total"]) for row in rows}
        return {domain: found.get(domain, 0) for domain in normalized}

    def sample_corpus(self, corpus_name: str, max_chars: int) -> str:
        if max_chars <= 0:
            raise InvalidRagInputError("max_chars debe ser mayor que cero")
        with self._connect() as connection:
            corpus_id = _find_corpus_id(connection, corpus_name)
            rows = connection.execute(
                """
                SELECT content
                FROM rag_chunks
                WHERE corpus_id = %s
                ORDER BY source_ref, ordinal, created_at, id
                """,
                (corpus_id,),
            ).fetchall()
        sample = "\n\n".join(row["content"] for row in rows)[:max_chars]
        if not sample.strip():
            raise InvalidRagInputError("el corpus no contiene texto para clasificar")
        return sample

    def propose_domain(
        self,
        corpus_name: str,
        domain: str,
        confidence: float,
    ) -> bool:
        domain = _validate_domain(domain)
        if isinstance(confidence, bool) or not 0.0 <= confidence <= 1.0:
            raise InvalidRagInputError("confidence debe estar entre 0 y 1")
        with self._connect() as connection:
            corpus_id = _find_corpus_id(connection, corpus_name)
            row = connection.execute(
                """
                INSERT INTO rag_corpus_domains (
                    id, corpus_id, domain, source, confidence, confirmed
                )
                VALUES (%s, %s, %s, 'auto', %s, false)
                ON CONFLICT (corpus_id, domain) DO UPDATE SET
                    confidence = EXCLUDED.confidence
                WHERE rag_corpus_domains.source = 'auto'
                  AND NOT rag_corpus_domains.confirmed
                RETURNING source, confirmed
                """,
                (uuid4(), corpus_id, domain, confidence),
            ).fetchone()
        return row is not None

    def confirm_domain(self, corpus_name: str, domain: str) -> bool:
        domain = _validate_domain(domain)
        with self._connect() as connection:
            corpus_id = _find_corpus_id(connection, corpus_name)
            current = connection.execute(
                """
                SELECT confirmed
                FROM rag_corpus_domains
                WHERE corpus_id = %s AND domain = %s
                FOR UPDATE
                """,
                (corpus_id, domain),
            ).fetchone()
            if current is None:
                raise KnowledgeLinkNotFoundError(
                    f"no existe vinculo para corpus '{corpus_name}' y dominio '{domain}'"
                )
            if current["confirmed"]:
                return False
            connection.execute(
                """
                UPDATE rag_corpus_domains
                SET confirmed = true
                WHERE corpus_id = %s AND domain = %s
                """,
                (corpus_id, domain),
            )
        return True

    def reject_domain(self, corpus_name: str, domain: str) -> bool:
        domain = _validate_domain(domain)
        with self._connect() as connection:
            corpus_id = _find_corpus_id(connection, corpus_name)
            current = connection.execute(
                """
                SELECT source, confirmed
                FROM rag_corpus_domains
                WHERE corpus_id = %s AND domain = %s
                FOR UPDATE
                """,
                (corpus_id, domain),
            ).fetchone()
            if current is None:
                return False
            if current["source"] != "auto" or current["confirmed"]:
                raise ProtectedKnowledgeLinkError(
                    "no se puede rechazar un vinculo manual o confirmado"
                )
            connection.execute(
                """
                DELETE FROM rag_corpus_domains
                WHERE corpus_id = %s AND domain = %s
                """,
                (corpus_id, domain),
            )
        return True

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


def _normalize_domains(domains) -> tuple[str, ...]:
    normalized: list[str] = []
    for domain in domains:
        value = domain.strip()
        if not value:
            raise InvalidRagInputError("domain no puede estar vacio")
        if value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _validate_domain(domain: str) -> str:
    value = domain.strip()
    if not value:
        raise InvalidRagInputError("domain no puede estar vacio")
    return value


def _find_corpus_id(connection, corpus_name: str):
    name = corpus_name.strip()
    if not name:
        raise InvalidRagInputError("corpus_name no puede estar vacio")
    row = connection.execute(
        """
        SELECT id
        FROM rag_corpora
        WHERE name = %s
        ORDER BY created_at, id
        LIMIT 1
        """,
        (name,),
    ).fetchone()
    if row is None:
        raise CorpusNotFoundError(f"corpus no encontrado: '{name}'")
    return row["id"]


def _vector_literal(vector) -> str:
    return "[" + ",".join(format(float(value), ".17g") for value in vector) + "]"


def _default_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "migrations"
        / "0002_rag.sql"
    )


def _default_domain_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "migrations"
        / "0003_rag_domains.sql"
    )
