"""Repositórios concretos de PostgreSQL e MongoDB."""
from psycopg.types.json import Jsonb

from midas_core.infrastructure.database import connect_mongo, connect_postgres

class PostgresRepository:
    def __init__(self, connector=connect_postgres):
        self._connector = connector

    def save_stocks(self, stocks, source):
        price_count = 0
        with self._connector() as connection:
            for stock in stocks:
                asset = connection.execute(
                    """INSERT INTO assets(ticker,name,category,sector,is_demo)
                       VALUES (%s,%s,'stock','Não informado',false)
                       ON CONFLICT (ticker) DO UPDATE SET name=EXCLUDED.name, is_demo=false
                       RETURNING id""",
                    (stock.ticker, stock.name),
                ).fetchone()
                for price in stock.prices:
                    connection.execute(
                        """INSERT INTO daily_prices(asset_id,price_date,close,adjusted_close,volume,source)
                           VALUES (%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (asset_id,price_date,source) DO UPDATE SET
                             close=EXCLUDED.close, adjusted_close=EXCLUDED.adjusted_close,
                             volume=EXCLUDED.volume, ingested_at=now()""",
                        (
                            asset["id"],
                            price.price_date,
                            price.close,
                            price.adjusted_close,
                            price.volume,
                            source,
                        ),
                    )
                    price_count += 1
        return price_count

    def assets_with_prices(self):
        with self._connector() as connection:
            assets = connection.execute(
                """SELECT a.id,a.ticker,a.name,a.category,a.sector,
                   EXISTS(SELECT 1 FROM watchlist_assets wa
                     JOIN watchlists w ON w.id=wa.watchlist_id
                     WHERE wa.asset_id=a.id AND w.name='Favoritos') AS favorite
                   FROM assets a WHERE NOT a.is_demo ORDER BY a.ticker"""
            ).fetchall()
            for asset in assets:
                asset["prices"] = connection.execute(
                    """SELECT price_date,close,adjusted_close,source FROM daily_prices
                       WHERE asset_id=%s AND source=(
                         SELECT source FROM daily_prices WHERE asset_id=%s
                         ORDER BY price_date DESC,ingested_at DESC,source LIMIT 1)
                       ORDER BY price_date DESC LIMIT 1260""",
                    (asset["id"], asset["id"]),
                ).fetchall()[::-1]
        return assets

    def training_prices(self, source):
        with self._connector() as connection:
            return connection.execute(
                """SELECT a.ticker,p.price_date,p.close,p.adjusted_close
                   FROM assets a JOIN daily_prices p ON p.asset_id=a.id
                   WHERE NOT a.is_demo AND p.source=%s
                   ORDER BY a.ticker,p.price_date""",
                (source,),
            ).fetchall()

    def model_runs(self, horizon):
        with self._connector() as connection:
            return connection.execute(
                """SELECT id,dataset_id,metrics,created_at FROM model_runs
                   WHERE horizon_months=%s ORDER BY created_at DESC""",
                (horizon,),
            ).fetchall()

    def save_model_run(self, run):
        with self._connector() as connection:
            connection.execute(
                """INSERT INTO model_runs(
                     id,dataset_id,algorithm,horizon_months,metrics,parameters)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (
                    run["id"],
                    run["dataset_id"],
                    run["algorithm"],
                    run["horizon"],
                    Jsonb(run["metrics"]),
                    Jsonb(run["parameters"]),
                ),
            )

    def set_favorite(self, asset_id, saved):
        with self._connector() as connection:
            if not connection.execute(
                "SELECT id FROM assets WHERE id=%s AND NOT is_demo", (asset_id,)
            ).fetchone():
                raise ValueError("Ativo não encontrado.")
            connection.execute("SELECT pg_advisory_xact_lock(741209)")
            watchlist = connection.execute(
                "SELECT id FROM watchlists WHERE name='Favoritos' ORDER BY id LIMIT 1"
            ).fetchone()
            if watchlist is None:
                watchlist = connection.execute(
                    "INSERT INTO watchlists(name) VALUES ('Favoritos') RETURNING id"
                ).fetchone()
            if saved:
                connection.execute(
                    """INSERT INTO watchlist_assets(watchlist_id,asset_id)
                       VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                    (watchlist["id"], asset_id),
                )
            else:
                connection.execute(
                    """DELETE FROM watchlist_assets WHERE asset_id=%s
                       AND watchlist_id IN (
                         SELECT id FROM watchlists WHERE name='Favoritos')""",
                    (asset_id,),
                )

    def portfolio_assets(self, name="Minha Carteira"):
        with self._connector() as connection:
            return connection.execute(
                """SELECT a.ticker,pa.quantity FROM portfolio_assets pa
                   JOIN portfolios p ON p.id=pa.portfolio_id
                   JOIN assets a ON a.id=pa.asset_id
                   WHERE p.name=%s ORDER BY a.ticker""", (name,)
            ).fetchall()

    def portfolio_tickers(self, name="Minha Carteira"):
        return [row["ticker"] for row in self.portfolio_assets(name)]

    def set_portfolio_asset(self, ticker, quantity, name="Minha Carteira"):
        with self._connector() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(741210)")
            portfolio = connection.execute(
                """INSERT INTO portfolios(name) VALUES (%s)
                   ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id""", (name,)
            ).fetchone()
            asset = connection.execute(
                "SELECT id FROM assets WHERE ticker=%s AND NOT is_demo", (ticker,)
            ).fetchone()
            if asset is None:
                raise ValueError("Ativo não encontrado. Importe suas cotações antes de adicionar à carteira.")
            connection.execute(
                """INSERT INTO portfolio_assets(portfolio_id,asset_id,quantity)
                   VALUES (%s,%s,%s) ON CONFLICT (portfolio_id,asset_id) DO UPDATE SET
                   quantity=EXCLUDED.quantity,updated_at=now()""",
                (portfolio["id"], asset["id"], quantity),
            )
        return self.portfolio_assets(name)

    def remove_portfolio_asset(self, ticker, name="Minha Carteira"):
        with self._connector() as connection:
            deleted = connection.execute(
                """DELETE FROM portfolio_assets pa USING portfolios p,assets a
                   WHERE pa.portfolio_id=p.id AND pa.asset_id=a.id
                   AND p.name=%s AND a.ticker=%s RETURNING pa.asset_id""",
                (name, ticker),
            ).fetchone()
        return bool(deleted)

