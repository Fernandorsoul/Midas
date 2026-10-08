import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from midas_core.application.market_import_yahoo import import_stocks_yahoo
from midas_core.domain.market_quality import (
    PriceMetadata,
    assert_consistent_series,
    collection_outcome,
    describe_price,
    resolve_price_source,
)
from midas_core.domain.entities import ImportedStock, PricePoint


class SourcePolicyTests(unittest.TestCase):
    def test_prefers_primary_yahoo(self):
        self.assertEqual(resolve_price_source(["brapi.dev", "yahoo.finance"]), "yahoo.finance")

    def test_falls_back_to_brapi(self):
        self.assertEqual(resolve_price_source(["brapi.dev", "enriched"]), "brapi.dev")

    def test_experimental_only_when_no_official(self):
        self.assertEqual(resolve_price_source(["enriched"]), "enriched")
        self.assertIsNone(resolve_price_source([]))

    def test_rejects_mixed_series(self):
        with self.assertRaisesRegex(ValueError, "mistura fontes"):
            assert_consistent_series(["yahoo.finance", "brapi.dev"])

    def test_accepts_single_source_series(self):
        self.assertEqual(assert_consistent_series(["yahoo.finance", "yahoo.finance"]), "yahoo.finance")


class PriceMetadataTests(unittest.TestCase):
    def _meta(self, price_date, **overrides):
        values = {
            "source": "yahoo.finance",
            "price_date": price_date,
            "ingested_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "close": 10.0,
            "adjusted_close": 10.5,
        }
        values.update(overrides)
        return PriceMetadata(**values)

    def test_describes_fresh_price_with_source_and_date(self):
        today = date.today()
        description = describe_price(self._meta(today), as_of=today)
        self.assertEqual(description["source"], "yahoo.finance")
        self.assertEqual(description["quality"], "ok")
        self.assertFalse(description["stale"])
        self.assertEqual(description["age_days"], 0)
        self.assertEqual(description["display_price_field"], "close")
        self.assertEqual(description["training_price_field"], "adjusted_close")

    def test_flags_stale_price(self):
        old = date(2020, 1, 1)
        description = describe_price(self._meta(old), as_of=date(2026, 1, 1))
        self.assertTrue(description["stale"])
        self.assertEqual(description["quality"], "stale")
        self.assertGreater(description["age_days"], 7)

    def test_missing_price_is_incomplete_or_missing(self):
        description = describe_price(None)
        self.assertEqual(description["quality"], "missing")
        self.assertTrue(description["stale"])
        self.assertIsNone(description["source"])

    def test_training_uses_close_when_no_adjusted(self):
        today = date.today()
        description = describe_price(self._meta(today, adjusted_close=None), as_of=today)
        self.assertEqual(description["training_price_field"], "close")


class CollectionOutcomeTests(unittest.TestCase):
    def test_all_failed_is_failed(self):
        self.assertEqual(collection_outcome(0, 2)["status"], "failed")

    def test_partial_is_not_success(self):
        outcome = collection_outcome(2, 1)
        self.assertEqual(outcome["status"], "partial")
        self.assertEqual(outcome["failed"], 1)

    def test_full_success(self):
        self.assertEqual(collection_outcome(3, 0)["status"], "succeeded")


class FakeRepository:
    def __init__(self):
        self.saved = None
        self.source = None

    def save_stocks(self, stocks, source):
        self.saved = stocks
        self.source = source
        return sum(len(stock.prices) for stock in stocks)


def _stock(ticker):
    return ImportedStock(
        ticker=ticker,
        name=ticker,
        prices=(PricePoint(price_date=date(2026, 1, 2), close=10.0, adjusted_close=9.5, volume=100.0),),
    )


class YahooImportOutcomeTests(unittest.TestCase):
    def test_partial_import_reports_partial_collection(self):
        repository = FakeRepository()

        def fake_fetch(ticker, period):
            if ticker == "FAIL":
                from midas_core.infrastructure.yahoo import YahooFinanceError
                raise YahooFinanceError("timeout")
            return _stock(ticker)

        import midas_core.application.market_import_yahoo as module
        original = module.fetch_history
        module.fetch_history = fake_fetch
        try:
            result = import_stocks_yahoo(["PETR4", "FAIL"], repository=repository)
        finally:
            module.fetch_history = original
        self.assertEqual(result["collection"]["status"], "partial")
        self.assertEqual(result["collection"]["imported"], 1)
        self.assertEqual(result["collection"]["failed"], 1)
        self.assertIn("warnings", result)

    def test_total_failure_raises_and_does_not_save(self):
        repository = FakeRepository()

        def fake_fetch(ticker, period):
            from midas_core.infrastructure.yahoo import YahooFinanceError
            raise YahooFinanceError("timeout")

        import midas_core.application.market_import_yahoo as module
        original = module.fetch_history
        module.fetch_history = fake_fetch
        try:
            with self.assertRaises(Exception):
                import_stocks_yahoo(["PETR4"], repository=repository)
        finally:
            module.fetch_history = original
        self.assertIsNone(repository.saved)

    def test_success_reports_succeeded(self):
        repository = FakeRepository()

        def fake_fetch(ticker, period):
            return _stock(ticker)

        import midas_core.application.market_import_yahoo as module
        original = module.fetch_history
        module.fetch_history = fake_fetch
        try:
            result = import_stocks_yahoo(["PETR4", "VALE3"], repository=repository)
        finally:
            module.fetch_history = original
        self.assertEqual(result["collection"]["status"], "succeeded")
        self.assertEqual(result["collection"]["failed"], 0)
        self.assertEqual(repository.source, "yahoo.finance")


class FundamentalsAvailabilityTests(unittest.TestCase):
    def test_fetch_fundamentals_is_defined(self):
        from midas_core.infrastructure import yahoo
        self.assertTrue(callable(getattr(yahoo, "fetch_fundamentals", None)))


if __name__ == "__main__":
    unittest.main()
