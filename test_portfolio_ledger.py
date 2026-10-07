import unittest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from midas_core.application.portfolio_ledger import (
    delete_operation,
    edit_operation,
    list_operations,
    parse_operation_payload,
    position_summary,
    record_operation,
)
from midas_core.domain.portfolio import Operation, calculate_position


NUMERIC_FIELDS = {"quantity", "unit_price", "amount", "fees", "taxes"}


def operation(kind, day, **values):
    fields = {
        key: (Decimal(str(value)) if key in NUMERIC_FIELDS else value)
        for key, value in values.items()
    }
    return Operation(kind, date.fromisoformat(day), **fields)


class DomainTotalPnlTests(unittest.TestCase):
    def test_total_pnl_separates_realized_unrealized_and_income(self):
        summary = calculate_position([
            operation("buy", "2025-01-01", quantity=10, unit_price=10),
            operation("sell", "2025-02-01", quantity=4, unit_price=12),
            operation("dividend", "2025-03-01", amount=5, taxes=1),
            operation("fee", "2025-04-01", amount=2),
        ], market_price=11)
        self.assertEqual(summary.realized_pnl, Decimal("8"))
        self.assertEqual(summary.unrealized_pnl, Decimal("6"))
        self.assertEqual(summary.income, Decimal("4"))
        self.assertEqual(summary.expenses, Decimal("2"))
        self.assertEqual(summary.total_pnl, Decimal("16"))

    def test_rejects_mixed_currency_ledger(self):
        with self.assertRaisesRegex(ValueError, "mesma moeda"):
            calculate_position([
                operation("buy", "2025-01-01", quantity=1, unit_price=10, currency="BRL"),
                operation("buy", "2025-02-01", quantity=1, unit_price=10, currency="USD"),
            ])


class ParsePayloadTests(unittest.TestCase):
    def test_parses_buy_payload(self):
        fields = parse_operation_payload({
            "ticker": "petr4",
            "operation_type": "buy",
            "occurred_on": "2025-01-15",
            "quantity": 10,
            "unit_price": 25.5,
            "fees": 2.5,
        })
        self.assertEqual(fields["ticker"], "PETR4")
        self.assertEqual(fields["operation_type"], "buy")
        self.assertEqual(fields["quantity"], Decimal("10"))
        self.assertEqual(fields["currency"], "BRL")

    def test_rejects_unknown_type(self):
        with self.assertRaisesRegex(ValueError, "Tipo de operação"):
            parse_operation_payload({
                "ticker": "PETR4",
                "operation_type": "transfer",
                "occurred_on": "2025-01-15",
            })

    def test_rejects_trade_without_quantity(self):
        with self.assertRaisesRegex(ValueError, "quantidade"):
            parse_operation_payload({
                "ticker": "PETR4",
                "operation_type": "buy",
                "occurred_on": "2025-01-15",
                "quantity": 0,
            })

    def test_rejects_cashflow_with_ticker(self):
        with self.assertRaisesRegex(ValueError, "ticker"):
            parse_operation_payload({
                "ticker": "PETR4",
                "operation_type": "deposit",
                "occurred_on": "2025-01-15",
                "amount": 100,
            })

    def test_rejects_invalid_date(self):
        with self.assertRaisesRegex(ValueError, "Data"):
            parse_operation_payload({
                "ticker": "PETR4",
                "operation_type": "buy",
                "occurred_on": "15/01/2025",
                "quantity": 1,
            })


