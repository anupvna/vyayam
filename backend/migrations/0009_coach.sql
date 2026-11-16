-- Coach conversations. Kept so the chat survives reloads and the coach remembers the
-- last few turns. The user can clear it any time (DELETE /api/coach/messages).
CREATE TABLE coach_messages (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role       text NOT NULL CHECK (role IN ('user', 'coach')),
    content    text NOT NULL CHECK (length(content) BETWEEN 1 AND 4000),
    -- Checked proposals: [{type, session_key, minutes, exercise_id, label, applied}]
    actions    jsonb NOT NULL DEFAULT '[]',
    -- Who answered: groq | gemini | engine | safety (null for the user's own messages)
    source     text CHECK (source IN ('groq', 'gemini', 'engine', 'safety')),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX coach_messages_user_time ON coach_messages (user_id, created_at DESC);
