-- `episodic` era residuo estructurado del hilo, no memoria durable.
-- Los engramas historicos no tienen session_id y no se pueden reescalar sin
-- inventar procedencia. Se archivan, siguen direccionables por id y el tipo
-- queda retirado para conservar su FK.

UPDATE engrams
SET status = 'archived',
    archived_at = now(),
    archived_reason = 'episodic_without_session_retired',
    version = version + 1
WHERE type_name = 'episodic'
  AND status = 'active';

UPDATE memory_types
SET status = 'retired',
    version = version + 1
WHERE name = 'episodic'
  AND status <> 'retired';

-- El nuevo nombre conserva contenido, namespaces, ranking y procedencia, pero
-- su clave incluye la sesion. El upsert solo converge la declaracion propia y
-- hace la migracion idempotente en instalaciones ya actualizadas.
INSERT INTO memory_types (
    name, "class", writer_principal, retrieval_mode, scope, namespaces,
    w_recency, w_similarity, w_stability, w_score, half_life_seconds,
    status, version
)
VALUES (
    'thread_artifacts', 'strict', 'extended', 'ranked', 'session',
    ARRAY['facts', 'tasks', 'preferences'],
    0.5, 0.35, 0.05, 0.10, 2592000,
    'active', 1
)
ON CONFLICT (name) DO UPDATE SET
    "class" = EXCLUDED."class",
    writer_principal = EXCLUDED.writer_principal,
    retrieval_mode = EXCLUDED.retrieval_mode,
    scope = EXCLUDED.scope,
    namespaces = EXCLUDED.namespaces,
    w_recency = EXCLUDED.w_recency,
    w_similarity = EXCLUDED.w_similarity,
    w_stability = EXCLUDED.w_stability,
    w_score = EXCLUDED.w_score,
    half_life_seconds = EXCLUDED.half_life_seconds,
    status = EXCLUDED.status;

-- `semantic` sigue declarado y recuperable, pero su escritura pertenece a
-- conscience. Extended ya no lo puebla por promocion.
UPDATE memory_types
SET "class" = 'delegated',
    writer_principal = 'conscience',
    version = GREATEST(version, 2)
WHERE name = 'semantic'
  AND (
      "class" <> 'delegated'
      OR writer_principal <> 'conscience'
      OR version < 2
  );

-- Una sesion ya archivada se lleva cualquier artefacto que hubiera quedado
-- activo. La guarda por estado permite reaplicar la migracion sin mutar otra
-- vez las filas.
UPDATE engrams e
SET status = 'archived',
    archived_at = s.archived_at,
    archived_reason = 'session_inactivity_elapsed',
    version = e.version + 1
FROM sessions s
WHERE s.user_id = e.user_id
  AND s.session_id = e.session_id
  AND s.status IN ('archivada', 'cerrada')
  AND e.type_name = 'thread_artifacts'
  AND e.status = 'active';