class FakeRepository:
    """Repositório em memória para testar o caso de uso sem PostgreSQL."""

    def __init__(self, rows=None, prices=None):
        self.rows = list(rows or [])
        self.prices = prices or {}
        self._next_id = max((row["id"] for row in self.rows), default=0) + 1

    def list_portfolio_operations(self, name="Minha Carteira", ticker=None):
        rows = [row for row in self.rows if ticker is None or row["ticker"] == ticker]
        return sorted(rows, key=lambda row: (row["occurred_on"], row["id"]))

    def get_portfolio_operation(self, operation_id, name="Minha Carteira"):
        for row in self.rows:
            if row["id"] == operation_id:
                return row
        return None

    def insert_portfolio_operation(self, portfolio_name, ticker, operation_type, occurred_on,
                                  quantity, unit_price, amount, fees, taxes, currency, notes=None):
        row = {
            "id": self._next_id,
            "ticker": ticker,
            "operation_type": operation_type,
            "occurred_on": occurred_on,
            "quantity": quantity,
            "unit_price": unit_price,
            "amount": amount,
            "fees": fees,
            "taxes": taxes,
            "currency": currency,
            "notes": notes,
            "created_at": None,
            "updated_at": None,
        }
        self._next_id += 1
        self.rows.append(row)
        return row

    def update_portfolio_operation(self, operation_id, ticker, operation_type, occurred_on,
                                  quantity, unit_price, amount, fees, taxes, currency, notes=None):
        for row in self.rows:
            if row["id"] == operation_id:
                row.update({
                    "ticker": ticker,
                    "operation_type": operation_type,
                    "occurred_on": occurred_on,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "amount": amount,
                    "fees": fees,
                    "taxes": taxes,
                    "currency": currency,
                    "notes": notes,
                })
                return row
        raise ValueError("Operação não encontrada.")

    def delete_portfolio_operation(self, operation_id, name="Minha Carteira"):
        before = len(self.rows)
        self.rows = [row for row in self.rows if row["id"] != operation_id]
        return len(self.rows) < before

    def latest_price(self, ticker, source=None):
        return self.prices.get(ticker)


def buy(day, quantity=10, unit_price=10, fees=0, taxes=0, ticker="PETR4"):
    return {
        "ticker": ticker,
        "operation_type": "buy",
        "occurred_on": day,
        "quantity": quantity,
        "unit_price": unit_price,
        "fees": fees,
        "taxes": taxes,
    }


class RecordOperationTests(unittest.TestCase):
    def test_records_buy_and_returns_operation(self):
        repository = FakeRepository()
        result = record_operation(buy("2025-01-01"), repository=repository)
        self.assertEqual(result["operation"]["operation_type"], "buy")
        self.assertEqual(result["operation"]["ticker"], "PETR4")
        self.assertEqual(len(repository.rows), 1)

    def test_rejects_sell_above_position(self):
        repository = FakeRepository()
        with self.assertRaisesRegex(ValueError, "excede"):
            record_operation({
                "ticker": "PETR4",
                "operation_type": "sell",
                "occurred_on": "2025-01-01",
                "quantity": 5,
                "unit_price": 12,
            }, repository=repository)
        self.assertEqual(repository.rows, [])

    def test_allows_partial_sell_after_buy(self):
        repository = FakeRepository()
        record_operation(buy("2025-01-01", quantity=10), repository=repository)
        result = record_operation({
            "ticker": "PETR4",
            "operation_type": "sell",
            "occurred_on": "2025-02-01",
            "quantity": 4,
            "unit_price": 12,
            "fees": 1,
        }, repository=repository)
        self.assertEqual(result["operation"]["operation_type"], "sell")
        self.assertEqual(len(repository.rows), 2)


