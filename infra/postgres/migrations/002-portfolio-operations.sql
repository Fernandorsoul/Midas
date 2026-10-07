BEGIN;
CREATE TABLE IF NOT EXISTS portfolio_operations (
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
CREATE INDEX IF NOT EXISTS idx_portfolio_operations_portfolio
    ON portfolio_operations (portfolio_id, occurred_on, id);
CREATE INDEX IF NOT EXISTS idx_portfolio_operations_asset
    ON portfolio_operations (asset_id, occurred_on, id);
GRANT SELECT, INSERT, UPDATE, DELETE ON portfolio_operations TO midas_app;
GRANT USAGE, SELECT ON SEQUENCE portfolio_operations_id_seq TO midas_app;
COMMIT;
