#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=app_password="$APP_PASSWORD" <<'SQL'
CREATE ROLE midas_app LOGIN PASSWORD :'app_password';
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE TABLE assets (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ticker text NOT NULL UNIQUE,
    name text NOT NULL,
    category text NOT NULL CHECK (category IN ('stock', 'fii', 'fiagro')),
    sector text NOT NULL,
    is_demo boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE daily_prices (
    asset_id bigint NOT NULL REFERENCES assets(id),
    price_date date NOT NULL,
    close numeric(20,8) NOT NULL CHECK (close > 0),
    adjusted_close numeric(20,8) CHECK (adjusted_close > 0),
    volume numeric(24,4) CHECK (volume >= 0),
    source text NOT NULL,
    ingested_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (asset_id, price_date, source)
);
CREATE TABLE watchlists (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE watchlist_assets (
    watchlist_id bigint REFERENCES watchlists(id) ON DELETE CASCADE,
    asset_id bigint REFERENCES assets(id),
    PRIMARY KEY (watchlist_id, asset_id)
);
CREATE TABLE model_runs (
    id uuid PRIMARY KEY,
    dataset_id text NOT NULL,
    algorithm text NOT NULL,
    horizon_months integer NOT NULL CHECK (horizon_months IN (12,24,36)),
    metrics jsonb NOT NULL DEFAULT '{}',
    parameters jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN model_runs.dataset_id IS 'ID lógico do snapshot em midas_training.datasets; referência entre bancos validada pela aplicação.';
GRANT CONNECT ON DATABASE midas TO midas_app;
GRANT USAGE ON SCHEMA public TO midas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO midas_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO midas_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO midas_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO midas_app;
SQL
