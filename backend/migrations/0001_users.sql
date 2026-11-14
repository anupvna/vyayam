-- Accounts. Emails are stored lowercase so "A@x.com" and "a@x.com" are one account.
-- Passwords are never stored, only an argon2 hash (added with auth).
CREATE TABLE users (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email         text NOT NULL,
    password_hash text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_lowercase CHECK (email = lower(email))
);

CREATE UNIQUE INDEX users_email_key ON users (email);
