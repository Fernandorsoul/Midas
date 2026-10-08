import io
import json
import unittest
from http.server import HTTPServer
from threading import Thread
from unittest.mock import patch

from midas_core.interfaces.http import RequestHandler


class HTTPTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), RequestHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def request(self, method, path, body=None, headers=None):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        extra = {"Content-Type": "application/json"} if body else {}
        if headers:
            extra.update(headers)
        payload = json.dumps(body).encode() if body else None
        conn.request(method, path, body=payload, headers=extra)
        response = conn.getresponse()
        data = response.read().decode()
        conn.close()
        return response.status, json.loads(data) if data else None


class TrainingStatusTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.latest_job")
    def test_returns_idle_status(self, mock_latest):
        mock_latest.return_value = {"job": None}
        status, body = self.request("GET", "/api/training/status")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "idle")

    @patch("midas_core.interfaces.http.latest_job")
    def test_returns_persisted_training_job(self, mock_latest):
        mock_latest.return_value = {"job": {"id": 1, "status": "running", "step": "dataset", "message": "ok"}}
        status, body = self.request("GET", "/api/training/status")
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "running")
        self.assertEqual(body["id"], 1)


class AnalysisEndpointTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.build_report")
    def test_returns_report_for_valid_horizon(self, mock_report):
        mock_report.return_value = {"assets": [], "horizon": 12}
        status, body = self.request("GET", "/api/analysis?horizon=12")
        self.assertEqual(status, 200)
        mock_report.assert_called_once_with(12)

    @patch("midas_core.interfaces.http.build_report")
    def test_defaults_to_12_when_no_horizon(self, mock_report):
        mock_report.return_value = {"assets": [], "horizon": 12}
        status, body = self.request("GET", "/api/analysis")
        self.assertEqual(status, 200)
        mock_report.assert_called_once_with(12)

    @patch("midas_core.interfaces.http.build_report")
    def test_returns_400_for_invalid_horizon(self, mock_report):
        mock_report.side_effect = ValueError("Horizonte deve ser 12, 24 ou 36 meses.")
        status, body = self.request("GET", "/api/analysis?horizon=99")
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    @patch("midas_core.interfaces.http.build_report")
    def test_returns_503_on_database_error(self, mock_report):
        import psycopg
        mock_report.side_effect = psycopg.Error("connection failed")
        status, body = self.request("GET", "/api/analysis?horizon=12")
        self.assertEqual(status, 503)
        self.assertIn("error", body)

    def test_returns_404_for_unknown_api_route(self):
        status, body = self.request("GET", "/api/unknown")
        self.assertEqual(status, 404)
        self.assertIn("error", body)


class TrainingEndpointTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.PostgresRepository")
    @patch("midas_core.interfaces.http.enqueue_job")
    def test_starts_training_and_returns_202(self, mock_enqueue, mock_repository):
        mock_repository.return_value.portfolio_tickers.return_value = []
        mock_enqueue.return_value = {
            "job": {"id": 1, "status": "queued", "step": "queued", "horizon": 12, "message": "Job enfileirado."},
            "message": "Job enfileirado.",
        }
        status, body = self.request("POST", "/api/training", {"horizon": 12})
        self.assertEqual(status, 202)
        self.assertEqual(body["status"], "queued")
        self.assertEqual(body["horizon"], 12)

    @patch("midas_core.interfaces.http.enqueue_job")
    def test_returns_400_for_invalid_horizon(self, mock_enqueue):
        mock_enqueue.side_effect = ValueError("Horizonte inválido.")
        status, body = self.request("POST", "/api/training", {"horizon": 99})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    @patch("midas_core.interfaces.http.enqueue_job")
    def test_returns_400_for_string_horizon(self, mock_enqueue):
        mock_enqueue.side_effect = ValueError("Horizonte inválido.")
        status, body = self.request("POST", "/api/training", {"horizon": "twelve"})
        self.assertEqual(status, 400)

    @patch("midas_core.interfaces.http.enqueue_job")
    def test_returns_409_when_already_running(self, mock_enqueue):
        mock_enqueue.side_effect = ValueError("Já existe um treinamento na fila ou em execução.")
        status, body = self.request("POST", "/api/training", {"horizon": 12})
        self.assertEqual(status, 409)

    def test_returns_404_for_unknown_post_route(self):
        status, body = self.request("POST", "/api/unknown", {})
        self.assertEqual(status, 404)

    def test_returns_400_for_non_json_content_type(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/training", body=b"not json", headers={"Content-Type": "text/plain"})
        response = conn.getresponse()
        self.assertEqual(response.status, 400)
        conn.close()

    def test_returns_400_for_empty_body(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/training", body=b"", headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        self.assertEqual(response.status, 400)
        conn.close()


class PortfolioEndpointTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.PostgresRepository")
    def test_lists_persisted_positions(self, mock_repository):
        mock_repository.return_value.portfolio_assets.return_value = [
            {"ticker": "PETR4", "quantity": 3},
            {"ticker": "VALE3", "quantity": 1.5},
        ]
        status, body = self.request("GET", "/api/portfolio/list")
        self.assertEqual(status, 200)
        self.assertEqual(body["tickers"], ["PETR4", "VALE3"])
        self.assertEqual(body["portfolio"], {"PETR4": 3.0, "VALE3": 1.5})

    @patch("midas_core.interfaces.http.enqueue_job")
    def test_add_enqueues_import_job(self, mock_enqueue):
        mock_enqueue.return_value = {
            "job": {"id": 7, "job_type": "import", "status": "queued", "ticker": "PETR4", "message": "Job enfileirado."},
            "message": "Job enfileirado.",
        }
        status, body = self.request("POST", "/api/portfolio/add", {"ticker": "petr4", "quantity": 10})
        self.assertEqual(status, 202)
        self.assertEqual(body["job"]["job_type"], "import")
        mock_enqueue.assert_called_once()
        args, kwargs = mock_enqueue.call_args
        self.assertEqual(args[0], "import")
        self.assertEqual(args[1]["ticker"], "PETR4")
        self.assertEqual(args[1]["quantity"], 10)

    @patch("midas_core.interfaces.http.enqueue_job")
    def test_add_returns_400_on_invalid_ticker(self, mock_enqueue):
        mock_enqueue.side_effect = ValueError("Ticker inválido.")
        status, body = self.request("POST", "/api/portfolio/add", {"ticker": "PETR4", "quantity": 10})
        self.assertEqual(status, 400)
        self.assertIn("error", body)

    @patch("midas_core.interfaces.http.PostgresRepository")
    def test_removes_persisted_position(self, mock_repository):
        repository = mock_repository.return_value
        repository.remove_portfolio_asset.return_value = True
        repository.portfolio_assets.return_value = []
        status, body = self.request("POST", "/api/portfolio/remove", {"ticker": "PETR4"})
        self.assertEqual(status, 200)
        repository.remove_portfolio_asset.assert_called_once_with("PETR4")
        self.assertEqual(body["tickers"], [])
        self.assertIn("removido", body["message"])

    @patch("midas_core.interfaces.http.PostgresRepository")
    @patch("midas_core.infrastructure.yahoo.fetch_dividends")
    def test_dividends_uses_persisted_quantities(self, mock_dividends, mock_repository):
        mock_repository.return_value.portfolio_assets.return_value = [{"ticker": "PETR4", "quantity": 10}]
        mock_dividends.return_value = {"annual_dividend": 2.5, "dividend_yield": 0.1, "price": 25}
        status, body = self.request("GET", "/api/portfolio/dividends")
        self.assertEqual(status, 200)
        self.assertEqual(body["dividends"]["PETR4"]["quantity"], 10.0)
        self.assertEqual(body["dividends"]["PETR4"]["total_dividends"], 25.0)

    @patch("midas_core.interfaces.http.PostgresRepository")
    @patch("midas_core.interfaces.http.build_portfolio_report")
    def test_report_uses_persisted_tickers(self, mock_report, mock_repository):
        mock_repository.return_value.portfolio_tickers.return_value = ["PETR4"]
        mock_report.return_value = {"portfolio": [], "horizon": 6}
        status, body = self.request("GET", "/api/portfolio?horizon=6")
        self.assertEqual(status, 200)
        self.assertEqual(body["horizon"], 6)
        mock_report.assert_called_once_with(6, ["PETR4"])


class PortfolioOperationsEndpointTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.list_operations")
    def test_lists_operations(self, mock_list):
        mock_list.return_value = {"operations": [{"id": 1, "operation_type": "buy"}]}
        status, body = self.request("GET", "/api/portfolio/operations")
        self.assertEqual(status, 200)
        self.assertEqual(body["operations"][0]["operation_type"], "buy")

    @patch("midas_core.interfaces.http.position_summary")
    def test_returns_position_summary(self, mock_summary):
        mock_summary.return_value = {
            "positions": {"PETR4": {"quantity": 10, "realized_pnl": 0, "unrealized_pnl": 5}},
            "totals": {"total_pnl": 5},
        }
        status, body = self.request("GET", "/api/portfolio/positions?ticker=PETR4")
        self.assertEqual(status, 200)
        self.assertIn("PETR4", body["positions"])
        mock_summary.assert_called_once()

    @patch("midas_core.interfaces.http.record_operation")
    def test_creates_operation(self, mock_record):
        mock_record.return_value = {"operation": {"id": 1, "operation_type": "buy"}, "message": "ok"}
        status, body = self.request("POST", "/api/portfolio/operations", {
            "ticker": "PETR4",
            "operation_type": "buy",
            "occurred_on": "2025-01-15",
            "quantity": 10,
            "unit_price": 25.5,
        })
        self.assertEqual(status, 201)
        self.assertEqual(body["operation"]["operation_type"], "buy")

    @patch("midas_core.interfaces.http.record_operation")
    def test_create_rejects_sell_above_position(self, mock_record):
        mock_record.side_effect = ValueError("Venda excede a posição disponível.")
        status, body = self.request("POST", "/api/portfolio/operations", {
            "ticker": "PETR4",
            "operation_type": "sell",
            "occurred_on": "2025-01-15",
            "quantity": 10,
            "unit_price": 25.5,
        })
        self.assertEqual(status, 400)
        self.assertIn("excede", body["error"])

    @patch("midas_core.interfaces.http.edit_operation")
    def test_edits_operation(self, mock_edit):
        mock_edit.return_value = {"operation": {"id": 1, "operation_type": "buy"}, "message": "ok"}
        status, body = self.request("PUT", "/api/portfolio/operations", {
            "id": 1,
            "ticker": "PETR4",
            "operation_type": "buy",
            "occurred_on": "2025-01-15",
            "quantity": 5,
            "unit_price": 25.5,
        })
        self.assertEqual(status, 200)
        self.assertEqual(body["operation"]["id"], 1)

    def test_edit_requires_operation_id(self):
        status, body = self.request("PUT", "/api/portfolio/operations", {
            "ticker": "PETR4",
            "operation_type": "buy",
            "occurred_on": "2025-01-15",
            "quantity": 5,
        })
        self.assertEqual(status, 400)
        self.assertIn("id", body["error"])

    @patch("midas_core.interfaces.http.delete_operation")
    def test_deletes_operation(self, mock_delete):
        mock_delete.return_value = {"message": "excluída", "id": 3}
        status, body = self.request("POST", "/api/portfolio/operations/delete", {"id": 3})
        self.assertEqual(status, 200)
        self.assertEqual(body["id"], 3)

    def test_delete_requires_integer_id(self):
        status, body = self.request("POST", "/api/portfolio/operations/delete", {"id": "3"})
        self.assertEqual(status, 400)

    def test_operations_reject_foreign_origin(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/portfolio/operations",
                     body=json.dumps({"operation_type": "buy"}).encode(),
                     headers={"Content-Type": "application/json", "Origin": "http://evil.com"})
        response = conn.getresponse()
        self.assertEqual(response.status, 403)
        conn.close()


class JobsEndpointTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.list_jobs")
    def test_lists_jobs(self, mock_list):
        mock_list.return_value = {"jobs": [{"id": 1, "job_type": "training", "status": "queued"}]}
        status, body = self.request("GET", "/api/jobs")
        self.assertEqual(status, 200)
        self.assertEqual(body["jobs"][0]["id"], 1)

    @patch("midas_core.interfaces.http.get_job")
    def test_gets_job_by_id(self, mock_get):
        mock_get.return_value = {"job": {"id": 2, "job_type": "import", "status": "running"}}
        status, body = self.request("GET", "/api/jobs?job_id=2")
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["status"], "running")

    @patch("midas_core.interfaces.http.enqueue_job")
    def test_creates_import_job(self, mock_enqueue):
        mock_enqueue.return_value = {"job": {"id": 3, "job_type": "import"}, "message": "ok"}
        status, body = self.request("POST", "/api/jobs", {
            "type": "import",
            "payload": {"ticker": "PETR4", "quantity": 10},
        })
        self.assertEqual(status, 202)
        self.assertEqual(body["job"]["job_type"], "import")

    @patch("midas_core.interfaces.http.cancel_job")
    def test_cancels_job(self, mock_cancel):
        mock_cancel.return_value = {"job": {"id": 4, "status": "cancelled"}, "message": "ok"}
        status, body = self.request("POST", "/api/jobs/cancel", {"id": 4})
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["status"], "cancelled")

    @patch("midas_core.interfaces.http.retry_job")
    def test_retries_job(self, mock_retry):
        mock_retry.return_value = {"job": {"id": 5, "status": "queued"}, "message": "ok"}
        status, body = self.request("POST", "/api/jobs/retry", {"id": 5})
        self.assertEqual(status, 202)

    def test_cancel_requires_integer_id(self):
        status, body = self.request("POST", "/api/jobs/cancel", {"id": "x"})
        self.assertEqual(status, 400)


