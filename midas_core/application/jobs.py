"""Caso de uso de jobs persistidos: enfileirar, consultar, cancelar e executar.

O worker reivindica jobs do PostgreSQL e executa importação ou treino sem
bloquear a interface. Estados vivem no banco e sobrevivem a reinícios.
"""
from midas_core.domain.jobs import (
    ACTIVE_STATUSES,
    QUEUED,
    RUNNING,
    SUCCEEDED,
    FAILED,
    CANCELLED,
    JobTransitionError,
    can_start_new,
    normalize_job_type,
    safe_error_message,
    validate_step,
)

DEFAULT_LIMIT = 20


def _row_to_api(row):
    if row is None:
        return None
    payload = row["payload"] or {}
    result = row["result"] or {}
    return {
        "id": row["id"],
        "job_type": row["job_type"],
        "status": row["status"],
        "step": row["step"],
        "progress": float(row["progress"] or 0),
        "payload": payload,
        "result": result,
        "error": row["error"],
        "cancel_requested": bool(row["cancel_requested"]),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "started_at": row["started_at"].isoformat() if row.get("started_at") else None,
        "finished_at": row["finished_at"].isoformat() if row.get("finished_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
        # Campos legados usados pela UI de treino
        "message": result.get("message") or row["error"] or _default_message(row["status"], row["step"]),
        "dataset_id": result.get("dataset_id"),
        "sample_count": result.get("sample_count"),
        "run_id": result.get("run_id"),
        "horizon": payload.get("horizon"),
        "ticker": payload.get("ticker"),
    }


def _default_message(status, step):
    if status == QUEUED:
        return "Job na fila."
    if status == RUNNING:
        return f"Executando etapa {step}."
    if status == SUCCEEDED:
        return "Job concluído."
    if status == FAILED:
        return "Job falhou."
    if status == CANCELLED:
        return "Job cancelado."
    return "Estado desconhecido."


def _validate_training_payload(payload):
    horizon = payload.get("horizon")
    if type(horizon) is not int or horizon not in (6, 12, 24, 36):
        raise ValueError("Horizonte inválido.")
    tickers = payload.get("tickers")
    if tickers is not None and not isinstance(tickers, list):
        raise ValueError("Tickers inválidos.")
    source = payload.get("source")
    if source is not None and not isinstance(source, str):
        raise ValueError("Fonte inválida.")
    return {
        "horizon": horizon,
        "tickers": tickers,
        "source": source or None,
    }


def _validate_import_payload(payload):
    ticker = str(payload.get("ticker") or "").strip().upper()
    if not ticker or not ticker.replace(".", "").replace("-", "").isalnum():
        raise ValueError("Ticker inválido.")
    quantity = payload.get("quantity", 100)
    if not isinstance(quantity, (int, float)) or quantity <= 0:
        raise ValueError("Quantidade inválida.")
    add_to_portfolio = bool(payload.get("add_to_portfolio", True))
    market_range = str(payload.get("range") or "5y")
    if market_range not in ("1y", "2y", "5y", "max"):
        raise ValueError("Período de importação inválido.")
    return {
        "ticker": ticker,
        "quantity": int(quantity),
        "add_to_portfolio": add_to_portfolio,
        "range": market_range,
    }


def enqueue_job(job_type, payload, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    kind = normalize_job_type(job_type)
    if not isinstance(payload, dict):
        raise ValueError("Payload inválido.")
    if kind == "training":
        clean = _validate_training_payload(payload)
    else:
        clean = _validate_import_payload(payload)
    row = repository.insert_job(kind, clean)
    return {"job": _row_to_api(row), "message": "Job enfileirado."}


def get_job(job_id, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    if not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("id de job inválido.")
    row = repository.get_job(job_id)
    if row is None:
        raise ValueError("Job não encontrado.")
    return {"job": _row_to_api(row)}


def list_jobs(job_type=None, limit=DEFAULT_LIMIT, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    if job_type:
        job_type = normalize_job_type(job_type)
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        limit = DEFAULT_LIMIT
    rows = repository.list_jobs(job_type=job_type, limit=limit)
    return {"jobs": [_row_to_api(row) for row in rows]}


def latest_job(job_type, repository=None):
    result = list_jobs(job_type=job_type, limit=1, repository=repository)
    jobs = result["jobs"]
    return {"job": jobs[0] if jobs else None}


def cancel_job(job_id, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    if not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("id de job inválido.")
    existing = repository.get_job(job_id)
    if existing is None:
        raise ValueError("Job não encontrado.")
    if existing["status"] in ("succeeded", "failed", "cancelled"):
        raise ValueError("Job já finalizado.")
    row = repository.request_job_cancel(job_id)
    return {"job": _row_to_api(row), "message": "Cancelamento solicitado."}


def retry_job(job_id, repository=None):
    """Reexecuta um job falho/cancelado criando um novo job com o mesmo payload."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    if not isinstance(job_id, int) or job_id <= 0:
        raise ValueError("id de job inválido.")
    existing = repository.get_job(job_id)
    if existing is None:
        raise ValueError("Job não encontrado.")
    if existing["status"] not in (FAILED, CANCELLED):
        raise ValueError("Somente jobs falhos ou cancelados podem ser reexecutados.")
    return enqueue_job(existing["job_type"], existing["payload"] or {}, repository=repository)


class JobCancelled(Exception):
    """Worker interrompeu o job a pedido do usuário."""


class JobWorker:
    """Executa jobs reivindicados do PostgreSQL."""

    def __init__(self, repository=None, handlers=None, poll_seconds=1.0, recover=True):
        from midas_core.infrastructure.repositories import PostgresRepository
        self.repository = repository or PostgresRepository()
        self.poll_seconds = poll_seconds
        self.handlers = handlers or {
            "training": self._run_training,
            "import": self._run_import,
        }
        if recover:
            self.recover_interrupted_jobs()

    def recover_interrupted_jobs(self):
        """Reenfileira jobs que ficaram em running após um reinício."""
        requeue = getattr(self.repository, "requeue_interrupted_jobs", None)
        if requeue is None:
            return []
        return requeue()

    def run_once(self):
        job = self.repository.claim_next_job()
        if job is None:
            return None
        try:
            result = self.execute(job)
            if job["cancel_requested"]:
                self.repository.finish_job(job["id"], CANCELLED, result=result, error="Cancelado pelo usuário.")
            else:
                self.repository.finish_job(job["id"], SUCCEEDED, result=result)
        except JobCancelled:
            self.repository.finish_job(job["id"], CANCELLED, error="Cancelado pelo usuário.")
        except Exception as error:
            self.repository.finish_job(job["id"], FAILED, error=safe_error_message(error))
        return self.repository.get_job(job["id"])

    def execute(self, job):
        handler = self.handlers.get(job["job_type"])
        if handler is None:
            raise ValueError("Tipo de job sem executor.")
        self._ensure_not_cancelled(job)
        return handler(job)

    def _ensure_not_cancelled(self, job):
        current = self.repository.get_job(job["id"])
        if current and current["cancel_requested"]:
            raise JobCancelled()

    def _progress(self, job, step, progress, result=None):
        self.repository.update_job_progress(job["id"], step, progress, result=result)
        self._ensure_not_cancelled(job)

    def _run_training(self, job):
        from midas_core.application.datasets import publish_dataset
        from midas_core.application.training import train

        payload = job["payload"] or {}
        horizon = payload.get("horizon")
        tickers = payload.get("tickers")
        source = payload.get("source")

        self._progress(job, "dataset", 10, {"message": "Publicando dataset no MongoDB..."})
        dataset_id, sample_count = publish_dataset((horizon,), source=source, tickers=tickers)
        self._progress(job, "training", 50, {
            "message": "Treinando modelos e validando temporalmente...",
            "dataset_id": dataset_id,
            "sample_count": sample_count,
        })
        run_id = train(dataset_id, horizon)
        return {
            "message": "Treinamento concluído.",
            "dataset_id": dataset_id,
            "sample_count": sample_count,
            "run_id": run_id,
        }

    def _run_import(self, job):
        from midas_core.infrastructure.yahoo import SOURCE, YahooFinanceError, fetch_history

        payload = job["payload"] or {}
        ticker = payload.get("ticker")
        market_range = payload.get("range") or "5y"
        add_to_portfolio = bool(payload.get("add_to_portfolio", True))
        quantity = payload.get("quantity", 100)

        self._progress(job, "import", 20, {"message": f"Importando cotações de {ticker}..."})
        try:
            stock = fetch_history(ticker, market_range)
        except YahooFinanceError as error:
            raise RuntimeError("Não foi possível importar cotações do Yahoo Finance.") from error
        price_count = self.repository.save_stocks([stock], SOURCE)
        result = {
            "message": f"{ticker} importado.",
            "ticker": ticker,
            "prices": price_count,
            "status": "imported",
            "source": SOURCE,
            "collection": {
                "status": "succeeded",
                "imported": 1,
                "failed": 0,
            },
        }
        if add_to_portfolio:
            self._progress(job, "portfolio", 70, result)
            rows = self.repository.set_portfolio_asset(ticker, quantity)
            result["portfolio"] = {row["ticker"]: float(row["quantity"]) for row in rows}
            result["tickers"] = sorted(result["portfolio"])
            result["message"] = f"{ticker} adicionado à carteira com {quantity} cotas."
        return result

    def run_forever(self, stop_event=None):
        import time
        while stop_event is None or not stop_event.is_set():
            processed = self.run_once()
            if processed is None:
                time.sleep(self.poll_seconds)
