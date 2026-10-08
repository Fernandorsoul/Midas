import unittest
from datetime import date
from decimal import Decimal

from midas_core.application.wealth_dashboard import _cash_flows, _twr_from_points, wealth_dashboard
from midas_core.domain.wealth import (
    allocation,
    money_weighted_return,
    rebase_series,
    subperiod_return,
    time_weighted_return,
    wealth_summary,
)


class TWRTests(unittest.TestCase):
    def test_subperiod_removes_deposit_effect(self):
        # 100 → 150 com aporte de 40: retorno de estratégia = 10%
        r = subperiod_return(Decimal("100"), Decimal("150"), Decimal("40"))
        self.assertEqual(r, Decimal("0.1"))

    def test_twr_compounds_without_cash_flow_distortion(self):
        twr = time_weighted_return([Decimal("0.10"), Decimal("0.10")])
        self.assertEqual(twr, Decimal("0.21"))

    def test_twr_from_equity_points(self):
        points = [
            {"date": date(2025, 1, 1), "market_value": Decimal("100"), "flow_sign": Decimal("0")},
            {"date": date(2025, 2, 1), "market_value": Decimal("150"), "flow_sign": Decimal("40")},
            {"date": date(2025, 3, 1), "market_value": Decimal("165"), "flow_sign": Decimal("0")},
        ]
        twr = _twr_from_points(points)
        self.assertAlmostEqual(float(twr), 0.21, places=6)


class XIRRTests(unittest.TestCase):
    def test_xirr_positive_when_portfolio_grows(self):
        flows = [
            (date(2025, 1, 1), Decimal("1000")),  # aporte
        ]
        rate = money_weighted_return(flows, Decimal("1100"))
        self.assertIsNotNone(rate)
        self.assertGreater(float(rate), 0)

    def test_xirr_none_without_flows(self):
        self.assertIsNone(money_weighted_return([], Decimal("100")))


class AllocationTests(unittest.TestCase):
    def test_normalizes_weights(self):
        result = allocation({"PETR4": 30, "VALE3": 70})
        self.assertAlmostEqual(result["PETR4"], 0.3)
        self.assertAlmostEqual(result["VALE3"], 0.7)

    def test_empty_allocation(self):
        self.assertEqual(allocation({}), {})


class RebaseTests(unittest.TestCase):
    def test_rebases_to_100(self):
        points = [(date(2025, 1, 1), 50), (date(2025, 2, 1), 75)]
        series = rebase_series(points)
        self.assertEqual(series[0]["value"], 100.0)
        self.assertEqual(series[1]["value"], 150.0)


class WealthSummaryTests(unittest.TestCase):
    def test_net_contribution_and_pnl(self):
        summary = wealth_summary(
            deposits=Decimal("1000"),
            withdrawals=Decimal("200"),
            market_value=Decimal("900"),
            realized_pnl=Decimal("50"),
            unrealized_pnl=Decimal("25"),
            income=Decimal("10"),
            expenses=Decimal("5"),
        )
        self.assertEqual(summary["net_contribution"], Decimal("800"))
        self.assertEqual(summary["total_pnl"], Decimal("80"))


class FakeRepository:
    def __init__(self, operations=None, prices=None):
        self.operations = operations or []
        self.prices = prices or {}

    def list_portfolio_operations(self, name="Minha Carteira", ticker=None):
        rows = [op for op in self.operations if ticker is None or op["ticker"] == ticker]
        return sorted(rows, key=lambda op: (op["occurred_on"], op["id"]))

    def get_portfolio_operation(self, operation_id, name="Minha Carteira"):
        for op in self.operations:
            if op["id"] == operation_id:
                return op
        return None

    def latest_price(self, ticker, source=None):
        return self.prices.get(ticker)

    def assets_with_prices(self):
        return []


def op(id, kind, day, **fields):
    row = {
        "id": id,
        "ticker": fields.get("ticker"),
        "operation_type": kind,
        "occurred_on": date.fromisoformat(day),
        "quantity": Decimal(str(fields.get("quantity", 0))),
        "unit_price": Decimal(str(fields.get("unit_price", 0))),
        "amount": Decimal(str(fields.get("amount", 0))),
        "fees": Decimal(str(fields.get("fees", 0))),
        "taxes": Decimal(str(fields.get("taxes", 0))),
        "currency": "BRL",
        "notes": None,
        "created_at": None,
        "updated_at": None,
    }
    return row


class DashboardTests(unittest.TestCase):
    def test_dashboard_separates_twr_and_xirr(self):
        repository = FakeRepository(
            operations=[
                op(1, "deposit", "2025-01-01", amount=1000),
                op(2, "buy", "2025-01-02", ticker="PETR4", quantity=100, unit_price=10),
                op(3, "sell", "2025-06-01", ticker="PETR4", quantity=40, unit_price=12),
            ],
            prices={"PETR4": {"close": Decimal("11"), "adjusted_close": Decimal("11"),
                              "price_date": date(2026, 1, 1), "source": "yahoo.finance", "ingested_at": None}},
        )
        result = wealth_dashboard(
            repository=repository,
            cdi_fetcher=lambda start, end: [(start, 100.0), (end, 105.0)],
            ibov_fetcher=lambda start, end: [(start, 100.0), (end, 110.0)],
        )
        self.assertIn("wealth", result)
        self.assertIn("returns", result)
        self.assertIn("twr", result["returns"])
        self.assertIn("xirr", result["returns"])
        self.assertTrue(result["returns"]["has_cash_flow"])
        self.assertIn("cdi", result["benchmarks"])
        self.assertIn("ibovespa", result["benchmarks"])
        self.assertEqual(result["benchmarks"]["cdi"]["source"], "Banco Central do Brasil (SGS 12)")
        self.assertTrue(result["benchmarks"]["period"]["start"])
        self.assertTrue(result["benchmarks"]["updated_at"])
        self.assertIn("allocation", result)
        self.assertIn("reconciliation", result)

    def test_deposits_do_not_count_as_strategy_return(self):
        repository = FakeRepository(
            operations=[
                op(1, "deposit", "2025-01-01", amount=5000),
                op(2, "buy", "2025-01-02", ticker="PETR4", quantity=100, unit_price=50),
            ],
            prices={"PETR4": {"close": Decimal("50"), "adjusted_close": Decimal("50"),
                              "price_date": date(2026, 1, 1), "source": "yahoo.finance", "ingested_at": None}},
        )
        result = wealth_dashboard(
            repository=repository,
            cdi_fetcher=lambda s, e: [],
            ibov_fetcher=lambda s, e: [],
        )
        # Sem variação de preço, TWR deve ser ~0 (não capturar o aporte como retorno)
        self.assertAlmostEqual(result["returns"]["twr"] or 0.0, 0.0, places=6)
        self.assertEqual(result["wealth"]["deposits"], 5000.0)


if __name__ == "__main__":
    unittest.main()
