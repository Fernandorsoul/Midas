import unittest

from midas_core.domain.screener import (
    DISCLAIMER,
    build_score,
    explain,
    score_data_quality,
    score_drawdown,
    score_momentum,
    score_volatility,
    screen_assets,
)


class CriterionTests(unittest.TestCase):
    def test_momentum_positive_scores_higher(self):
        low = score_momentum(-0.5)
        high = score_momentum(0.5)
        self.assertGreater(high.normalized, low.normalized)

    def test_drawdown_shallow_better(self):
        deep = score_drawdown(-0.40)
        mild = score_drawdown(-0.05)
        self.assertGreater(mild.normalized, deep.normalized)

    def test_volatility_prefers_moderate(self):
        moderate = score_volatility(0.15)
        extreme = score_volatility(0.60)
        self.assertGreater(moderate.normalized, extreme.normalized)

    def test_data_quality_official_and_fresh_best(self):
        best = score_data_quality("yahoo.finance", "2026-10-07", False)
        stale = score_data_quality("yahoo.finance", "2026-01-01", True)
        self.assertGreater(best.normalized, stale.normalized)


class BuildScoreTests(unittest.TestCase):
    def test_score_between_zero_and_one(self):
        score, factors = build_score({
            "momentum_12m": 0.2,
            "drawdown": -0.1,
            "volatility": 0.15,
            "volume": 1_000_000,
            "source": "yahoo.finance",
            "price_date": "2026-10-07",
            "stale": False,
        })
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)
        self.assertEqual(len(factors), 5)

    def test_explanation_has_drivers_and_disclaimer(self):
        score, factors = build_score({"momentum_12m": 0.1})
        explanation = explain(factors)
        self.assertTrue(explanation["top_drivers"])
        self.assertIn("recomendação", explanation["disclaimer"].lower())
        self.assertEqual(explanation["disclaimer"], DISCLAIMER)

    def test_missing_data_scores_lower(self):
        empty, _ = build_score({})
        full, _ = build_score({
            "momentum_12m": 0.2,
            "drawdown": -0.05,
            "volatility": 0.12,
            "volume": 2_000_000,
            "source": "yahoo.finance",
            "price_date": "2026-10-07",
            "stale": False,
        })
        self.assertLess(empty, full)


class ScreenAssetsTests(unittest.TestCase):
    def assets(self):
        return [
            {"ticker": "GOOD3", "name": "Good", "category": "stock", "sector": "Tech",
             "price": 10.0, "price_date": "2026-10-07", "source": "yahoo.finance",
             "momentum_12m": 0.4, "drawdown": -0.05, "volatility": 0.12, "volume": 5_000_000, "stale": False},
            {"ticker": "BAD3", "name": "Bad", "category": "stock", "sector": "Tech",
             "price": 3.0, "price_date": "2026-01-01", "source": "enriched",
             "momentum_12m": -0.5, "drawdown": -0.6, "volatility": 0.8, "volume": 1_000, "stale": True},
            {"ticker": "FII1", "name": "Fundo", "category": "fii", "sector": "Real Estate",
             "price": 90.0, "price_date": "2026-10-07", "source": "yahoo.finance",
             "momentum_12m": 0.1, "drawdown": -0.1, "volatility": 0.1, "volume": 800_000, "stale": False},
        ]

    def test_orders_by_score(self):
        result = screen_assets(self.assets())
        self.assertEqual(result["results"][0]["ticker"], "GOOD3")
        self.assertGreaterEqual(result["results"][0]["score"], result["results"][-1]["score"])
        self.assertIn("disclaimer", result)

    def test_filters_by_category(self):
        result = screen_assets(self.assets(), category="fii")
        self.assertEqual([r["ticker"] for r in result["results"]], ["FII1"])

    def test_filters_by_min_volume(self):
        result = screen_assets(self.assets(), min_volume=500_000)
        tickers = {r["ticker"] for r in result["results"]}
        self.assertNotIn("BAD3", tickers)
        self.assertIn("GOOD3", tickers)

    def test_query_filter(self):
        result = screen_assets(self.assets(), query="good")
        self.assertEqual(len(result["results"]), 1)

    def test_limit(self):
        result = screen_assets(self.assets(), limit=1)
        self.assertEqual(len(result["results"]), 1)

    def test_every_result_explains_criteria(self):
        result = screen_assets(self.assets())
        for item in result["results"]:
            criteria = item["explanation"]["criteria"]
            self.assertGreaterEqual(len(criteria), 3)
            self.assertTrue(all("note" in c and "weight" in c for c in criteria))


if __name__ == "__main__":
    unittest.main()
