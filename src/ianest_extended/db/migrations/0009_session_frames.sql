-- Marco versionado de la conversacion (extended ADR 0017).

ALTER TABLE sessions
    ADD COLUMN IF NOT EXISTS awaiting_part text;

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'sessions'::regclass
          AND conname = 'sessions_awaiting_part_check'
    ) THEN
        ALTER TABLE sessions
            ADD CONSTRAINT sessions_awaiting_part_check
            CHECK (awaiting_part IS NULL OR awaiting_part IN ('person', 'device', 'place'));
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS session_frames (
    user_id text NOT NULL,
    session_id text NOT NULL,
    seq integer NOT NULL CHECK (seq >= 0),
    account jsonb NOT NULL CHECK (jsonb_typeof(account) = 'object'),
    person jsonb NOT NULL CHECK (jsonb_typeof(person) = 'object'),
    device jsonb NOT NULL CHECK (jsonb_typeof(device) = 'object'),
    place jsonb NOT NULL CHECK (jsonb_typeof(place) = 'object'),
    missing jsonb NOT NULL CHECK (jsonb_typeof(missing) = 'array'),
    cause text NOT NULL CHECK (cause IN ('open', 'edge', 'dialog')),
    changed jsonb NOT NULL CHECK (jsonb_typeof(changed) = 'array'),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, session_id, seq),
    FOREIGN KEY (user_id, session_id)
        REFERENCES sessions (user_id, session_id)
);

CREATE INDEX IF NOT EXISTS session_frames_unresolved_idx
    ON session_frames (created_at);

REVOKE UPDATE, DELETE, TRUNCATE ON session_frames FROM PUBLIC;

CREATE OR REPLACE FUNCTION reject_session_frame_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    RAISE EXCEPTION 'session_frames is append-only'
        USING ERRCODE = '42501';
END
$function$;

DROP TRIGGER IF EXISTS session_frames_append_only ON session_frames;
CREATE TRIGGER session_frames_append_only
BEFORE UPDATE OR DELETE ON session_frames
FOR EACH STATEMENT EXECUTE FUNCTION reject_session_frame_mutation();
