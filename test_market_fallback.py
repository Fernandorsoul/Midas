import unittest
from datetime import date
from unittest.mock import patch

from midas_core.application.market_fallback import fetch_price_history
from midas_core.domain.entities import ImportedStock, PricePoint
from midas_core.domain.market_quality import (
    ERROR_AUTH,
    ERROR_NOT_FOUND,
    ERROR_RATE_LIMIT,
    ERROR_TIMEOUT,
    classify_fetch_error,
    collection_outcome,
    fallback_report,
    next_price_source,
    should_try_fallback,
)


class ClassifyErrorTests(unittest.TestCase):
    def test_rate_limit(self):
        self.assertEqual(classify_fetch_error("HTTP 429 rate limit"), ERROR_RATE_LIMIT)
        self.assertEqual(classify_fetch_error("quota esgotada"), ERROR_RATE_LIMIT)

    def test_timeout(self):
        self.assertEqual(classify_fetch_error("Não foi possível conectar à brapi.dev."), ERROR_TIMEOUT)
        self.assertEqual(classify_fetch_error("timed out"), ERROR_TIMEOUT)

    def test_auth(self):
        self.assertEqual(classify_fetch_error("Configure BRAPI_TOKEN"), ERROR_AUTH)
        self.assertEqual(classify_fetch_error("A API recusou o acesso."), ERROR_AUTH)

    def test_not_found(self):
        self.assertEqual(classify_fetch_error("Nenhum dado encontrado"), ERROR_NOT_FOUND)

    def test_fallback_rules(self):
        self.assertTrue(should_try_fallback(ERROR_TIMEOUT))
        self.assertTrue(should_try_fallback(ERROR_RATE_LIMIT))
        self.assertFalse(should_try_fallback(ERROR_NOT_FOUND))
        self.assertFalse(should_try_fallback(ERROR_AUTH))


class SourceChainTests(unittest.TestCase):
    def test_order_is_yahoo_then_brapi(self):
        self.assertEqual(next_price_source([]), "yahoo.finance")
        self.assertEqual(next_price_source(["yahoo.finance"]), "brapi.dev")
        self.assertIsNone(next_price_source(["yahoo.finance", "brapi.dev"]))

    def test_fallback_report_hides_secrets(self):
        report = fallback_report("PETR4", [
            {"source": "yahoo.finance", "ok": False, "error_kind": ERROR_TIMEOUT,
             "message": "timeout with token abc123"},
            {"source": "brapi.dev", "ok": True, "error_kind": None, "message": ""},
        ])
        self.assertEqual(report["used_source"], "brapi.dev")
        self.assertEqual(report["status"], "succeeded")
        self.assertEqual(len(report["attempts"]), 1)
        self.assertLessEqual(len(report["attempts"][0]["message"]), 200)


def _stock(ticker="PETR4"):
    return ImportedStock(
        ticker=ticker,
        name=ticker,
        prices=(PricePoint(price_date=date(2026, 1, 2), close=10.0, adjusted_close=9.5, volume=1.0),),
    )


class FallbackOrchestrationTests(unittest.TestCase):
    def test_yahoo_success_skips_brapi(self):
        calls = []

        def yahoo(ticker, period):
            calls.append("yahoo")
            return _stock(ticker)

        def brapi(ticker, period):
            calls.append("brapi")
            return _stock(ticker)

        result = fetch_price_history("PETR4", "5y", fetchers={
            "yahoo.finance": yahoo,
            "brapi.dev": brapi,
        })
        self.assertEqual(result["source"], "yahoo.finance")
        self.assertEqual(calls, ["yahoo"])
        self.assertEqual(result["fallback"]["status"], "succeeded")

    def test_timeout_falls_back_to_brapi(self):
        def yahoo(ticker, period):
            raise RuntimeError("Não foi possível conectar à fonte.")

        def brapi(ticker, period):
            return _stock(ticker)

        result = fetch_price_history("PETR4", "5y", fetchers={
            "yahoo.finance": yahoo,
            "brapi.dev": brapi,
        })
        self.assertEqual(result["source"], "brapi.dev")
        self.assertEqual(result["fallback"]["used_source"], "brapi.dev")
        self.assertEqual(result["fallback"]["attempts"][0]["kind"], ERROR_TIMEOUT)

    def test_rate_limit_429_falls_back(self):
        def yahoo(ticker, period):
            raise RuntimeError("HTTP 429 rate limit")

        def brapi(ticker, period):
            return _stock(ticker)

        result = fetch_price_history("PETR4", "5y", fetchers={
            "yahoo.finance": yahoo,
            "brapi.dev": brapi,
        })
        self.assertEqual(result["source"], "brapi.dev")

    def test_not_found_does_not_fall_back(self):
        calls = []

        def yahoo(ticker, period):
            calls.append("yahoo")
            raise RuntimeError("Nenhum dado encontrado para XYZ")

        def brapi(ticker, period):
            calls.append("brapi")
            return _stock(ticker)

        with self.assertRaises(RuntimeError):
            fetch_price_history("XYZ", "5y", fetchers={
                "yahoo.finance": yahoo,
                "brapi.dev": brapi,
            })
        self.assertEqual(calls, ["yahoo"])

    def test_all_rate_limits_raise_safe_message(self):
        def rate_limited(ticker, period):
            raise RuntimeError("HTTP 429")

        with self.assertRaisesRegex(RuntimeError, "Limite de requisições") as ctx:
            fetch_price_history("PETR4", "5y", fetchers={
                "yahoo.finance": rate_limited,
                "brapi.dev": rate_limited,
            })
        self.assertNotIn("Bearer", str(ctx.exception))
        self.assertNotIn("token", str(ctx.exception).lower())

    def test_all_failures_raise_safe_message(self):
        def boom(ticker, period):
            raise RuntimeError("falha interna com segredo xyz")

        with self.assertRaisesRegex(RuntimeError, "nenhuma fonte oficial"):
            fetch_price_history("PETR4", "5y", fetchers={
                "yahoo.finance": boom,
                "brapi.dev": boom,
            })


class CollectionOutcomeTests(unittest.TestCase):
    def test_partial_still_partial(self):
        self.assertEqual(collection_outcome(1, 1)["status"], "partial")


if __name__ == "__main__":
    unittest.main()
