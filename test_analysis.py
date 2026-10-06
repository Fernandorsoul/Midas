import unittest
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import numpy as np

from midas_core.application.analysis import (
    MINIMUM_DRAWDOWN,
    MINIMUM_RANK_CORRELATION,
    MINIMUM_RELATIVE_MAE_IMPROVEMENT,
    _is_validated,
    build_report,
    set_favorite,
)


def _make_asset(ticker, prices, favorite=False):
    base = date(2020, 1, 1)
    return {
        "id": 1,
        "ticker": ticker,
        "name": ticker,
        "category": "stock",
        "sector": "Teste",
        "favorite": favorite,
        "prices": [
            {"price_date": date(base.year + (base.month + i - 1) // 12,
                                (base.month + i - 1) % 12 + 1, 1),
             "close": p, "adjusted_close": p, "source": "brapi.dev"}
            for i, p in enumerate(prices)
        ],
    }


def _make_artifact(model_version=5, features=None):
    features = features or ["momentum_6m", "momentum_12m", "volatility", "drawdown", "rsi_14m", "macd_signal", "sma_ratio_12m", "bb_position", "atr_ratio", "pe_ratio", "dividend_yield", "net_margin"]
    return {
        "_id": "run-1",
        "dataset_id": "ds-1",
        "parameters": {
            "model_version": model_version,
            "features": features,
            "residual_quantiles": {"p10": -0.02, "p90": 0.02},
        },
        "mean": [0.0] * len(features),
        "scale": [1.0] * len(features),
        "weights": [0.05] + [0.01] * len(features),
    }


def _make_metrics(mae_improvement=0.05, rank_correlation=0.20):
    return {
        "mae": 0.08,
        "baseline_mae": 0.10,
        "mae_improvement": mae_improvement,
        "rank_correlation": rank_correlation,
        "directional_accuracy": 0.6,
    }


def _make_run(horizon=12):
    return {
        "id": "run-1",
        "dataset_id": "ds-1",
        "metrics": _make_metrics(),
        "created_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
    }


class IsvalidatedTests(unittest.TestCase):
    def test_validated_when_all_conditions_met(self):
        metrics = _make_metrics()
        artifact = _make_artifact()
        self.assertTrue(_is_validated(metrics, artifact))

    def test_not_validated_without_metrics(self):
        self.assertFalse(_is_validated(None, _make_artifact()))

    def test_not_validated_without_artifact(self):
        self.assertFalse(_is_validated(_make_metrics(), None))

    def test_not_validated_with_wrong_model_version(self):
        metrics = _make_metrics()
        artifact = _make_artifact(model_version=2)
        self.assertFalse(_is_validated(metrics, artifact))

    def test_not_validated_with_low_mae_improvement(self):
        metrics = _make_metrics(mae_improvement=0.001)
        artifact = _make_artifact()
        self.assertFalse(_is_validated(metrics, artifact))

    def test_not_validated_with_low_rank_correlation(self):
        metrics = _make_metrics(rank_correlation=0.01)
        artifact = _make_artifact()
        self.assertFalse(_is_validated(metrics, artifact))


