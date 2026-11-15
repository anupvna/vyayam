-- A user can save several gyms (e.g. "NYU gym", "Home"). Exactly one is active;
-- the planner only uses equipment from the active gym.
CREATE TABLE gyms (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name       text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 60),
    equipment  text[] NOT NULL DEFAULT '{}',
    is_active  boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX gyms_user_id_idx ON gyms (user_id);

-- The database itself guarantees "at most one active gym per user".
CREATE UNIQUE INDEX gyms_one_active_per_user ON gyms (user_id) WHERE is_active;
