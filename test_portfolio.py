import unittest
from datetime import date
from decimal import Decimal

from midas_core.domain.portfolio import Operation, calculate_position


def operation(kind, day, **values):
    return Operation(kind, date.fromisoformat(day), **{key: Decimal(str(value)) for key, value in values.items()})


class PortfolioCalculationTests(unittest.TestCase):
    def test_buy_sell_partial_and_market_value(self):
        summary = calculate_position([
            operation("buy", "2025-01-01", quantity=10, unit_price=10, fees=2),
            operation("buy", "2025-02-01", quantity=10, unit_price=14),
            operation("sell", "2025-03-01", quantity=5, unit_price=16, fees=1),
        ], market_price=15)
        self.assertEqual(summary.quantity, Decimal("15"))
        self.assertEqual(summary.cost_basis, Decimal("181.5"))
        self.assertEqual(summary.average_cost, Decimal("12.1"))
        self.assertEqual(summary.realized_pnl, Decimal("18.5"))
        self.assertEqual(summary.unrealized_pnl, Decimal("43.5"))

    def test_rejects_sale_above_available_position(self):
        with self.assertRaisesRegex(ValueError, "excede"):
            calculate_position([operation("sell", "2025-01-01", quantity=1, unit_price=10)])

    def test_separates_income_and_expenses(self):
        summary = calculate_position([
            operation("buy", "2025-01-01", quantity=1, unit_price=100),
            operation("dividend", "2025-02-01", amount=5, taxes=1),
            operation("jcp", "2025-03-01", amount=3),
            operation("fee", "2025-04-01", amount=2),
        ])
        self.assertEqual(summary.income, Decimal("7"))
        self.assertEqual(summary.expenses, Decimal("2"))
        self.assertEqual(summary.realized_pnl, Decimal("0"))
        self.assertEqual(summary.net_cash_flow, Decimal("-95"))

    def test_applies_operations_in_chronological_order(self):
        summary = calculate_position([
            operation("sell", "2025-02-01", quantity=1, unit_price=12),
            operation("buy", "2025-01-01", quantity=1, unit_price=10),
        ])
        self.assertEqual(summary.realized_pnl, Decimal("2"))


if __name__ == "__main__":
    unittest.main()
