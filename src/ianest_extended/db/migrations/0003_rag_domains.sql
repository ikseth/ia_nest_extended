CREATE TABLE IF NOT EXISTS rag_corpus_domains (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    corpus_id uuid NOT NULL REFERENCES rag_corpora(id),
    domain text NOT NULL CHECK (btrim(domain) <> ''),
    source text NOT NULL CHECK (source IN ('manual', 'auto')),
    confidence double precision,
    confirmed boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (corpus_id, domain),
    CHECK (
        (source = 'manual' AND confidence IS NULL)
        OR
        (source = 'auto' AND confidence BETWEEN 0.0 AND 1.0)
    )
);

DO $migration$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'rag_corpora'
          AND column_name = 'domain'
    ) THEN
        INSERT INTO rag_corpus_domains (
            id,
            corpus_id,
            domain,
            source,
            confidence,
            confirmed
        )
        SELECT gen_random_uuid(), id, domain, 'manual', NULL, true
        FROM rag_corpora
        ON CONFLICT (corpus_id, domain) DO NOTHING;

        ALTER TABLE rag_corpora DROP COLUMN domain;
    END IF;
END
$migration$;

CREATE INDEX IF NOT EXISTS rag_corpus_domains_confirmed_domain_idx
    ON rag_corpus_domains (domain, corpus_id)
    WHERE confirmed;
