-- Login sessions. The browser holds a random token in an HttpOnly cookie; we store
-- only its SHA-256 hash, so a database leak does not hand out live sessions.
-- Each session also has its own CSRF token (sent back in a header on writes).
CREATE TABLE sessions (
    token_hash text PRIMARY KEY,
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    csrf_token text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);

CREATE INDEX sessions_user_id_idx ON sessions (user_id);
