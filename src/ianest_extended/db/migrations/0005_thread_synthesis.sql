-- Anclaje auditable de la sintesis de hilo (Fase 9).
-- La sintesis es el source y cada engrama resumido es un target.

DO $migration$
BEGIN
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
END
$migration$;
