"""Interface HTTP local; valida entrada e delega casos de uso."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from datetime import datetime, timezone
import json
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import psycopg
from pymongo.errors import PyMongoError

from midas_core.application.analysis import build_report, build_portfolio_report, set_favorite
from midas_core.application.datasets import publish_dataset
from midas_core.application.training import train
from midas_core.config import PROJECT_ROOT, Settings

WEB_ROOT = PROJECT_ROOT / "web"
PORTFOLIO_FILE = PROJECT_ROOT / "data" / "my-portfolio.txt"
TRAINING_LOCK = threading.Lock()
TRAINING_JOB = {"status": "idle", "message": "Nenhum treinamento em execução."}

def _training_snapshot():
    with TRAINING_LOCK:
        return dict(TRAINING_JOB)

def _update_training_job(**values):
    with TRAINING_LOCK:
        TRAINING_JOB.update(values)

def _run_training_job(horizon):
    started_at = datetime.now(timezone.utc).isoformat()
    try:
        _update_training_job(
            status="running",
            step="dataset",
            message="Publicando dataset no MongoDB...",
            horizon=horizon,
            started_at=started_at,
            finished_at=None,
            dataset_id=None,
            sample_count=None,
            run_id=None,
            error=None,
        )
        dataset_id, sample_count = publish_dataset((horizon,))
        _update_training_job(
            step="training",
            message="Treinando modelos e validando temporalmente...",
            dataset_id=dataset_id,
            sample_count=sample_count,
        )
        run_id = train(dataset_id, horizon)
        _update_training_job(
            status="succeeded",
            step="done",
            message="Treinamento concluído.",
            run_id=run_id,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as error:
        _update_training_job(
            status="failed",
            step="failed",
            message="Treinamento falhou.",
            error=str(error),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )

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
            self.respond(200, _training_snapshot())
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
                self.respond(200, build_portfolio_report(horizon))
            except ValueError as error:
                self.respond(400, {"error": str(error)})
            except (psycopg.Error, PyMongoError, KeyError):
                self.respond(503, {"error": "Não foi possível acessar os bancos de dados."})
            return
        if url.path == "/api/portfolio/list":
            self.respond(200, _get_portfolio_list())
            return
        if url.path.startswith("/api/"):
            self.respond(404, {"error": "Rota não encontrada."})
        else:
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/portfolio/add":
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                self.respond(403, {"error": "Origem não permitida."})
                return
            try:
                body = self._read_json()
                ticker = body.get("ticker", "").strip().upper()
                if not ticker:
                    raise ValueError("Ticker inválido.")
                result = _add_to_portfolio(ticker)
                self.respond(200, result)
            except ValueError as error:
                self.respond(400, {"error": str(error)})
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
            return
        if self.path != "/api/training":
            self.respond(404, {"error": "Rota não encontrada."})
            return
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.respond(403, {"error": "Origem não permitida."})
            return
        try:
            body = self._read_json()
            horizon = body.get("horizon", 12)
            if type(horizon) is not int or horizon not in (12, 24, 36):
                raise ValueError("Horizonte inválido.")
            with TRAINING_LOCK:
                if TRAINING_JOB.get("status") == "running":
                    self.respond(409, dict(TRAINING_JOB))
                    return
                TRAINING_JOB.clear()
                TRAINING_JOB.update({
                    "status": "queued",
                    "step": "queued",
                    "message": "Treinamento enfileirado.",
                    "horizon": horizon,
                })
            thread = threading.Thread(target=_run_training_job, args=(horizon,), daemon=True)
            thread.start()
            self.respond(202, _training_snapshot())
        except (ValueError, UnicodeError) as error:
            self.respond(400, {"error": str(error)})

    def do_PUT(self):
        if self.path != "/api/favorites":
            self.respond(404, {"error": "Rota não encontrada."})
            return
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + self.headers.get("Host", ""):
            self.respond(403, {"error": "Origem não permitida."})
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
    server = ThreadingHTTPServer((settings.http_host, settings.http_port), RequestHandler)
    print(f"Midas disponível em http://localhost:{settings.http_port}", flush=True)
    server.serve_forever()

def _get_portfolio_list():
    """Retorna a lista de ativos na carteira."""
    if not PORTFOLIO_FILE.exists():
        return {"tickers": []}
    tickers = []
    for line in PORTFOLIO_FILE.read_text(encoding="utf-8").splitlines():
        content = line.split("#", 1)[0].strip()
        if content:
            tickers.append(content.strip())
    return {"tickers": tickers}

def _add_to_portfolio(ticker):
    """Adiciona um ativo à carteira."""
    tickers = _get_portfolio_list()["tickers"]
    if ticker in tickers:
        return {"message": f"{ticker} já está na carteira.", "tickers": tickers}
    
    tickers.append(ticker)
    _save_portfolio(tickers)
    return {"message": f"{ticker} adicionado à carteira.", "tickers": tickers}

def _remove_from_portfolio(ticker):
    """Remove um ativo da carteira."""
    tickers = _get_portfolio_list()["tickers"]
    if ticker not in tickers:
        return {"message": f"{ticker} não está na carteira.", "tickers": tickers}
    
    tickers.remove(ticker)
    _save_portfolio(tickers)
    return {"message": f"{ticker} removido da carteira.", "tickers": tickers}

def _save_portfolio(tickers):
    """Salva a lista de ativos no arquivo."""
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    content = "# Minha Carteira de Ações\n"
    content += "# Adicione ativos pela interface ou edite este arquivo\n"
    content += "# Um ticker por linha\n"
    for ticker in tickers:
        content += ticker + "\n"
    PORTFOLIO_FILE.write_text(content, encoding="utf-8")
