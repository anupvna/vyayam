-- The split each user trains with. Built-in splits live in code (engine/splits.py);
-- a custom split stores its sessions here as JSON: [{"name": "...", "muscles": [...]}].
CREATE TABLE user_splits (
    user_id         uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    split_id        text NOT NULL,
    custom_sessions jsonb,
    started_on      date NOT NULL, -- Monday of the week the split started (for rotation and deloads)
    updated_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT custom_has_sessions CHECK ((split_id = 'custom') = (custom_sessions IS NOT NULL))
);

-- Changes to single days: skip a day, or swap it to another session. The week's plan
-- is recomputed from the split plus these overrides, so the plan itself is never
-- stored and can't drift out of sync with your profile or gym.
CREATE TABLE day_overrides (
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    day         date NOT NULL,
    action      text NOT NULL CHECK (action IN ('skip', 'swap')),
    session_key text,
    muscles     text[] NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, day)
);
