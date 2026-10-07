BEGIN;
CREATE TABLE IF NOT EXISTS portfolios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS portfolio_assets (
    portfolio_id bigint NOT NULL REFERENCES portfolios(id) ON DELETE CASCADE,
    asset_id bigint NOT NULL REFERENCES assets(id),
    quantity numeric(20,8) NOT NULL CHECK (quantity > 0),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (portfolio_id, asset_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON portfolios, portfolio_assets TO midas_app;
GRANT USAGE, SELECT ON SEQUENCE portfolios_id_seq TO midas_app;
COMMIT;
