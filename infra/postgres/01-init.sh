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
    horizon_months integer NOT NULL CHECK (horizon_months IN (6,12,24,36)),
    metrics jsonb NOT NULL DEFAULT '{}',
    parameters jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE portfolios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE portfolio_assets (
    portfolio_id bigint NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id bigint NOT NULL REFERENCES assets(id),
    quantity numeric(20,8) NOT NULL CHECK (quantity > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (portfolio_id, asset_id)
);
CREATE TABLE portfolio_operations (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    portfolio_id bigint NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id bigint REFERENCES assets(id),
    operation_type text NOT NULL CHECK (operation_type IN (
        'buy', 'sell', 'deposit', 'withdrawal', 'dividend', 'jcp', 'fee', 'tax'
    )),
    occurred_on date NOT NULL,
    quantity numeric(20,8) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    unit_price numeric(20,8) NOT NULL DEFAULT 0 CHECK (unit_price >= 0),
    amount numeric(20,8) NOT NULL DEFAULT 0 CHECK (amount >= 0),
    fees numeric(20,8) NOT NULL DEFAULT 0 CHECK (fees >= 0),
    taxes numeric(20,8) NOT NULL DEFAULT 0 CHECK (taxes >= 0),
    currency char(3) NOT NULL DEFAULT 'BRL' CHECK (currency ~ '^[A-Z]{3}$'),
    notes text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT trade_requires_asset_and_quantity CHECK (
        (operation_type IN ('buy', 'sell') AND asset_id IS NOT NULL AND quantity > 0)
        OR (operation_type NOT IN ('buy', 'sell'))
    ),
    CONSTRAINT cashflow_requires_amount CHECK (
        (operation_type IN ('deposit', 'withdrawal', 'dividend', 'jcp', 'fee', 'tax') AND amount > 0)
        OR (operation_type IN ('buy', 'sell'))
    ),
    CONSTRAINT income_requires_asset CHECK (
        (operation_type IN ('dividend', 'jcp', 'fee', 'tax') AND asset_id IS NOT NULL)
        OR (operation_type NOT IN ('dividend', 'jcp', 'fee', 'tax'))
    )
);
CREATE INDEX idx_portfolio_operations_portfolio
    ON portfolio_operations (portfolio_id, occurred_on, id);
CREATE INDEX idx_portfolio_operations_asset
    ON portfolio_operations (asset_id, occurred_on, id);
COMMENT ON COLUMN model_runs.dataset_id IS 'ID lógico do snapshot em midas_training.datasets; referência entre bancos validada pela aplicação.';
GRANT CONNECT ON DATABASE midas TO midas_app;
GRANT USAGE ON SCHEMA public TO midas_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO midas_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO midas_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO midas_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO midas_app;
SQL