class MongoRepository:
    def __init__(self, connector=connect_mongo):
        self._connector = connector

    def publish_dataset(self, metadata, samples):
        with self._connector() as client:
            database = client.midas_training
            database.datasets.insert_one(metadata)
            try:
                database.training_samples.insert_many(samples, ordered=True)
            except Exception:
                database.datasets.delete_one({"_id": metadata["_id"]})
                database.training_samples.delete_many({"dataset_id": metadata["_id"]})
                raise

    def dataset_exists(self, dataset_id):
        with self._connector() as client:
            return bool(client.midas_training.datasets.find_one(
                {"_id": dataset_id, "is_demo": False}
            ))

    def training_samples(self, dataset_id, horizon):
        with self._connector() as client:
            return list(client.midas_training.training_samples.find(
                {"dataset_id": dataset_id, "horizon_months": horizon}
            ).sort("as_of", 1))

    def save_artifact(self, artifact):
        with self._connector() as client:
            client.midas_training.model_artifacts.insert_one(artifact)

    def delete_artifact(self, artifact_id):
        with self._connector() as client:
            client.midas_training.model_artifacts.delete_one({"_id": artifact_id})

    def dataset_count(self):
        with self._connector() as client:
            return client.midas_training.datasets.count_documents({"is_demo": False})

    def artifact_for_run(self, run):
        with self._connector() as client:
            database = client.midas_training
            dataset = database.datasets.find_one(
                {"_id": run["dataset_id"], "is_demo": False}
            )
            artifact = database.model_artifacts.find_one({"_id": str(run["id"])})
            return artifact if dataset and artifact else None