class FavoritesEndpointTests(HTTPTestBase):
    @patch("midas_core.interfaces.http.set_favorite")
    def test_saves_favorite(self, mock_fav):
        status, body = self.request("PUT", "/api/favorites", {"asset_id": 1, "saved": True})
        self.assertEqual(status, 200)
        self.assertEqual(body["saved"], True)
        mock_fav.assert_called_once_with(1, True)

    @patch("midas_core.interfaces.http.set_favorite")
    def test_removes_favorite(self, mock_fav):
        status, body = self.request("PUT", "/api/favorites", {"asset_id": 2, "saved": False})
        self.assertEqual(status, 200)
        self.assertEqual(body["saved"], False)
        mock_fav.assert_called_once_with(2, False)

    def test_returns_400_for_missing_asset_id(self):
        status, body = self.request("PUT", "/api/favorites", {"saved": True})
        self.assertEqual(status, 400)

    def test_returns_400_for_string_asset_id(self):
        status, body = self.request("PUT", "/api/favorites", {"asset_id": "one", "saved": True})
        self.assertEqual(status, 400)

    def test_returns_400_for_non_bool_saved(self):
        status, body = self.request("PUT", "/api/favorites", {"asset_id": 1, "saved": "yes"})
        self.assertEqual(status, 400)

    def test_returns_404_for_unknown_put_route(self):
        status, body = self.request("PUT", "/api/unknown", {})
        self.assertEqual(status, 404)


class CORSTests(HTTPTestBase):
    def test_post_rejects_foreign_origin(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("POST", "/api/training",
                     body=json.dumps({"horizon": 12}).encode(),
                     headers={"Content-Type": "application/json", "Origin": "http://evil.com"})
        response = conn.getresponse()
        self.assertEqual(response.status, 403)
        conn.close()

    def test_put_rejects_foreign_origin(self):
        import http.client
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request("PUT", "/api/favorites",
                     body=json.dumps({"asset_id": 1, "saved": True}).encode(),
                     headers={"Content-Type": "application/json", "Origin": "http://evil.com"})
        response = conn.getresponse()
        self.assertEqual(response.status, 403)
        conn.close()


class ResponseFormatTests(HTTPTestBase):
    def test_json_content_type(self):
        status, body = self.request("GET", "/api/training/status")
        self.assertEqual(status, 200)

    @patch("midas_core.interfaces.http.build_report")
    def test_error_response_is_json(self, mock_report):
        mock_report.side_effect = ValueError("test error")
        status, body = self.request("GET", "/api/analysis?horizon=12")
        self.assertEqual(status, 400)
        self.assertIsInstance(body, dict)
        self.assertIn("error", body)


if __name__ == "__main__":
    unittest.main()
