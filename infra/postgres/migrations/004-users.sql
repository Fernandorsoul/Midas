BEGIN;
CREATE TABLE IF NOT EXISTS users (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email text NOT NULL UNIQUE,
    password_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS user_sessions (
    token_hash text PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions (user_id);
ALTER TABLE portfolios ADD COLUMN IF NOT EXISTS user_id bigint REFERENCES users(id);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id bigint REFERENCES users(id);
ALTER TABLE watchlists ADD COLUMN IF NOT EXISTS user_id bigint REFERENCES users(id);
CREATE INDEX IF NOT EXISTS idx_portfolios_user ON portfolios (user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON users, user_sessions TO midas_app;
GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO midas_app;
COMMIT;
