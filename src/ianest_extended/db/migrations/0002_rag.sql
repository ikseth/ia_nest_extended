CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS rag_corpora (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    domain text NOT NULL,
    description text NOT NULL DEFAULT '',
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived')),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (name, domain)
);

CREATE TABLE IF NOT EXISTS rag_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    corpus_id uuid NOT NULL REFERENCES rag_corpora(id),
    content text NOT NULL,
    embedding vector({{embedding_dimension}}) NOT NULL,
    source_ref text NOT NULL,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (corpus_id, source_ref, ordinal)
);

CREATE INDEX IF NOT EXISTS rag_corpora_domain_status_idx
    ON rag_corpora (domain, status);
CREATE INDEX IF NOT EXISTS rag_chunks_corpus_idx
    ON rag_chunks (corpus_id);
