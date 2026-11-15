-- One profile per user: the answers from onboarding.
-- Everything is stored in metric; the app converts for display (unit_system).
CREATE TABLE profiles (
    user_id             uuid PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    birth_year          integer NOT NULL,
    sex                 text NOT NULL CHECK (sex IN ('male', 'female')),
    height_cm           double precision NOT NULL CHECK (height_cm BETWEEN 120 AND 230),
    weight_kg           double precision NOT NULL CHECK (weight_kg BETWEEN 30 AND 300),
    experience          text NOT NULL
                        CHECK (experience IN ('beginner', 'intermediate', 'advanced')),
    goal                text NOT NULL
                        CHECK (goal IN ('fat_loss', 'muscle_gain', 'recomposition', 'strength')),
    target_weight_kg    double precision CHECK (target_weight_kg BETWEEN 30 AND 300),
    target_body_fat_pct double precision CHECK (target_body_fat_pct BETWEEN 3 AND 50),
    -- 0 = Monday ... 6 = Sunday. At most 6: at least one full rest day per week.
    training_days       smallint[] NOT NULL
                        CHECK (cardinality(training_days) BETWEEN 1 AND 6),
    session_minutes     smallint NOT NULL CHECK (session_minutes BETWEEN 20 AND 180),
    injury_areas        text[] NOT NULL DEFAULT '{}',
    injury_notes        text NOT NULL DEFAULT '' CHECK (char_length(injury_notes) <= 500),
    unit_system         text NOT NULL DEFAULT 'metric'
                        CHECK (unit_system IN ('metric', 'imperial')),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);
