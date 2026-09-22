-- La sesion pasa de etiqueta en engrams a entidad con ciclo de vida propio
-- (ADR 0015). La clave incluye al usuario: el mismo texto de session_id no
-- mezcla interlocutores.

CREATE TABLE IF NOT EXISTS sessions (
    user_id text NOT NULL,
    session_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_activity_at timestamptz NOT NULL DEFAULT now(),
    status text NOT NULL DEFAULT 'activa'
        CHECK (status IN ('activa', 'archivada', 'cerrada')),
    archived_at timestamptz,
    closed_at timestamptz,
    PRIMARY KEY (user_id, session_id),
    CHECK (last_activity_at >= created_at),
    CHECK (
        (status = 'activa' AND archived_at IS NULL AND closed_at IS NULL)
        OR
        (status = 'archivada' AND archived_at IS NOT NULL AND closed_at IS NULL)
        OR
        (status = 'cerrada' AND archived_at IS NOT NULL AND closed_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS sessions_status_activity_idx
    ON sessions (status, last_activity_at);

-- Backfill obligatorio: una fila por cada clave de sesion ya mencionada. El
-- reloj conserva las 4 h vigentes. archived_at registra el instante en que la
-- sesion cruzo el umbral, que se puede reconstruir exactamente desde su ultima
-- actividad; el estado nunca se deduce despues de que el campo sea nulo.
INSERT INTO sessions (
    user_id,
    session_id,
    created_at,
    last_activity_at,
    status,
    archived_at,
    closed_at
)
SELECT
    user_id,
    session_id,
    min(created_at),
    max(created_at),
    CASE
        WHEN max(created_at) < now() - (14400 * interval '1 second')
            THEN 'archivada'
        ELSE 'activa'
    END,
    CASE
        WHEN max(created_at) < now() - (14400 * interval '1 second')
            THEN max(created_at) + (14400 * interval '1 second')
        ELSE NULL
    END,
    NULL
FROM engrams
WHERE user_id IS NOT NULL
  AND session_id IS NOT NULL
GROUP BY user_id, session_id
ON CONFLICT (user_id, session_id) DO NOTHING;

-- Una sesion que nace ya archivada por el backfill se lleva tambien sus
-- engramas de hilo. El filtro por estado hace esta reparacion idempotente.
UPDATE engrams e
SET status = 'archived',
    archived_at = s.archived_at,
    archived_reason = 'session_inactivity_elapsed',
    version = e.version + 1
FROM sessions s
WHERE s.user_id = e.user_id
  AND s.session_id = e.session_id
  AND s.status IN ('archivada', 'cerrada')
  AND e.type_name IN ('dialog', 'thread_summary')
  AND e.status = 'active';

-- El backfill precede a la FK para que un despliegue existente no deje
-- engramas huerfanos. La guarda hace que la migracion pueda reaplicarse incluso
-- despues de migraciones posteriores, como exige docs/DESPLIEGUE.md.
DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'engrams'::regclass
          AND conname = 'engrams_session_fk'
    ) THEN
        ALTER TABLE engrams
            ADD CONSTRAINT engrams_session_fk
            FOREIGN KEY (user_id, session_id)
            REFERENCES sessions (user_id, session_id);
    END IF;
END
$migration$;
