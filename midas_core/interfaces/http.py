"""Interface HTTP local; valida entrada e delega casos de uso."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlparse

import psycopg
from pymongo.errors import PyMongoError

from midas_core.application.analysis import build_report, build_portfolio_report, set_favorite
from midas_core.application.jobs import (
    cancel_job,
    enqueue_job,
    get_job,
    latest_job,
    list_jobs,
    retry_job,
    JobWorker,
)
from midas_core.application.market_quality import market_quality_report
from midas_core.application.wealth_dashboard import wealth_dashboard
from midas_core.application.portfolio_ledger import (
    delete_operation,
    edit_operation,
    list_operations,
    position_summary,
    record_operation,
)
from midas_core.config import PROJECT_ROOT, Settings
from midas_core.infrastructure.repositories import PostgresRepository

WEB_ROOT = PROJECT_ROOT / "web"


class MarketDataUnavailable(RuntimeError):
    """A fonte de mercado não respondeu para uma operação de carteira."""

class RequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_ROOT), **kwargs)

    def respond(self, status, body):
        data = json.dumps(body, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/training/status":
            try:
                result = latest_job("training", repository=PostgresRepository())
                job = result["job"]
                if job is None:
                    self.respond(200, {"status": "idle", "message": "Nenhum treinamento em execução."})
                else:
                    self.respond(200, job)
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if url.path == "/api/market/quality":
            try:
                self.respond(200, market_quality_report(repository=PostgresRepository()))
            except (psycopg.Error, PyMongoError, KeyError):
                self.respond(503, {"error": "Não foi possível acessar os bancos de dados."})
            return
        if url.path == "/api/wealth/dashboard":
            try:
                self.respond(200, wealth_dashboard(repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except (psycopg.Error, PyMongoError, KeyError):
                self.respond(503, {"error": "Não foi possível acessar os bancos de dados."})
            return
        if url.path == "/api/jobs":
            try:
                query = parse_qs(url.query)
                job_id = query.get("job_id", [None])[0]
                if job_id is not None:
                    self.respond(200, get_job(int(job_id), repository=PostgresRepository()))
                else:
                    job_type = query.get("type", [None])[0]
                    limit = int(query.get("limit", ["20"])[0])
                    self.respond(200, list_jobs(job_type=job_type, limit=limit, repository=PostgresRepository()))
            except (ValueError, TypeError) as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if url.path == "/api/analysis":
            try:
                horizon = int(parse_qs(url.query).get("horizon", ["12"])[0])
                self.respond(200, build_report(horizon))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except (psycopg.Error, PyMongoError, KeyError):
                self.respond(503, {"error": "Não foi possível acessar os bancos de dados."})
            return
        if url.path == "/api/portfolio":
            try:
                horizon = int(parse_qs(url.query).get("horizon", ["6"])[0])
                tickers = PostgresRepository().portfolio_tickers()
                self.respond(200, build_portfolio_report(horizon, tickers))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except (psycopg.Error, PyMongoError, KeyError):
                self.respond(503, {"error": "Não foi possível acessar os bancos de dados."})
            return
        if url.path == "/api/portfolio/list":
            try:
                self.respond(200, _get_portfolio_list())
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if url.path == "/api/portfolio/dividends":
            try:
                self.respond(200, _get_portfolio_dividends())
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if url.path == "/api/portfolio/operations":
            try:
                query = parse_qs(url.query)
                ticker = query.get("ticker", [None])[0]
                self.respond(200, list_operations(repository=PostgresRepository(), ticker=ticker))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if url.path == "/api/portfolio/positions":
            try:
                ticker = parse_qs(url.query).get("ticker", [None])[0]
                self.respond(200, position_summary(ticker=ticker, repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if url.path.startswith("/api/"):
            self.respond(404, {"error": "Rota não encontrada."})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/portfolio/add":
            if not self._require_same_origin():
                return
            try:
                body = self._read_json()
                ticker = body.get("ticker", "").strip().upper()
                quantity = body.get("quantity", 100)
                if not ticker:
                    raise ValueError("Ticker inválido.")
                if not isinstance(quantity, (int, float)) or quantity <= 0:
                    raise ValueError("Quantidade inválida.")
                result = enqueue_job("import", {
                    "ticker": ticker,
                    "quantity": int(quantity),
                    "add_to_portfolio": True,
                    "range": "5y",
                }, repository=PostgresRepository())
                self.respond(202, result)
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path == "/api/portfolio/remove":
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                self.respond(403, {"error": "Origem não permitida."})
                return
            try:
                body = self._read_json()
                ticker = body.get("ticker", "").strip().upper()
                if not ticker:
                    raise ValueError("Ticker inválido.")
                result = _remove_from_portfolio(ticker)
                self.respond(200, result)
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path == "/api/portfolio/operations":
            if not self._require_same_origin():
                return
            try:
                body = self._read_json()
                self.respond(201, record_operation(body, repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path == "/api/portfolio/operations/delete":
            if not self._require_same_origin():
                return
            try:
                body = self._read_json()
                operation_id = body.get("id")
                if type(operation_id) is not int:
                    raise ValueError("id da operação inválido.")
                self.respond(200, delete_operation(operation_id, repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path == "/api/jobs":
            if not self._require_same_origin():
                return
            try:
                body = self._read_json()
                result = enqueue_job(body.get("type") or body.get("job_type"), body.get("payload") or {
                    key: body[key] for key in ("horizon", "tickers", "source", "ticker", "quantity", "add_to_portfolio", "range") if key in body
                }, repository=PostgresRepository())
                self.respond(202, result)
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path == "/api/jobs/cancel":
            if not self._require_same_origin():
                return
            try:
                body = self._read_json()
                job_id = body.get("id") or body.get("job_id")
                if type(job_id) is not int:
                    raise ValueError("id de job inválido.")
                self.respond(200, cancel_job(job_id, repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path == "/api/jobs/retry":
            if not self._require_same_origin():
                return
            try:
                body = self._read_json()
                job_id = body.get("id") or body.get("job_id")
                if type(job_id) is not int:
                    raise ValueError("id de job inválido.")
                self.respond(202, retry_job(job_id, repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path != "/api/training":
            self.respond(404, {"error": "Rota não encontrada."})
            return
        if not self._require_same_origin():
            return
        try:
            body = self._read_json()
            horizon = body.get("horizon", 6)
            tickers = PostgresRepository().portfolio_tickers() or None
            result = enqueue_job("training", {
                "horizon": horizon,
                "tickers": tickers,
                "source": None,
            }, repository=PostgresRepository())
            self.respond(202, result["job"])
        except ValueError as error:
            self.respond(409 if "Já existe" in str(error) else 400, {"error": str(error)})
        except psycopg.Error:
            self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})

    def do_PUT(self):
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.respond(403, {"error": "Origem não permitida."})
            return
        if self.path == "/api/portfolio/operations":
            try:
                body = self._read_json()
                operation_id = body.get("id")
                if type(operation_id) is not int:
                    raise ValueError("id da operação inválido.")
                self.respond(200, edit_operation(operation_id, body, repository=PostgresRepository()))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except psycopg.Error:
                self.respond(503, {"error": "Não foi possível acessar o PostgreSQL."})
            return
        if self.path != "/api/favorites":
            self.respond(404, {"error": "Rota não encontrada."})
            return
        try:
            body = self._read_json()
            if type(body.get("asset_id")) is not int or type(body.get("saved")) is not bool:
                raise ValueError("asset_id e saved inválidos.")
            set_favorite(body["asset_id"], body["saved"])
            self.respond(200, {"saved": body["saved"]})
        except (ValueError, UnicodeError) as error:
            self.respond(400, {"error": str(error)})
        except (psycopg.Error, KeyError):
            self.respond(503, {"error": "Não foi possível salvar no PostgreSQL."})

    def _require_same_origin(self):
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.respond(403, {"error": "Origem não permitida."})
            return False
        return True

    def _read_json(self):
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 4096 or self.headers.get("Content-Type") != "application/json":
            raise ValueError("Envie um objeto JSON válido.")
        body = json.loads(self.rfile.read(size))
        if not isinstance(body, dict):
            raise ValueError("Envie um objeto JSON válido.")
        return body

def run_server():
    settings = Settings.from_environment()
    # Worker embutido permite modo single-process; em produção use o processo
    # dedicado `python midas_core/worker.py` (serviço `worker` no compose).
    worker = JobWorker()
    worker_thread = threading.Thread(target=worker.run_forever, daemon=True, name="job-worker")
    worker_thread.start()
    server = ThreadingHTTPServer((settings.http_host, settings.http_port), RequestHandler)
    print(f"Midas disponível em http://localhost:{settings.http_port}", flush=True)
    server.serve_forever()

def _get_portfolio_list():
    """Retorna posições persistidas da carteira padrão."""
    rows = PostgresRepository().portfolio_assets()
    portfolio = {row["ticker"]: float(row["quantity"]) for row in rows}
    return {"tickers": sorted(portfolio), "portfolio": portfolio}

def _remove_from_portfolio(ticker):
    """Remove uma posição persistida da carteira padrão."""
    repository = PostgresRepository()
    removed = repository.remove_portfolio_asset(ticker)
    result = _get_portfolio_list()
    result["message"] = f"{ticker} removido da carteira." if removed else f"{ticker} não está na carteira."
    return result

def _get_portfolio_dividends():
    """Retorna dados de dividendos dos ativos da carteira."""
    from midas_core.infrastructure.yahoo import fetch_dividends, YahooFinanceError
    portfolio = _get_portfolio_list()["portfolio"]
    tickers = list(portfolio)
    quantities = portfolio
    
    if not tickers:
        return {"dividends": {}}
    
    dividends = {}
    for ticker in tickers:
        try:
            div_data = fetch_dividends(ticker)
            quantity = quantities.get(ticker, 100)
            annual_div = div_data.get("annual_dividend", 0) or 0
            price = div_data.get("price", 0) or 0
            dividend_yield = div_data.get("dividend_yield", 0) or 0
            
            # Calcular reinvestimento
            total_dividends = annual_div * quantity
            shares_from_dividends = int(total_dividends / price) if price > 0 else 0
            
            dividends[ticker] = {
                "annual_dividend": round(annual_div, 4),
                "dividend_yield": round(dividend_yield * 100, 2),
                "price": round(price, 2),
                "quantity": quantity,
                "total_dividends": round(total_dividends, 2),
                "shares_from_dividends": shares_from_dividends,
                "status": "ok",
            }
        except (YahooFinanceError, Exception) as e:
            dividends[ticker] = {
                "status": "error",
                "error": str(e),
            }
    
    return {"dividends": dividends}
