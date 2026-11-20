-- Registro de entidades versionado (extended ADR 0016).

ALTER TABLE entities
    ADD COLUMN IF NOT EXISTS observed jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS curated jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS retired_at timestamptz;

-- `profile` queda como proyeccion de compatibilidad de `curated`. El backfill
-- conserva los perfiles delegados que ya existian.
UPDATE entities
SET curated = profile
WHERE curated = '{}'::jsonb AND profile <> '{}'::jsonb;

DO $migration$
DECLARE
    definition text;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO definition
    FROM pg_constraint
    WHERE conrelid = 'entities'::regclass
      AND conname = 'entities_status_check';
    IF definition IS NULL THEN
        ALTER TABLE entities
            ADD CONSTRAINT entities_status_check
            CHECK (status IN ('active', 'retired'));
    ELSIF position('retired' in definition) = 0 THEN
        ALTER TABLE entities DROP CONSTRAINT entities_status_check;
        ALTER TABLE entities
            ADD CONSTRAINT entities_status_check
            CHECK (status IN ('active', 'retired'));
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS entity_keys (
    namespace text NOT NULL,
    external_id text NOT NULL,
    entity_id uuid NOT NULL REFERENCES entities(id),
    added_at timestamptz NOT NULL DEFAULT now(),
    retired_at timestamptz,
    CHECK (namespace <> '' AND external_id <> '')
);

CREATE UNIQUE INDEX IF NOT EXISTS entity_keys_current_unique_idx
    ON entity_keys (namespace, external_id)
    WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS entity_keys_entity_idx
    ON entity_keys (entity_id, retired_at);

CREATE TABLE IF NOT EXISTS entity_versions (
    entity_id uuid NOT NULL REFERENCES entities(id),
    version integer NOT NULL CHECK (version > 0),
    kind text NOT NULL,
    name text NOT NULL,
    aliases text[] NOT NULL DEFAULT '{}',
    observed jsonb NOT NULL,
    curated jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('active', 'retired')),
    author text NOT NULL CHECK (author IN ('extended', 'operator', 'conscience')),
    origin text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, version),
    CHECK (
        origin = 'cli'
        OR origin ~ '^refresh:.+$'
        OR origin ~ '^seed:[0-9a-f]{64}$'
    )
);

-- Una unica siembra declarativa gobierna sus hechos y recuerda si creo la
-- entidad. La tabla puede mutar; el historico de negocio sigue siendo
-- exclusivamente `entity_versions`.
CREATE TABLE IF NOT EXISTS entity_seed_ownership (
    entity_id uuid PRIMARY KEY REFERENCES entities(id),
    owns_entity boolean NOT NULL,
    curated_keys text[] NOT NULL DEFAULT '{}'
);

DO $migration$
DECLARE
    origin_definition text;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO origin_definition
    FROM pg_constraint
    WHERE conrelid = 'entity_versions'::regclass
      AND conname = 'entity_versions_origin_check';
    IF origin_definition IS NULL THEN
        ALTER TABLE entity_versions
            ADD CONSTRAINT entity_versions_origin_check CHECK (
                origin = 'cli'
                OR origin ~ '^refresh:.+$'
                OR origin ~ '^seed:[0-9a-f]{64}$'
            );
    ELSIF position('refresh:.+' in origin_definition) = 0 THEN
        ALTER TABLE entity_versions
            DROP CONSTRAINT entity_versions_origin_check;
        ALTER TABLE entity_versions
            ADD CONSTRAINT entity_versions_origin_check CHECK (
                origin = 'cli'
                OR origin ~ '^refresh:.+$'
                OR origin ~ '^seed:[0-9a-f]{64}$'
            );
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'entities'::regclass
          AND conname = 'entities_retired_at_check'
    ) THEN
        ALTER TABLE entities
            ADD CONSTRAINT entities_retired_at_check CHECK (
                (status = 'active' AND retired_at IS NULL)
                OR (status = 'retired' AND retired_at IS NOT NULL)
            );
    END IF;
END
$migration$;

REVOKE UPDATE, DELETE, TRUNCATE ON entity_versions FROM PUBLIC;

-- Incluso el propietario de la tabla (el usuario unico de instalaciones de
-- desarrollo) queda sujeto a la inmutabilidad. INSERT sigue siendo el unico
-- camino normal del historico.
CREATE OR REPLACE FUNCTION reject_entity_version_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'entity_versions is append-only'
        USING ERRCODE = '42501';
END
$function$;

DROP TRIGGER IF EXISTS entity_versions_append_only ON entity_versions;
CREATE TRIGGER entity_versions_append_only
BEFORE UPDATE OR DELETE ON entity_versions
FOR EACH STATEMENT EXECUTE FUNCTION reject_entity_version_mutation();
