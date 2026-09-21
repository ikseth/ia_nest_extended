-- Anclaje auditable de la sintesis de hilo (Fase 9).
-- La sintesis es el source y cada engrama resumido es un target.
--
-- Solo ensancha el CHECK si `summarizes` no esta ya admitido. Misma regla que
-- la 0004: las migraciones se reaplican todas en cada arranque, y una que
-- estreche lo que otra posterior ensancho rompe el despliegue.

DO $migration$
DECLARE
    definicion text;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO definicion
    FROM pg_constraint
    WHERE conrelid = 'memory_links'::regclass
      AND conname = 'memory_links_link_kind_check';

    IF definicion IS NULL OR position('summarizes' in definicion) = 0 THEN
        ALTER TABLE memory_links
            DROP CONSTRAINT IF EXISTS memory_links_link_kind_check;
        ALTER TABLE memory_links
            ADD CONSTRAINT memory_links_link_kind_check
            CHECK (
                link_kind IN (
                    'evidence',
                    'consolidated_from',
                    'contradicted_by',
                    'summarizes'
                )
            );
    END IF;
END
$migration$;
