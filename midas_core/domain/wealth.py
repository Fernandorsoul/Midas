"""Métricas patrimoniais puras: TWR, XIRR, alocação e rebase de benchmarks.

TWR remove o efeito de aportes/retiradas no retorno de estratégia.
XIRR é o retorno pessoal do investidor com fluxo de caixa irregular.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

ZERO = Decimal("0")
ONE = Decimal("1")


@dataclass(frozen=True)
class CashFlow:
    occurred_on: date
    amount: Decimal  # positivo = aporte; negativo = retirada
    kind: str = "deposit"


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def money_weighted_return(flows, final_value, guess=0.1, max_iter=50, tol=Decimal("0.000001")):
    """XIRR anualizado por Newton-Raphson.

    `flows` é lista de (date, amount) com aporte positivo e retirada negativo.
    O valor final é tratado como entrada positiva na última data.
    Retorna None quando não há fluxos ou o solver não converge.
    """
    if not flows:
        return None
    points = [(day, _to_decimal(amount)) for day, amount in flows]
    last_day = max(day for day, _ in points)
    points.append((last_day, _to_decimal(final_value)))
    if not any(amount != ZERO for _, amount in points):
        return None

    base = points[0][0]
    years = [
        (Decimal((day - base).days) / Decimal("365"), amount)
        for day, amount in points
    ]
    rate = Decimal(str(guess))
    for _ in range(max_iter):
        value = ZERO
        derivative = ZERO
        for year, amount in years:
            factor = (ONE + rate) ** year
            value += amount / factor
            if year != ZERO:
                derivative -= year * amount / (factor * (ONE + rate))
        if abs(derivative) < tol:
            break
        step = value / derivative
        rate -= step
        if abs(step) < tol:
            break
    if rate <= Decimal("-0.999999"):
        return None
    return rate


def time_weighted_return(subperiods):
    """TWR composto a partir de retornos de subperíodos já sem fluxo de caixa.

    `subperiods` é lista de Decimal (ex.: 0.01 = +1%).
    """
    if not subperiods:
        return ZERO
    growth = ONE
    for r in subperiods:
        growth *= (ONE + _to_decimal(r))
    return growth - ONE


def subperiod_return(start_value, end_value, net_flow):
    """Retorno do período isolando aporte/retirada (fluxo meio do período)."""
    start_value = _to_decimal(start_value)
    end_value = _to_decimal(end_value)
    net_flow = _to_decimal(net_flow)
    if start_value <= ZERO:
        return ZERO
    return (end_value - start_value - net_flow) / start_value


def allocation(weights):
    """Normaliza pesos de alocação por ativo somando 1 (ou 0 se vazio)."""
    cleaned = {key: _to_decimal(value) for key, value in (weights or {}).items() if value is not None}
    total = sum(cleaned.values(), ZERO)
    if total <= ZERO:
        return {}
    return {key: float(value / total) for key, value in cleaned.items()}


def rebase_series(points, base=Decimal("100")):
    """Rebase de série de preços/patrimônio para comparar com benchmarks.

    `points` é lista de (date, value). O primeiro valor vira `base`.
    """
    cleaned = [(day, _to_decimal(value)) for day, value in points if value is not None]
    cleaned = [(day, value) for day, value in cleaned if value != ZERO]
    if not cleaned:
        return []
    first = cleaned[0][1]
    return [
        {"date": day.isoformat() if hasattr(day, "isoformat") else str(day), "value": float(base * value / first)}
        for day, value in cleaned
    ]


def wealth_summary(deposits, withdrawals, market_value, realized_pnl, unrealized_pnl, income, expenses):
    """Consolida patrimônio e separa retorno de estratégia do fluxo de caixa."""
    deposits = _to_decimal(deposits)
    withdrawals = _to_decimal(withdrawals)
    market_value = _to_decimal(market_value)
    invested = deposits - withdrawals
    total_pnl = _to_decimal(realized_pnl) + _to_decimal(unrealized_pnl) + _to_decimal(income) - _to_decimal(expenses)
    return {
        "market_value": market_value,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "net_contribution": invested,
        "total_pnl": total_pnl,
        # Patrimônio ≈ contribuição líquida + resultado acumulado da carteira
        "equity": invested + total_pnl,
    }
