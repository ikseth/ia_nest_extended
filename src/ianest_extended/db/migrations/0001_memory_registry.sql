CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS memory_types (
    name text PRIMARY KEY,
    "class" text NOT NULL CHECK ("class" IN ('strict', 'delegated')),
    writer_principal text NOT NULL
        CHECK (writer_principal IN ('extended', 'conscience')),
    retrieval_mode text NOT NULL
        CHECK (retrieval_mode IN ('ranked', 'always_inject', 'profile_lookup')),
    scope text NOT NULL CHECK (scope IN ('session', 'user', 'entity', 'global')),
    namespaces text[] NOT NULL DEFAULT '{}',
    w_recency numeric,
    w_similarity numeric,
    w_stability numeric,
    w_score numeric,
    half_life_seconds bigint CHECK (
        half_life_seconds IS NULL OR half_life_seconds > 0
    ),
    status text NOT NULL DEFAULT 'active',
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    CHECK (
        (retrieval_mode = 'ranked'
         AND w_recency IS NOT NULL
         AND w_similarity IS NOT NULL
         AND w_stability IS NOT NULL
         AND w_score IS NOT NULL)
        OR
        (retrieval_mode <> 'ranked'
         AND w_recency IS NULL
         AND w_similarity IS NULL
         AND w_stability IS NULL
         AND w_score IS NULL)
    ),
    CHECK (
        ("class" = 'strict' AND writer_principal = 'extended')
        OR
        ("class" = 'delegated' AND writer_principal = 'conscience')
    )
);

CREATE TABLE IF NOT EXISTS engrams (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name text NOT NULL REFERENCES memory_types(name),
    user_id text,
    session_id text,
    namespace text,
    content text NOT NULL,
    embedding vector({{embedding_dimension}}) NOT NULL,
    score numeric NOT NULL DEFAULT 0 CHECK (score >= 0 AND score <= 1),
    stability integer NOT NULL DEFAULT 0 CHECK (stability >= 0),
    service text,
    domain_tag text,
    entity_refs uuid[] NOT NULL DEFAULT '{}',
    unresolved_mentions text[] NOT NULL DEFAULT '{}',
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'superseded')),
    archived_at timestamptz,
    archived_reason text,
    source_trace_id text,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    last_reinforced_at timestamptz,
    CHECK (
        (type_name = 'dialog' AND namespace IS NULL)
        OR (type_name <> 'dialog' AND namespace IS NOT NULL)
    ),
    CHECK (
        (status = 'active' AND archived_at IS NULL AND archived_reason IS NULL)
        OR status IN ('archived', 'superseded')
    )
);

CREATE INDEX IF NOT EXISTS engrams_type_scope_idx
    ON engrams (type_name, user_id, session_id, namespace, status);
CREATE INDEX IF NOT EXISTS engrams_domain_idx
    ON engrams (domain_tag) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS engrams_entity_refs_idx
    ON engrams USING gin (entity_refs);

CREATE TABLE IF NOT EXISTS entities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    kind text NOT NULL,
    name text NOT NULL,
    aliases text[] NOT NULL DEFAULT '{}',
    profile jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'active',
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source_kind text NOT NULL,
    source_id uuid NOT NULL,
    target_engram_id uuid NOT NULL REFERENCES engrams(id),
    link_kind text NOT NULL
        CHECK (link_kind IN ('evidence', 'consolidated_from')),
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS memory_links_target_idx
    ON memory_links (target_engram_id);
