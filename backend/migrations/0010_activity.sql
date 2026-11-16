-- Cardio and floor work.

-- How much cardio to aim for: none | light | regular | lots. NULL = decided by the goal.
ALTER TABLE profiles
    ADD COLUMN cardio_level text CHECK (cardio_level IN ('none', 'light', 'regular', 'lots'));

-- Anything that isn't a lifting set: treadmill, bike, a walk, jump rope, a mat workout...
-- The id is made on the phone (like set logs), so a resend after a lost reply, or an
-- offline sync, never creates a duplicate.
CREATE TABLE activity_logs (
    id          uuid PRIMARY KEY,
    user_id     uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    day         date NOT NULL,
    activity    text NOT NULL,
    part        text NOT NULL DEFAULT 'main' CHECK (part IN ('warmup', 'main', 'finisher', 'cooldown')),
    minutes     numeric(5, 1) NOT NULL CHECK (minutes > 0 AND minutes <= 600),
    intensity   text NOT NULL DEFAULT 'moderate' CHECK (intensity IN ('easy', 'moderate', 'hard')),
    speed_kmh   numeric(4, 1) CHECK (speed_kmh > 0 AND speed_kmh <= 40),
    incline_pct numeric(3, 1) CHECK (incline_pct >= 0 AND incline_pct <= 40),
    level       smallint CHECK (level BETWEEN 1 AND 40),
    distance_km numeric(6, 2) CHECK (distance_km > 0 AND distance_km <= 500),
    calories    integer CHECK (calories > 0 AND calories <= 5000), -- from the machine, if entered
    items       text[] NOT NULL DEFAULT '{}', -- floor moves done (mat workout, HIIT)
    note        text NOT NULL DEFAULT '' CHECK (length(note) <= 200),
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX activity_logs_user_day ON activity_logs (user_id, day);

-- Where you train on a given day, when it isn't your active gym: one of your other gyms,
-- or at home with just a mat. The plan swaps each exercise for one that works there.
CREATE TABLE day_places (
    user_id  uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    day      date NOT NULL,
    gym_id   uuid REFERENCES gyms (id) ON DELETE CASCADE,
    mat_only boolean NOT NULL DEFAULT false,
    PRIMARY KEY (user_id, day),
    CONSTRAINT one_place CHECK (mat_only <> (gym_id IS NOT NULL))
);
