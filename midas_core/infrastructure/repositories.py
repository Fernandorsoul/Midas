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
                # Fonte da série: oficial (yahoo/brapi) antes de experimental;
                # dentro da mesma classe, a mais recente. A série nunca mistura fontes.
                asset["prices"] = connection.execute(
                    """SELECT price_date,close,adjusted_close,source,ingested_at FROM daily_prices
                       WHERE asset_id=%s AND source=(
                         SELECT source FROM daily_prices WHERE asset_id=%s
                         ORDER BY CASE WHEN source IN ('yahoo.finance','brapi.dev') THEN 0 ELSE 1 END,
                                  price_date DESC,ingested_at DESC,source LIMIT 1)
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

    def _ensure_portfolio(self, connection, name):
        connection.execute("SELECT pg_advisory_xact_lock(741210)")
        portfolio = connection.execute(
            """INSERT INTO portfolios(name) VALUES (%s)
               ON CONFLICT (name) DO UPDATE SET name=EXCLUDED.name RETURNING id""",
            (name,),
        ).fetchone()
        return portfolio["id"]

    def _ensure_asset(self, connection, ticker):
        asset = connection.execute(
            "SELECT id FROM assets WHERE ticker=%s AND NOT is_demo", (ticker,)
        ).fetchone()
        if asset is None:
            raise ValueError("Ativo não encontrado. Importe suas cotações antes de lançar operações.")
        return asset["id"]

    def list_portfolio_operations(self, name="Minha Carteira", ticker=None):
        with self._connector() as connection:
            sql = """SELECT po.id,a.ticker,po.operation_type,po.occurred_on,po.quantity,
                            po.unit_price,po.amount,po.fees,po.taxes,po.currency,po.notes,
                            po.created_at,po.updated_at
                     FROM portfolio_operations po
                     JOIN portfolios p ON p.id=po.portfolio_id
                     LEFT JOIN assets a ON a.id=po.asset_id
                     WHERE p.name=%s"""
            params = [name]
            if ticker:
                sql += " AND a.ticker=%s"
                params.append(ticker)
            sql += " ORDER BY po.occurred_on, po.id"
            return connection.execute(sql, params).fetchall()

    def get_portfolio_operation(self, operation_id, name="Minha Carteira"):
        with self._connector() as connection:
            return connection.execute(
                """SELECT po.id,a.ticker,po.operation_type,po.occurred_on,po.quantity,
                          po.unit_price,po.amount,po.fees,po.taxes,po.currency,po.notes,
                          po.created_at,po.updated_at
                   FROM portfolio_operations po
                   JOIN portfolios p ON p.id=po.portfolio_id
                   LEFT JOIN assets a ON a.id=po.asset_id
                   WHERE po.id=%s AND p.name=%s""",
                (operation_id, name),
            ).fetchone()

    def insert_portfolio_operation(
        self, portfolio_name, ticker, operation_type, occurred_on,
        quantity, unit_price, amount, fees, taxes, currency, notes=None,
    ):
        with self._connector() as connection:
            portfolio_id = self._ensure_portfolio(connection, portfolio_name)
            asset_id = self._ensure_asset(connection, ticker) if ticker else None
            return connection.execute(
                """INSERT INTO portfolio_operations(
                       portfolio_id,asset_id,operation_type,occurred_on,quantity,
                       unit_price,amount,fees,taxes,currency,notes)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING id,operation_type,occurred_on,quantity,unit_price,amount,
                             fees,taxes,currency,notes,created_at,updated_at""",
                (
                    portfolio_id, asset_id, operation_type, occurred_on, quantity,
                    unit_price, amount, fees, taxes, currency, notes,
                ),
            ).fetchone() | {"ticker": ticker}

    def update_portfolio_operation(
        self, operation_id, ticker, operation_type, occurred_on,
        quantity, unit_price, amount, fees, taxes, currency, notes=None,
    ):
        with self._connector() as connection:
            asset_id = self._ensure_asset(connection, ticker) if ticker else None
            row = connection.execute(
                """UPDATE portfolio_operations SET
                       asset_id=%s,operation_type=%s,occurred_on=%s,quantity=%s,
                       unit_price=%s,amount=%s,fees=%s,taxes=%s,currency=%s,
                       notes=%s,updated_at=now()
                   WHERE id=%s
                   RETURNING id,operation_type,occurred_on,quantity,unit_price,amount,
                             fees,taxes,currency,notes,created_at,updated_at""",
                (
                    asset_id, operation_type, occurred_on, quantity, unit_price,
                    amount, fees, taxes, currency, notes, operation_id,
                ),
            ).fetchone()
            if row is None:
                raise ValueError("Operação não encontrada.")
            return row | {"ticker": ticker}

    def delete_portfolio_operation(self, operation_id, name="Minha Carteira"):
        with self._connector() as connection:
            deleted = connection.execute(
                """DELETE FROM portfolio_operations po USING portfolios p
                   WHERE po.portfolio_id=p.id AND po.id=%s AND p.name=%s
                   RETURNING po.id""",
                (operation_id, name),
            ).fetchone()
            return bool(deleted)

    def latest_price(self, ticker, source=None):
        with self._connector() as connection:
            if source:
                return connection.execute(
                    """SELECT p.close,p.adjusted_close,p.price_date,p.source,p.ingested_at
                       FROM daily_prices p JOIN assets a ON a.id=p.asset_id
                       WHERE a.ticker=%s AND p.source=%s
                       ORDER BY p.price_date DESC LIMIT 1""",
                    (ticker, source),
                ).fetchone()
            return connection.execute(
                """SELECT p.close,p.adjusted_close,p.price_date,p.source,p.ingested_at
                   FROM daily_prices p JOIN assets a ON a.id=p.asset_id
                   WHERE a.ticker=%s
                   ORDER BY CASE WHEN p.source IN ('yahoo.finance','brapi.dev') THEN 0 ELSE 1 END,
                            p.price_date DESC,p.ingested_at DESC LIMIT 1""",
                (ticker,),
            ).fetchone()

    # --- Jobs persistidos ---

    def insert_job(self, job_type, payload, step="queued", user_id=None):
        with self._connector() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(741211)")
            active = connection.execute(
                """SELECT job_type FROM jobs
                   WHERE status IN ('queued','running')
                   FOR UPDATE""",
            ).fetchall()
            active_types = {row["job_type"] for row in active}
            if job_type == "training" and "training" in active_types:
                raise ValueError("Já existe um treinamento na fila ou em execução.")
            return connection.execute(
                """INSERT INTO jobs(job_type,status,step,payload,user_id)
                   VALUES (%s,'queued',%s,%s,%s)
                   RETURNING id,job_type,status,step,payload,result,progress,error,
                             cancel_requested,created_at,started_at,finished_at,updated_at""",
                (job_type, step, Jsonb(payload), user_id),
            ).fetchone()

    def list_jobs(self, job_type=None, limit=20):
        with self._connector() as connection:
            if job_type:
                return connection.execute(
                    """SELECT id,job_type,status,step,payload,result,progress,error,
                              cancel_requested,created_at,started_at,finished_at,updated_at
                       FROM jobs WHERE job_type=%s
                       ORDER BY created_at DESC,id DESC LIMIT %s""",
                    (job_type, limit),
                ).fetchall()
            return connection.execute(
                """SELECT id,job_type,status,step,payload,result,progress,error,
                          cancel_requested,created_at,started_at,finished_at,updated_at
                   FROM jobs ORDER BY created_at DESC,id DESC LIMIT %s""",
                (limit,),
            ).fetchall()

    def get_job(self, job_id):
        with self._connector() as connection:
            return connection.execute(
                """SELECT id,job_type,status,step,payload,result,progress,error,
                          cancel_requested,created_at,started_at,finished_at,updated_at
                   FROM jobs WHERE id=%s""",
                (job_id,),
            ).fetchone()

    def claim_next_job(self):
        """Reivindica o próximo job queued de forma segura entre workers."""
        with self._connector() as connection:
            row = connection.execute(
                """UPDATE jobs SET status='running', started_at=now(), updated_at=now()
                   WHERE id = (
                     SELECT id FROM jobs
                     WHERE status='queued' AND NOT cancel_requested
                     ORDER BY created_at,id
                     FOR UPDATE SKIP LOCKED
                     LIMIT 1
                   )
                   RETURNING id,job_type,status,step,payload,result,progress,error,
                             cancel_requested,created_at,started_at,finished_at,updated_at""",
            ).fetchone()
            return row

    def update_job_progress(self, job_id, step, progress, result=None):
        with self._connector() as connection:
            return connection.execute(
                """UPDATE jobs SET step=%s, progress=%s,
                       result=COALESCE(%s, result), updated_at=now()
                   WHERE id=%s AND status='running'
                   RETURNING id,job_type,status,step,payload,result,progress,error,
                             cancel_requested,created_at,started_at,finished_at,updated_at""",
                (step, progress, Jsonb(result) if result is not None else None, job_id),
            ).fetchone()

    def finish_job(self, job_id, status, result=None, error=None):
        with self._connector() as connection:
            return connection.execute(
                """UPDATE jobs SET status=%s, step=%s, progress=CASE WHEN %s='succeeded' THEN 100 ELSE progress END,
                       result=COALESCE(%s, result), error=%s,
                       finished_at=now(), updated_at=now()
                   WHERE id=%s AND status IN ('running','queued')
                   RETURNING id,job_type,status,step,payload,result,progress,error,
                             cancel_requested,created_at,started_at,finished_at,updated_at""",
                (
                    status,
                    "done" if status == "succeeded" else ("failed" if status == "failed" else "cancelled"),
                    status,
                    Jsonb(result) if result is not None else None,
                    error,
                    job_id,
                ),
            ).fetchone()

    def request_job_cancel(self, job_id):
        """Cancela queued imediatamente; running marca cancel_requested."""
        with self._connector() as connection:
            row = connection.execute(
                """UPDATE jobs SET
                       status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END,
                       finished_at=CASE WHEN status='queued' THEN now() ELSE finished_at END,
                       cancel_requested=true,
                       step=CASE WHEN status='queued' THEN 'cancelled' ELSE step END,
                       updated_at=now()
                   WHERE id=%s AND status IN ('queued','running')
                   RETURNING id,job_type,status,step,payload,result,progress,error,
                             cancel_requested,created_at,started_at,finished_at,updated_at""",
                (job_id,),
            ).fetchone()
            return row

    def requeue_interrupted_jobs(self):
        """Reenfileira jobs running órfãos após reinício do worker.

        Executado uma vez no start, sob lock consultivo, para que um job
        interrompido por crash/reinício não fique preso em running.
        """
        with self._connector() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(741212)")
            return connection.execute(
                """UPDATE jobs SET status='queued', step='queued', progress=0,
                       started_at=NULL, error=NULL, updated_at=now()
                   WHERE status='running'
                   RETURNING id""",
            ).fetchall()

    # --- Usuários e sessões ---

    def create_user(self, email, password_hash):
        with self._connector() as connection:
            existing = connection.execute(
                "SELECT id FROM users WHERE email=%s", (email,)
            ).fetchone()
            if existing:
                raise ValueError("E-mail já cadastrado.")
            return connection.execute(
                """INSERT INTO users(email,password_hash) VALUES (%s,%s)
                   RETURNING id,email,created_at""",
                (email, password_hash),
            ).fetchone()

    def get_user_by_email(self, email):
        with self._connector() as connection:
            return connection.execute(
                "SELECT id,email,password_hash,created_at FROM users WHERE email=%s",
                (email,),
            ).fetchone()

    def get_user(self, user_id):
        with self._connector() as connection:
            return connection.execute(
                "SELECT id,email,created_at FROM users WHERE id=%s", (user_id,)
            ).fetchone()

    def create_session(self, token_hash, user_id, expires_at):
        with self._connector() as connection:
            connection.execute(
                """INSERT INTO user_sessions(token_hash,user_id,expires_at)
                   VALUES (%s,%s,%s)""",
                (token_hash, user_id, expires_at),
            )
            return {"token_hash": token_hash, "user_id": user_id, "expires_at": expires_at}

    def get_session_user(self, token_hash):
        with self._connector() as connection:
            return connection.execute(
                """SELECT u.id,u.email,s.expires_at
                   FROM user_sessions s JOIN users u ON u.id=s.user_id
                   WHERE s.token_hash=%s AND s.expires_at > now()""",
                (token_hash,),
            ).fetchone()

    def delete_session(self, token_hash):
        with self._connector() as connection:
            deleted = connection.execute(
                "DELETE FROM user_sessions WHERE token_hash=%s RETURNING token_hash",
                (token_hash,),
            ).fetchone()
            return bool(deleted)

    def export_user_data(self, user_id):
        """Exporta dados do usuário sem expor hashes de senha/token."""
        with self._connector() as connection:
            user = connection.execute(
                "SELECT id,email,created_at FROM users WHERE id=%s", (user_id,)
            ).fetchone()
            if user is None:
                raise ValueError("Usuário não encontrado.")
            portfolios = connection.execute(
                "SELECT id,name,created_at FROM portfolios WHERE user_id=%s ORDER BY id",
                (user_id,),
            ).fetchall()
            operations = connection.execute(
                """SELECT po.id,a.ticker,po.operation_type,po.occurred_on,po.quantity,
                          po.unit_price,po.amount,po.fees,po.taxes,po.currency,po.notes
                   FROM portfolio_operations po
                   JOIN portfolios p ON p.id=po.portfolio_id
                   LEFT JOIN assets a ON a.id=po.asset_id
                   WHERE p.user_id=%s ORDER BY po.occurred_on,po.id""",
                (user_id,),
            ).fetchall()
            jobs = connection.execute(
                """SELECT id,job_type,status,step,progress,created_at,finished_at
                   FROM jobs WHERE user_id=%s ORDER BY created_at""",
                (user_id,),
            ).fetchall()
            return {"user": user, "portfolios": portfolios, "operations": operations, "jobs": jobs}

    def delete_user_data(self, user_id):
        """Remove dados do usuário e a conta (com cascata em sessões)."""
        with self._connector() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(741213)")
            connection.execute("DELETE FROM jobs WHERE user_id=%s", (user_id,))
            connection.execute(
                """DELETE FROM portfolio_operations po USING portfolios p
                   WHERE po.portfolio_id=p.id AND p.user_id=%s""",
                (user_id,),
            )
            connection.execute("DELETE FROM portfolio_assets pa USING portfolios p WHERE pa.portfolio_id=p.id AND p.user_id=%s", (user_id,))
            connection.execute("DELETE FROM watchlist_assets wa USING watchlists w WHERE wa.watchlist_id=w.id AND w.user_id=%s", (user_id,))
            connection.execute("DELETE FROM watchlists WHERE user_id=%s", (user_id,))
            connection.execute("DELETE FROM portfolios WHERE user_id=%s", (user_id,))
            deleted = connection.execute(
                "DELETE FROM users WHERE id=%s RETURNING id", (user_id,)
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