class EditDeleteTests(unittest.TestCase):
    def test_edit_rejects_change_that_makes_sell_invalid(self):
        repository = FakeRepository(rows=[
            {
                "id": 1,
                "ticker": "PETR4",
                "operation_type": "buy",
                "occurred_on": date(2025, 1, 1),
                "quantity": Decimal("10"),
                "unit_price": Decimal("10"),
                "amount": Decimal("0"),
                "fees": Decimal("0"),
                "taxes": Decimal("0"),
                "currency": "BRL",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
            {
                "id": 2,
                "ticker": "PETR4",
                "operation_type": "sell",
                "occurred_on": date(2025, 2, 1),
                "quantity": Decimal("6"),
                "unit_price": Decimal("12"),
                "amount": Decimal("0"),
                "fees": Decimal("0"),
                "taxes": Decimal("0"),
                "currency": "BRL",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        with self.assertRaisesRegex(ValueError, "excede"):
            edit_operation(1, {
                "id": 1,
                "ticker": "PETR4",
                "operation_type": "buy",
                "occurred_on": "2025-01-01",
                "quantity": 3,
                "unit_price": 10,
            }, repository=repository)
        self.assertEqual(repository.rows[0]["quantity"], Decimal("10"))

    def test_delete_rejects_when_remaining_sell_exceeds_position(self):
        repository = FakeRepository(rows=[
            {
                "id": 1,
                "ticker": "PETR4",
                "operation_type": "buy",
                "occurred_on": date(2025, 1, 1),
                "quantity": Decimal("10"),
                "unit_price": Decimal("10"),
                "amount": Decimal("0"),
                "fees": Decimal("0"),
                "taxes": Decimal("0"),
                "currency": "BRL",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
            {
                "id": 2,
                "ticker": "PETR4",
                "operation_type": "sell",
                "occurred_on": date(2025, 2, 1),
                "quantity": Decimal("10"),
                "unit_price": Decimal("12"),
                "amount": Decimal("0"),
                "fees": Decimal("0"),
                "taxes": Decimal("0"),
                "currency": "BRL",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        with self.assertRaisesRegex(ValueError, "excede"):
            delete_operation(1, repository=repository)
        self.assertEqual(len(repository.rows), 2)

    def test_delete_allows_when_ledger_stays_valid(self):
        repository = FakeRepository(rows=[
            {
                "id": 1,
                "ticker": "PETR4",
                "operation_type": "buy",
                "occurred_on": date(2025, 1, 1),
                "quantity": Decimal("10"),
                "unit_price": Decimal("10"),
                "amount": Decimal("0"),
                "fees": Decimal("0"),
                "taxes": Decimal("0"),
                "currency": "BRL",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        result = delete_operation(1, repository=repository)
        self.assertEqual(result["id"], 1)
        self.assertEqual(repository.rows, [])


class PositionSummaryTests(unittest.TestCase):
    def test_summarizes_position_with_realized_and_unrealized(self):
        repository = FakeRepository(
            rows=[
                {
                    "id": 1,
                    "ticker": "PETR4",
                    "operation_type": "buy",
                    "occurred_on": date(2025, 1, 1),
                    "quantity": Decimal("10"),
                    "unit_price": Decimal("10"),
                    "amount": Decimal("0"),
                    "fees": Decimal("0"),
                    "taxes": Decimal("0"),
                    "currency": "BRL",
                    "notes": None,
                    "created_at": None,
                    "updated_at": None,
                },
                {
                    "id": 2,
                    "ticker": "PETR4",
                    "operation_type": "sell",
                    "occurred_on": date(2025, 2, 1),
                    "quantity": Decimal("4"),
                    "unit_price": Decimal("12"),
                    "amount": Decimal("0"),
                    "fees": Decimal("0"),
                    "taxes": Decimal("0"),
                    "currency": "BRL",
                    "notes": None,
                    "created_at": None,
                    "updated_at": None,
                },
            ],
            prices={"PETR4": {"close": Decimal("11"), "price_date": date(2025, 3, 1), "source": "yahoo"}},
        )
        result = position_summary(repository=repository)
        position = result["positions"]["PETR4"]
        self.assertEqual(position["quantity"], 6.0)
        self.assertEqual(position["cost_basis"], 60.0)
        self.assertEqual(position["average_cost"], 10.0)
        self.assertEqual(position["realized_pnl"], 8.0)
        self.assertEqual(position["unrealized_pnl"], 6.0)
        self.assertEqual(position["total_pnl"], 14.0)
        self.assertEqual(position["market_price"], 11.0)

    def test_lists_operations(self):
        repository = FakeRepository(rows=[
            {
                "id": 1,
                "ticker": "PETR4",
                "operation_type": "dividend",
                "occurred_on": date(2025, 3, 1),
                "quantity": Decimal("0"),
                "unit_price": Decimal("0"),
                "amount": Decimal("5"),
                "fees": Decimal("0"),
                "taxes": Decimal("1"),
                "currency": "BRL",
                "notes": None,
                "created_at": None,
                "updated_at": None,
            },
        ])
        result = list_operations(repository=repository)
        self.assertEqual(len(result["operations"]), 1)
        self.assertEqual(result["operations"][0]["operation_type"], "dividend")
        self.assertEqual(result["operations"][0]["amount"], 5.0)


if __name__ == "__main__":
    unittest.main()
