-- Procedencia del engrama y lineage de contradiccion (ADR 0013).
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

-- La anotacion de contradiccion busca candidatos del modelo por tipo y usuario;
-- el prefijo del indice sirve a esa consulta. Namespace no es un filtro.
CREATE INDEX IF NOT EXISTS engrams_stated_by_idx
    ON engrams (type_name, user_id, namespace, stated_by)
    WHERE status = 'active';

-- `contradicted_by`: el usuario dijo algo muy proximo a lo que este engrama
-- afirma. No retira nada; el recall lo lee para desprioriar y etiquetar.
-- Se ANADE el valor solo si el CHECK vigente no lo admite ya. Las migraciones
-- se reaplican TODAS en cada arranque, asi que una que estreche lo que otra
-- posterior ensancho rompe el despliegue: medido el 2026-09-21, reejecutar el
-- instalador fallaba con CheckViolation en cuanto existia un enlace de la 0005.
DO $migration$
DECLARE
    definicion text;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO definicion
    FROM pg_constraint
    WHERE conrelid = 'memory_links'::regclass
      AND conname = 'memory_links_link_kind_check';

    IF definicion IS NULL THEN
        ALTER TABLE memory_links
            ADD CONSTRAINT memory_links_link_kind_check
            CHECK (link_kind IN ('evidence', 'consolidated_from', 'contradicted_by'));
    ELSIF position('contradicted_by' in definicion) = 0 THEN
        ALTER TABLE memory_links
            DROP CONSTRAINT memory_links_link_kind_check;
        ALTER TABLE memory_links
            ADD CONSTRAINT memory_links_link_kind_check
            CHECK (link_kind IN ('evidence', 'consolidated_from', 'contradicted_by'));
    END IF;
END
$migration$;

-- Un mismo par (contradicho, contradictor) se anota una sola vez: el
-- ON CONFLICT del write-back necesita el indice para apoyarse.
CREATE UNIQUE INDEX IF NOT EXISTS memory_links_unique_kind_idx
    ON memory_links (source_id, target_engram_id, link_kind);

-- El recall pregunta por los enlaces entrantes de cada engrama recuperado.
CREATE INDEX IF NOT EXISTS memory_links_source_kind_idx
    ON memory_links (source_id, link_kind);
