"""Regras puras para o livro razão de uma carteira.

Valores monetários e quantidades usam ``Decimal`` para que cálculos financeiros
não dependam de arredondamento binário de ponto flutuante.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re


TRADE_TYPES = frozenset({"buy", "sell"})
INCOME_TYPES = frozenset({"dividend", "jcp"})
EXPENSE_TYPES = frozenset({"fee", "tax"})
CASHFLOW_TYPES = frozenset({"deposit", "withdrawal"})
OPERATION_TYPES = TRADE_TYPES | INCOME_TYPES | EXPENSE_TYPES | CASHFLOW_TYPES
ZERO = Decimal("0")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class Operation:
    operation_type: str
    occurred_on: date
    quantity: Decimal = ZERO
    unit_price: Decimal = ZERO
    amount: Decimal = ZERO
    fees: Decimal = ZERO
    taxes: Decimal = ZERO
    currency: str = "BRL"
    notes: str | None = None

    def __post_init__(self):
        if self.operation_type not in OPERATION_TYPES:
            raise ValueError("Tipo de operação inválido.")
        if not isinstance(self.occurred_on, date):
            raise ValueError("Data da operação inválida.")
        if not CURRENCY_PATTERN.match(self.currency or ""):
            raise ValueError("Moeda inválida. Use um código de três letras, como BRL.")
        if self.operation_type in TRADE_TYPES:
            if self.quantity <= ZERO or self.unit_price < ZERO:
                raise ValueError("Compra e venda exigem quantidade positiva e preço não negativo.")
        elif self.operation_type in CASHFLOW_TYPES | INCOME_TYPES | EXPENSE_TYPES:
            if self.amount <= ZERO:
                raise ValueError("Aporte, retirada, provento, taxa e imposto exigem valor positivo.")
        if self.fees < ZERO or self.taxes < ZERO:
            raise ValueError("Taxas e impostos não podem ser negativos.")
        if self.quantity < ZERO or self.unit_price < ZERO or self.amount < ZERO:
            raise ValueError("Quantidade, preço e valor não podem ser negativos.")


@dataclass(frozen=True)
class PositionSummary:
    quantity: Decimal
    cost_basis: Decimal
    average_cost: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None
    income: Decimal
    expenses: Decimal
    net_cash_flow: Decimal

    @property
    def total_pnl(self):
        """Resultado total: realizado + não realizado + renda - despesas avulsas."""
        unrealized = ZERO if self.unrealized_pnl is None else self.unrealized_pnl
        return self.realized_pnl + unrealized + self.income - self.expenses


def calculate_position(operations, market_price=None):
    """Calcula uma posição pelo custo médio móvel, em ordem cronológica.

    Venda descoberta não é suportada: uma venda acima da posição disponível é
    rejeitada. Dividendos/JCP são renda; taxas, impostos e saques são saídas de
    caixa e não mudam o custo dos ativos ainda mantidos.
    """
    quantity = cost_basis = realized_pnl = income = expenses = net_cash_flow = ZERO
    currencies = set()
    for operation in sorted(operations, key=lambda item: item.occurred_on):
        currencies.add(operation.currency)
        kind = operation.operation_type
        if kind == "buy":
            gross = operation.quantity * operation.unit_price
            total = gross + operation.fees + operation.taxes
            quantity += operation.quantity
            cost_basis += total
            net_cash_flow -= total
        elif kind == "sell":
            if operation.quantity > quantity:
                raise ValueError("Venda excede a posição disponível.")
            average_cost = cost_basis / quantity if quantity else ZERO
            proceeds = operation.quantity * operation.unit_price - operation.fees - operation.taxes
            realized_pnl += proceeds - (operation.quantity * average_cost)
            quantity -= operation.quantity
            cost_basis -= operation.quantity * average_cost
            net_cash_flow += proceeds
        elif kind in INCOME_TYPES:
            received = operation.amount - operation.taxes
            income += received
            net_cash_flow += received
        elif kind in EXPENSE_TYPES:
            total = operation.amount + operation.fees + operation.taxes
            expenses += total
            net_cash_flow -= total
        elif kind == "deposit":
            net_cash_flow += operation.amount
        elif kind == "withdrawal":
            net_cash_flow -= operation.amount

    if len(currencies) > 1:
        raise ValueError("Operações da mesma posição devem usar a mesma moeda.")

    average_cost = cost_basis / quantity if quantity else ZERO
    unrealized_pnl = None if market_price is None else (quantity * Decimal(str(market_price))) - cost_basis
    return PositionSummary(
        quantity=quantity,
        cost_basis=cost_basis,
        average_cost=average_cost,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        income=income,
        expenses=expenses,
        net_cash_flow=net_cash_flow,
    )


def validate_ledger(operations):
    """Valida o livro completo e devolve o resumo final.

    Usado após inclusão, edição ou exclusão para garantir que nenhuma venda
    exceda a posição disponível em nenhum ponto da linha do tempo.
    """
    return calculate_position(operations)
