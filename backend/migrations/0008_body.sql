-- Daily weigh-ins: one per day (logging again the same day replaces it, so retries
-- are naturally harmless).
CREATE TABLE body_weights (
    user_id    uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    day        date NOT NULL,
    weight_kg  double precision NOT NULL CHECK (weight_kg BETWEEN 30 AND 300),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, day)
);

-- Tape measurements (cm) and/or a body fat reading from a scale or DEXA scan.
-- The Navy estimate is computed from neck/waist(/hips), not stored.
CREATE TABLE body_measurements (
    user_id       uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    day           date NOT NULL,
    neck_cm       double precision CHECK (neck_cm BETWEEN 10 AND 100),
    waist_cm      double precision CHECK (waist_cm BETWEEN 30 AND 250),
    hips_cm       double precision CHECK (hips_cm BETWEEN 30 AND 250),
    chest_cm      double precision CHECK (chest_cm BETWEEN 30 AND 250),
    arm_cm        double precision CHECK (arm_cm BETWEEN 10 AND 100),
    thigh_cm      double precision CHECK (thigh_cm BETWEEN 20 AND 150),
    body_fat_pct  double precision CHECK (body_fat_pct BETWEEN 3 AND 60),
    body_fat_source text CHECK (body_fat_source IN ('scale', 'dexa', 'other')),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, day)
);
