"""Adaptador postgres+pgvector del sustrato de memoria."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from ..errors import (
    EngramNotFoundError,
    InvalidConsolidationEventError,
    InvalidEmbeddingDimensionError,
    InvalidEngramError,
    InvalidMemoryTypeError,
    SchemaMigrationRequiredError,
    ScopeViolationError,
    UnsupportedWriteError,
    WriteAuthorityError,
)
from ..models import (
    ConsolidationEvent,
    ConsolidationResult,
    Engram,
    EngramStatus,
    EngramWrite,
    EntityProfile,
    MemoryClass,
    MemoryIdentity,
    MemoryType,
    Principal,
    RecallItem,
    RecallQuery,
    RetrievalMode,
    Scope,
)
from ..ports import Embedder
from ..registry import MemoryTypeRegistry, derive_memory_key, seed_memory_types


class PostgresMemoryStore:
    """Almacen de referencia con reglas de dominio antes de cada mutacion."""

    def __init__(
        self,
        dsn: str,
        embedder: Embedder | None,
        migration_path: Path | None = None,
    ) -> None:
        if embedder is not None and embedder.dimension <= 0:
            raise InvalidEmbeddingDimensionError(
                "embedding_dimension debe ser mayor que cero"
            )
        self._dsn = dsn
        self._embedder = embedder
        self._migration_path = migration_path or _default_migration_path()

    def verify_schema(self) -> None:
        """Comprueba el esquema SIN mutarlo (migracion explicita, ADR 0011)."""
        with self._connect() as connection:
            for relation in ("memory_types", "engrams", "memory_links"):
                exists = connection.execute(
                    "SELECT to_regclass(%s) AS relation",
                    (relation,),
                ).fetchone()["relation"]
                if exists is None:
                    raise SchemaMigrationRequiredError(
                        "el esquema de memoria no esta migrado "
                        f"(falta '{relation}'); ejecuta "
                        "'ianest-extended runtime migrate'",
                        relation,
                    )

    def migrate(self) -> None:
        embedder = self._require_embedder()
        template = self._migration_path.read_text(encoding="ascii")
        sql = template.replace(
            "{{embedding_dimension}}",
            str(embedder.dimension),
        )
        if "{{" in sql or "}}" in sql:
            raise InvalidEmbeddingDimensionError(
                "la migracion contiene parametros sin resolver"
            )
        with self._connect() as connection:
            connection.execute(sql)
            self._ensure_embedding_dimension(connection)
        for memory_type in seed_memory_types():
            self.register_type(memory_type)

    def _ensure_embedding_dimension(self, connection) -> None:
        row = connection.execute(
            """
            SELECT format_type(attribute.atttypid, attribute.atttypmod)
                   AS data_type
            FROM pg_attribute attribute
            WHERE attribute.attrelid = 'engrams'::regclass
              AND attribute.attname = 'embedding'
              AND NOT attribute.attisdropped
            """
        ).fetchone()
        if row is None:
            raise InvalidEmbeddingDimensionError(
                "no se encontro la columna engrams.embedding"
            )
        match = re.fullmatch(r"vector\((\d+)\)", row["data_type"])
        if match is None:
            raise InvalidEmbeddingDimensionError(
                "engrams.embedding no declara una dimension vectorial"
            )
        current_dimension = int(match.group(1))
        embedder = self._require_embedder()
        if current_dimension == embedder.dimension:
            return

        rows = connection.execute(
            "SELECT id, content FROM engrams ORDER BY created_at, id"
        ).fetchall()
        connection.execute(
            """
            ALTER TABLE engrams
            ALTER COLUMN embedding TYPE vector
            USING embedding::vector
            """
        )
        for engram in rows:
            embedding = embedder.embed(engram["content"])
            connection.execute(
                """
                UPDATE engrams
                SET embedding = %s::vector
                WHERE id = %s
                """,
                (_vector_literal(embedding), engram["id"]),
            )
        dimension = embedder.dimension
        connection.execute(
            f"""
            ALTER TABLE engrams
            ALTER COLUMN embedding TYPE vector({dimension})
            USING embedding::vector({dimension})
            """
        )

    def register_type(self, memory_type: MemoryType) -> None:
        existing_types = tuple(self.list_types())
        same_name = next(
            (item for item in existing_types if item.name == memory_type.name),
            None,
        )
        if same_name is not None:
            if same_name == memory_type:
                return
            raise InvalidMemoryTypeError(
                f"el tipo {memory_type.name!r} ya existe con otra declaracion"
            )
        registry = MemoryTypeRegistry(existing_types)
        registry.register(memory_type)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_types (
                    name, "class", writer_principal, retrieval_mode, scope,
                    namespaces, w_recency, w_similarity, w_stability, w_score,
                    half_life_seconds, status, version
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    memory_type.name,
                    memory_type.memory_class.value,
                    memory_type.writer_principal.value,
                    memory_type.retrieval_mode.value,
                    memory_type.scope.value,
                    list(memory_type.namespaces),
                    memory_type.w_recency,
                    memory_type.w_similarity,
                    memory_type.w_stability,
                    memory_type.w_score,
                    memory_type.half_life_seconds,
                    memory_type.status,
                    memory_type.version,
                ),
            )

    def list_types(self) -> tuple[MemoryType, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT name, "class", writer_principal, retrieval_mode, scope,
                       namespaces, w_recency, w_similarity, w_stability,
                       w_score, half_life_seconds, status, version
                FROM memory_types
                ORDER BY created_at, name
                """
            ).fetchall()
        return tuple(_memory_type_from_row(row) for row in rows)

    def write(self, principal: Principal, request: EngramWrite) -> Engram:
        memory_type = self._get_type(request.type_name)
        _require_authority(memory_type, principal)
        if memory_type.retrieval_mode is RetrievalMode.PROFILE_LOOKUP:
            raise UnsupportedWriteError(
                "profile_lookup se escribe mediante write_entity"
            )
        key = derive_memory_key(
            memory_type,
            request.identity,
            request.namespace,
            request.entity_id,
        )
        if not 0.0 <= request.score <= 1.0:
            raise InvalidEngramError("score debe estar entre 0 y 1")
        if request.stability < 0:
            raise InvalidEngramError("stability no puede ser negativo")

        engram_id = uuid4()
        embedding = self._require_embedder().embed(request.content)
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO engrams (
                    id, type_name, user_id, session_id, namespace, content,
                    embedding, score, stability, service, domain_tag,
                    entity_refs, unresolved_mentions, source_trace_id
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s,
                    %s, %s, %s
                )
                RETURNING *
                """,
                (
                    engram_id,
                    memory_type.name,
                    key.user_id,
                    key.session_id,
                    key.namespace,
                    request.content,
                    _vector_literal(embedding),
                    request.score,
                    request.stability,
                    request.service,
                    request.domain_tag,
                    list(request.entity_refs),
                    list(request.unresolved_mentions),
                    request.source_trace_id,
                ),
            ).fetchone()
        return _engram_from_row(row)

    def write_entity(
        self,
        principal: Principal,
        type_name: str,
        entity: EntityProfile,
    ) -> EntityProfile:
        memory_type = self._get_type(type_name)
        _require_authority(memory_type, principal)
        if (
            memory_type.retrieval_mode is not RetrievalMode.PROFILE_LOOKUP
            or memory_type.scope is not Scope.ENTITY
        ):
            raise UnsupportedWriteError(
                "write_entity exige un tipo profile_lookup con scope entity"
            )
        derive_memory_key(
            memory_type,
            MemoryIdentity(),
            memory_type.namespaces[0],
            entity.id,
        )
        with self._connect() as connection:
            row = connection.execute(
                """
                INSERT INTO entities (
                    id, kind, name, aliases, profile, status, version
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    kind = EXCLUDED.kind,
                    name = EXCLUDED.name,
                    aliases = EXCLUDED.aliases,
                    profile = EXCLUDED.profile,
                    status = EXCLUDED.status,
                    version = entities.version + 1,
                    updated_at = now()
                RETURNING *
                """,
                (
                    entity.id,
                    entity.kind,
                    entity.name,
                    list(entity.aliases),
                    json.dumps(entity.profile),
                    entity.status,
                    entity.version,
                ),
            ).fetchone()
        return _entity_from_row(row)

    def recall(self, query: RecallQuery) -> tuple[RecallItem, ...]:
        if not query.type_names:
            return ()
        registry = MemoryTypeRegistry(self.list_types())
        selected = tuple(registry.get(name) for name in query.type_names)
        items: list[RecallItem] = []

        ranked = tuple(
            item
            for item in selected
            if item.retrieval_mode is RetrievalMode.RANKED
        )
        always = tuple(
            item
            for item in selected
            if item.retrieval_mode is RetrievalMode.ALWAYS_INJECT
        )
        profiles = tuple(
            item
            for item in selected
            if item.retrieval_mode is RetrievalMode.PROFILE_LOOKUP
        )
        if ranked and query.top_k > 0:
            items.extend(self._recall_ranked(ranked, query))
        if always:
            items.extend(self._recall_always(always, query))
        if profiles:
            items.extend(self._recall_profiles(profiles, query))
        return tuple(
            sorted(items, key=lambda item: item.relevance, reverse=True)
        )

    def archive(
        self,
        principal: Principal,
        engram_id: UUID,
        reason: str,
    ) -> Engram:
        current = self.get_engram(engram_id)
        memory_type = self._get_type(current.type_name)
        _require_authority(memory_type, principal)
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE engrams
                SET status = 'archived',
                    archived_at = now(),
                    archived_reason = %s,
                    version = version + 1
                WHERE id = %s
                RETURNING *
                """,
                (reason, engram_id),
            ).fetchone()
        if row is None:
            raise EngramNotFoundError(f"engrama no encontrado: {engram_id}")
        return _engram_from_row(row)

    def get_engram(self, engram_id: UUID) -> Engram:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM engrams WHERE id = %s",
                (engram_id,),
            ).fetchone()
        if row is None:
            raise EngramNotFoundError(f"engrama no encontrado: {engram_id}")
        return _engram_from_row(row)

    def find_similar(
        self,
        *,
        user_id: str,
        namespace: str,
        text: str,
        threshold: float,
    ) -> Engram | None:
        if not 0.0 <= threshold <= 1.0:
            raise InvalidEngramError("threshold debe estar entre 0 y 1")
        if not user_id:
            raise ScopeViolationError("dedup exige user_id")
        episodic = self._get_type("episodic")
        derive_memory_key(
            episodic,
            MemoryIdentity(user_id=user_id),
            namespace,
        )
        embedding = self._require_embedder().embed(text)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM engrams
                WHERE type_name = 'episodic'
                  AND user_id = %s
                  AND session_id IS NULL
                  AND namespace = %s
                  AND status = 'active'
                  AND 1 - (embedding <=> %s::vector) >= %s
                ORDER BY embedding <=> %s::vector, created_at DESC
                LIMIT 1
                """,
                (
                    user_id,
                    namespace,
                    _vector_literal(embedding),
                    threshold,
                    _vector_literal(embedding),
                ),
            ).fetchone()
        return None if row is None else _engram_from_row(row)

    def reinforce(
        self,
        principal: Principal,
        engram_id: UUID,
    ) -> Engram:
        current = self.get_engram(engram_id)
        memory_type = self._get_type(current.type_name)
        _require_authority(memory_type, principal)
        with self._connect() as connection:
            row = connection.execute(
                """
                UPDATE engrams
                SET stability = stability + 1,
                    last_reinforced_at = now(),
                    version = version + 1
                WHERE id = %s AND status = 'active'
                RETURNING *
                """,
                (engram_id,),
            ).fetchone()
        if row is None:
            raise EngramNotFoundError(
                f"engrama activo no encontrado: {engram_id}"
            )
        return _engram_from_row(row)

    def find_dialogs_to_archive(
        self,
        *,
        now: datetime,
        hot_window_seconds: int,
    ) -> tuple[Engram, ...]:
        if hot_window_seconds <= 0:
            raise InvalidConsolidationEventError(
                "hot_window_seconds debe ser mayor que cero"
            )
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM engrams
                WHERE type_name = 'dialog'
                  AND status = 'active'
                  AND created_at < (
                      %s::timestamptz
                      - (%s * interval '1 second')
                  )
                ORDER BY created_at, id
                """,
                (now, hot_window_seconds),
            ).fetchall()
        return tuple(_engram_from_row(row) for row in rows)

    def find_episodic_to_promote(
        self,
        *,
        now: datetime,
        recency_max: float,
        min_stability: int,
        min_score: float,
    ) -> tuple[Engram, ...]:
        if not 0.0 <= recency_max <= 1.0:
            raise InvalidConsolidationEventError(
                "recency_max debe estar entre 0 y 1"
            )
        if min_stability < 0:
            raise InvalidConsolidationEventError(
                "min_stability no puede ser negativo"
            )
        if not 0.0 <= min_score <= 1.0:
            raise InvalidConsolidationEventError(
                "min_score debe estar entre 0 y 1"
            )
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT e.*
                FROM engrams e
                JOIN memory_types mt ON mt.name = e.type_name
                WHERE e.type_name = 'episodic'
                  AND e.status = 'active'
                  AND e.namespace <> 'tasks'
                  AND mt.half_life_seconds IS NOT NULL
                  AND power(
                      0.5,
                      GREATEST(
                          EXTRACT(
                              EPOCH FROM (
                                  %s::timestamptz
                                  - COALESCE(
                                      e.last_reinforced_at,
                                      e.created_at
                                  )
                              )
                          ),
                          0
                      ) / mt.half_life_seconds
                  ) < %s
                  AND (e.stability >= %s OR e.score >= %s)
                ORDER BY e.created_at, e.id
                """,
                (now, recency_max, min_stability, min_score),
            ).fetchall()
        return tuple(_engram_from_row(row) for row in rows)

    def execute_consolidation(
        self,
        event: ConsolidationEvent,
    ) -> ConsolidationResult:
        _validate_consolidation_event(event)
        target_type = None
        if event.target_type is not None:
            target_type = self._get_type(event.target_type)
            _require_authority(target_type, event.principal)
            if target_type.retrieval_mode is RetrievalMode.PROFILE_LOOKUP:
                raise UnsupportedWriteError(
                    "profile_lookup se escribe mediante write_entity"
                )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM engrams
                WHERE id = ANY(%s::uuid[])
                FOR UPDATE
                """,
                (list(event.source_ids),),
            ).fetchall()
            by_id = {row["id"]: row for row in rows}
            missing = [
                source_id
                for source_id in event.source_ids
                if source_id not in by_id
            ]
            if missing:
                raise EngramNotFoundError(
                    f"engramas fuente no encontrados: {missing!r}"
                )
            ordered_rows = [by_id[source_id] for source_id in event.source_ids]
            if any(
                row["status"] != EngramStatus.ACTIVE.value
                for row in ordered_rows
            ):
                raise InvalidConsolidationEventError(
                    "todos los engramas fuente deben estar activos"
                )

            target_row = None
            if target_type is not None:
                target_row = self._insert_consolidation_target(
                    connection,
                    event,
                    target_type,
                    ordered_rows,
                )
                for source_id in event.source_ids:
                    connection.execute(
                        """
                        INSERT INTO memory_links (
                            source_kind, source_id, target_engram_id, link_kind
                        )
                        VALUES ('engram', %s, %s, 'consolidated_from')
                        """,
                        (source_id, target_row["id"]),
                    )

            archived_rows = connection.execute(
                """
                UPDATE engrams
                SET status = 'archived',
                    archived_at = now(),
                    archived_reason = %s,
                    version = version + 1
                WHERE id = ANY(%s::uuid[])
                RETURNING *
                """,
                (event.reason, list(event.source_ids)),
            ).fetchall()

        archived_by_id = {row["id"]: row for row in archived_rows}
        first = ordered_rows[0]
        return ConsolidationResult(
            target=None if target_row is None else _engram_from_row(target_row),
            archived_sources=tuple(
                _engram_from_row(archived_by_id[source_id])
                for source_id in event.source_ids
            ),
            links_created=(
                len(event.source_ids) if target_row is not None else 0
            ),
            identity=MemoryIdentity(
                user_id=first["user_id"],
                session_id=first["session_id"],
                service=first["service"],
                domain_tag=first["domain_tag"],
                namespace=first["namespace"],
            ),
        )

    def _insert_consolidation_target(
        self,
        connection,
        event: ConsolidationEvent,
        target_type: MemoryType,
        source_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        first = source_rows[0]
        namespace = event.target_namespace
        if namespace is None:
            namespace = first["namespace"]
        keys = []
        for row in source_rows:
            keys.append(
                derive_memory_key(
                    target_type,
                    MemoryIdentity(
                        user_id=row["user_id"],
                        session_id=row["session_id"],
                    ),
                    namespace,
                )
            )
        if any(key != keys[0] for key in keys[1:]):
            raise InvalidConsolidationEventError(
                "las fuentes no comparten la clave del destino"
            )

        content = event.content
        assert content is not None
        if len(source_rows) == 1 and content == first["content"]:
            embedding = _parse_vector(first["embedding"])
        else:
            embedding = self._require_embedder().embed(content)
        entity_refs = tuple(
            dict.fromkeys(
                entity_id
                for row in source_rows
                for entity_id in row["entity_refs"]
            )
        )
        unresolved_mentions = tuple(
            dict.fromkeys(
                mention
                for row in source_rows
                for mention in row["unresolved_mentions"]
            )
        )
        row = connection.execute(
            """
            INSERT INTO engrams (
                id, type_name, user_id, session_id, namespace, content,
                embedding, score, stability, service, domain_tag,
                entity_refs, unresolved_mentions, source_trace_id
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s::vector, %s, %s, %s, %s,
                %s, %s, %s
            )
            RETURNING *
            """,
            (
                uuid4(),
                target_type.name,
                keys[0].user_id,
                keys[0].session_id,
                keys[0].namespace,
                content,
                _vector_literal(embedding),
                max(float(row["score"]) for row in source_rows),
                max(row["stability"] for row in source_rows),
                first["service"],
                first["domain_tag"],
                list(entity_refs),
                list(unresolved_mentions),
                first["source_trace_id"],
            ),
        ).fetchone()
        assert row is not None
        return row

    def _recall_ranked(
        self,
        memory_types: tuple[MemoryType, ...],
        query: RecallQuery,
    ) -> list[RecallItem]:
        """Recupera tipos `RANKED` (dialog/episodic/semantic).

        Filtro de dominio (D2, PLAN.md): una memoria sin `domain_tag` es
        SIEMPRE candidata (neutra, no incompatible); el filtro excluye solo
        las de un dominio DISTINTO del pedido. Sin dominio pedido, no hay
        filtro (comportamiento sin cambios).
        """
        scope_clauses: list[str] = []
        parameters: list[Any] = []
        for memory_type in memory_types:
            namespace = (
                None
                if memory_type.scope is Scope.SESSION
                else query.namespace
            )
            key = derive_memory_key(
                memory_type,
                query.identity,
                namespace,
                query.entity_id,
            )
            clause, values = _scope_clause(memory_type, key)
            scope_clauses.append(f"(e.type_name = %s AND {clause})")
            parameters.append(memory_type.name)
            parameters.extend(values)

        query_embedding = self._require_embedder().embed(query.text)
        now = query.now or datetime.now(UTC)
        # D4: el suelo de similitud gatea SOLO `episodic` (ruido reciente de
        # alto volumen). `semantic` ya paso un juicio de promocion y `dialog`
        # es continuidad, no pertinencia tematica; ninguno de los dos se
        # gatea aqui aunque la query traiga un `min_similarity`. Ver
        # docs/PLAN.md D4 y docs/handoff/deuda_d4_brief.md.
        gated_type_names = tuple(
            memory_type.name
            for memory_type in memory_types
            if memory_type.name == "episodic"
        )
        sql = f"""
            SELECT e.*,
                   (
                     mt.w_recency *
                       CASE
                         WHEN mt.half_life_seconds IS NULL THEN 1.0
                         ELSE power(
                           0.5,
                           GREATEST(
                             EXTRACT(EPOCH FROM (%s::timestamptz - e.created_at)),
                             0
                           ) / mt.half_life_seconds
                         )
                       END
                     + mt.w_similarity * (1 - (e.embedding <=> %s::vector))
                     + mt.w_stability * LEAST(e.stability, 10) / 10.0
                     + mt.w_score * e.score
                   ) AS relevance
            FROM engrams e
            JOIN memory_types mt ON mt.name = e.type_name
            WHERE e.status = 'active'
              AND ({" OR ".join(scope_clauses)})
              AND (
                  %s::text IS NULL
                  OR e.domain_tag IS NULL
                  OR e.domain_tag = %s
              )
              AND (
                  %s::float IS NULL
                  OR e.type_name <> ALL(%s::text[])
                  OR (1 - (e.embedding <=> %s::vector)) >= %s
              )
              AND (%s::uuid IS NULL OR %s = ANY(e.entity_refs))
            ORDER BY relevance DESC, e.created_at DESC
            LIMIT %s
        """
        full_parameters = [
            now,
            _vector_literal(query_embedding),
            *parameters,
            query.domain_tag,
            query.domain_tag,
            query.min_similarity,
            list(gated_type_names),
            _vector_literal(query_embedding),
            query.min_similarity,
            query.entity_ref,
            query.entity_ref,
            query.top_k,
        ]
        with self._connect() as connection:
            rows = connection.execute(sql, full_parameters).fetchall()
        return [
            RecallItem(
                type_name=row["type_name"],
                relevance=float(row["relevance"]),
                engram=_engram_from_row(row),
            )
            for row in rows
        ]

    def _recall_always(
        self,
        memory_types: tuple[MemoryType, ...],
        query: RecallQuery,
    ) -> list[RecallItem]:
        """Recupera tipos `ALWAYS_INJECT` (identity/principles/safety).

        D2 (PLAN.md) NO toca este filtro a proposito: los delegados ya se
        inyectan de forma incondicional porque quien los recupera
        (`MemoryEnricher.recall`, DELEGATED_TYPES) nunca pasa `domain_tag` en
        la query, con o sin `--domain` en la peticion. La forma estricta
        `e.domain_tag = %s` se conserva sin efecto observable hoy; si algun
        dia un llamador pasara `domain_tag` para un tipo delegado, revisar si
        la semantica neutra de D2 debe extenderse aqui tambien.
        """
        clauses: list[str] = []
        parameters: list[Any] = []
        for memory_type in memory_types:
            namespace = query.namespace
            if namespace is None and len(memory_type.namespaces) == 1:
                namespace = memory_type.namespaces[0]
            key = derive_memory_key(
                memory_type,
                query.identity,
                namespace,
                query.entity_id,
            )
            clause, values = _scope_clause(memory_type, key)
            clauses.append(f"(e.type_name = %s AND {clause})")
            parameters.append(memory_type.name)
            parameters.extend(values)
        sql = f"""
            SELECT e.*
            FROM engrams e
            WHERE e.status = 'active'
              AND ({" OR ".join(clauses)})
              AND (%s::text IS NULL OR e.domain_tag = %s)
              AND (%s::uuid IS NULL OR %s = ANY(e.entity_refs))
            ORDER BY e.created_at, e.id
        """
        parameters.extend(
            (
                query.domain_tag,
                query.domain_tag,
                query.entity_ref,
                query.entity_ref,
            )
        )
        with self._connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [
            RecallItem(
                type_name=row["type_name"],
                relevance=1.0,
                engram=_engram_from_row(row),
            )
            for row in rows
        ]

    def _recall_profiles(
        self,
        memory_types: tuple[MemoryType, ...],
        query: RecallQuery,
    ) -> list[RecallItem]:
        if query.entity_id is None:
            raise ScopeViolationError(
                "profile_lookup exige entity_id en la consulta"
            )
        for memory_type in memory_types:
            derive_memory_key(
                memory_type,
                query.identity,
                memory_type.namespaces[0],
                query.entity_id,
            )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM entities
                WHERE id = %s AND status = 'active'
                """,
                (query.entity_id,),
            ).fetchone()
        if row is None:
            return []
        return [
            RecallItem(
                type_name=memory_types[0].name,
                relevance=1.0,
                entity=_entity_from_row(row),
            )
        ]

    def _get_type(self, name: str) -> MemoryType:
        registry = MemoryTypeRegistry(self.list_types())
        return registry.get(name)

    def _connect(self):
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def _require_embedder(self) -> Embedder:
        if self._embedder is None:
            raise InvalidConsolidationEventError(
                "esta operacion exige un embedder configurado"
            )
        return self._embedder


def _default_migration_path() -> Path:
    return (
        Path(__file__).resolve().parents[3]
        / "db"
        / "migrations"
        / "0001_memory_registry.sql"
    )


def _require_authority(
    memory_type: MemoryType,
    principal: Principal,
) -> None:
    if principal is not memory_type.writer_principal:
        raise WriteAuthorityError(
            f"{principal.value!r} no puede escribir {memory_type.name!r}"
        )


def _validate_consolidation_event(event: ConsolidationEvent) -> None:
    if not event.source_ids:
        raise InvalidConsolidationEventError(
            "source_ids no puede estar vacio"
        )
    if len(set(event.source_ids)) != len(event.source_ids):
        raise InvalidConsolidationEventError(
            "source_ids no admite duplicados"
        )
    if not str(event.trigger).strip():
        raise InvalidConsolidationEventError("trigger no puede estar vacio")
    if not event.reason.strip():
        raise InvalidConsolidationEventError("reason no puede estar vacio")
    has_target = event.target_type is not None
    has_content = event.content is not None
    if has_target != has_content:
        raise InvalidConsolidationEventError(
            "target_type y content deben aparecer juntos"
        )
    if event.target_namespace is not None and not has_target:
        raise InvalidConsolidationEventError(
            "target_namespace exige target_type"
        )


def _scope_clause(memory_type: MemoryType, key) -> tuple[str, list[Any]]:
    if memory_type.scope is Scope.SESSION:
        return (
            "e.user_id = %s AND e.session_id = %s AND e.namespace IS NULL",
            [key.user_id, key.session_id],
        )
    if memory_type.scope is Scope.USER:
        return (
            "e.user_id = %s AND e.session_id IS NULL AND e.namespace = %s",
            [key.user_id, key.namespace],
        )
    if memory_type.scope is Scope.GLOBAL:
        return (
            "e.user_id IS NULL AND e.session_id IS NULL AND e.namespace = %s",
            [key.namespace],
        )
    raise UnsupportedWriteError(
        "los perfiles entity se recuperan mediante profile_lookup"
    )


def _memory_type_from_row(row: dict[str, Any]) -> MemoryType:
    return MemoryType(
        name=row["name"],
        memory_class=MemoryClass(row["class"]),
        writer_principal=Principal(row["writer_principal"]),
        retrieval_mode=RetrievalMode(row["retrieval_mode"]),
        scope=Scope(row["scope"]),
        namespaces=tuple(row["namespaces"]),
        w_recency=_optional_float(row["w_recency"]),
        w_similarity=_optional_float(row["w_similarity"]),
        w_stability=_optional_float(row["w_stability"]),
        w_score=_optional_float(row["w_score"]),
        half_life_seconds=row["half_life_seconds"],
        status=row["status"],
        version=row["version"],
    )


def _engram_from_row(row: dict[str, Any]) -> Engram:
    return Engram(
        id=row["id"],
        type_name=row["type_name"],
        user_id=row["user_id"],
        session_id=row["session_id"],
        namespace=row["namespace"],
        content=row["content"],
        embedding=_parse_vector(row["embedding"]),
        score=float(row["score"]),
        stability=row["stability"],
        service=row["service"],
        domain_tag=row["domain_tag"],
        entity_refs=tuple(row["entity_refs"]),
        unresolved_mentions=tuple(row["unresolved_mentions"]),
        status=EngramStatus(row["status"]),
        archived_at=row["archived_at"],
        archived_reason=row["archived_reason"],
        source_trace_id=row["source_trace_id"],
        version=row["version"],
        created_at=row["created_at"],
        last_reinforced_at=row["last_reinforced_at"],
    )


def _entity_from_row(row: dict[str, Any]) -> EntityProfile:
    return EntityProfile(
        id=row["id"],
        kind=row["kind"],
        name=row["name"],
        aliases=tuple(row["aliases"]),
        profile=row["profile"],
        status=row["status"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _optional_float(value) -> float | None:
    return None if value is None else float(value)


def _vector_literal(vector: tuple[float, ...]) -> str:
    return "[" + ",".join(format(value, ".17g") for value in vector) + "]"


def _parse_vector(value: Any) -> tuple[float, ...]:
    if isinstance(value, str):
        stripped = value.strip("[]")
        if not stripped:
            return ()
        return tuple(float(item) for item in stripped.split(","))
    return tuple(float(item) for item in value)
