-- Procedencia del engrama y lineage de supersede (ADR 0013).
--
-- Los engramas anteriores a esta migracion quedan en 'unknown': no se les
-- inventa procedencia. Mismo criterio que `source_trace_id` en CR-0005, un
-- hueco visible es mejor que un valor plausible y falso.

ALTER TABLE engrams
    ADD COLUMN IF NOT EXISTS stated_by text NOT NULL DEFAULT 'unknown';

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'engrams'::regclass
          AND conname = 'engrams_stated_by_check'
    ) THEN
        ALTER TABLE engrams
            ADD CONSTRAINT engrams_stated_by_check
            CHECK (stated_by IN ('user', 'model', 'unknown'));
    END IF;
END
$migration$;

-- El supersede por correccion busca candidatos del modelo dentro del scope de
-- usuario y namespace; el indice sirve a esa consulta.
CREATE INDEX IF NOT EXISTS engrams_stated_by_idx
    ON engrams (type_name, user_id, namespace, stated_by)
    WHERE status = 'active';

-- `superseded_by`: lineage de la correccion, hermano de `consolidated_from`.
DO $migration$
BEGIN
    ALTER TABLE memory_links
        DROP CONSTRAINT IF EXISTS memory_links_link_kind_check;
    ALTER TABLE memory_links
        ADD CONSTRAINT memory_links_link_kind_check
        CHECK (link_kind IN ('evidence', 'consolidated_from', 'superseded_by'));
END
$migration$;
