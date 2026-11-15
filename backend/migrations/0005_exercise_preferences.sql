-- Favorite and hidden exercises, per user. Exercises themselves live in code
-- (app/data/exercises.json); the API checks exercise_id against that library.
-- No row means "no preference".
CREATE TABLE exercise_preferences (
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    exercise_id text NOT NULL,
    preference  text NOT NULL CHECK (preference IN ('favorite', 'hidden')),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, exercise_id)
);