class BuildReportTests(unittest.TestCase):
    def test_rejects_invalid_horizon(self):
        with self.assertRaises(ValueError):
            build_report(1)
        with self.assertRaises(ValueError):
            build_report(48)

    def test_returns_empty_assets_when_no_data(self):
        pg = MagicMock()
        pg.assets_with_prices.return_value = []
        pg.model_runs.return_value = []
        mongo = MagicMock()
        mongo.dataset_count.return_value = 0
        result = build_report(12, mongo, pg)
        self.assertEqual(result["assets"], [])
        self.assertEqual(result["horizon"], 12)
        self.assertIsNone(result["metrics"])
        self.assertFalse(result["model_validated"])
        self.assertIsNone(result["method"])

    def test_assets_without_model_have_no_opportunity(self):
        prices = [100.0 + i for i in range(20)]
        pg = MagicMock()
        pg.assets_with_prices.return_value = [_make_asset("PETR4", prices)]
        pg.model_runs.return_value = []
        mongo = MagicMock()
        mongo.dataset_count.return_value = 0
        result = build_report(12, mongo, pg)
        self.assertEqual(len(result["assets"]), 1)
        self.assertIsNone(result["assets"][0]["opportunity"])

    def test_assets_with_validated_model_get_opportunity(self):
        # 24 monthly prices so month_end_series produces >= 13 entries
        prices = [100.0 + i * 0.5 for i in range(24)]
        pg = MagicMock()
        pg.assets_with_prices.return_value = [_make_asset("PETR4", prices)]
        pg.model_runs.return_value = [_make_run()]
        mongo = MagicMock()
        mongo.artifact_for_run.return_value = _make_artifact()
        mongo.dataset_count.return_value = 1
        result = build_report(12, mongo, pg)
        asset = result["assets"][0]
        self.assertIsNotNone(asset["opportunity"])
        self.assertIn("estimate", asset["opportunity"])
        self.assertIn("estimate_low", asset["opportunity"])
        self.assertIn("estimate_high", asset["opportunity"])
        self.assertTrue(result["model_validated"])
        self.assertEqual(result["method"], "temporal-model-selection-v3")

    def test_candidates_sorted_first(self):
        prices = [100.0 + i for i in range(20)]
        pg = MagicMock()
        pg.assets_with_prices.return_value = [
            _make_asset("AAAA4", prices),
            _make_asset("BBBB4", prices),
        ]
        run = _make_run()
        run["metrics"] = _make_metrics()
        pg.model_runs.return_value = [run]
        mongo = MagicMock()
        mongo.artifact_for_run.return_value = _make_artifact()
        mongo.dataset_count.return_value = 1
        result = build_report(12, mongo, pg)
        for asset in result["assets"]:
            if asset["opportunity"] and asset["opportunity"]["candidate"]:
                idx = result["assets"].index(asset)
                self.assertEqual(idx, 0)
                break

    def test_unvalidated_model_sets_opportunity_but_not_candidate(self):
        prices = [100.0 + i * 0.5 for i in range(24)]
        pg = MagicMock()
        pg.assets_with_prices.return_value = [_make_asset("PETR4", prices)]
        run = _make_run()
        run["metrics"] = _make_metrics(mae_improvement=0.001, rank_correlation=0.01)
        pg.model_runs.return_value = [run]
        mongo = MagicMock()
        mongo.artifact_for_run.return_value = _make_artifact()
        mongo.dataset_count.return_value = 1
        result = build_report(12, mongo, pg)
        asset = result["assets"][0]
        self.assertIsNotNone(asset["opportunity"])
        self.assertFalse(asset["opportunity"]["validated"])
        self.assertFalse(asset["opportunity"]["candidate"])
        self.assertFalse(result["model_validated"])

    def test_chart_limited_to_756_prices(self):
        # 1000 monthly prices
        prices = [100.0 + i * 0.5 for i in range(1000)]
        pg = MagicMock()
        pg.assets_with_prices.return_value = [_make_asset("PETR4", prices)]
        pg.model_runs.return_value = []
        mongo = MagicMock()
        mongo.dataset_count.return_value = 0
        result = build_report(12, mongo, pg)
        self.assertLessEqual(len(result["assets"][0]["chart"]), 756)


class SetFavoriteTests(unittest.TestCase):
    def test_delegates_to_repository(self):
        repo = MagicMock()
        set_favorite(42, True, repo)
        repo.set_favorite.assert_called_once_with(42, True)

    def test_delegates_false(self):
        repo = MagicMock()
        set_favorite(7, False, repo)
        repo.set_favorite.assert_called_once_with(7, False)


if __name__ == "__main__":
    unittest.main()