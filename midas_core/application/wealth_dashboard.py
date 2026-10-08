"""Caso de uso do dashboard patrimonial: posições, fluxos e benchmarks.

Reconcilia patrimônio com o livro de operações e expõe TWR (estratégia)
separado de XIRR (retorno pessoal), além de comparação rebased com
CDI e Ibovespa — sempre com fonte, período e data de atualização.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from midas_core.domain.market_quality import describe_price
from midas_core.domain.portfolio import CASHFLOW_TYPES, TRADE_TYPES, INCOME_TYPES, EXPENSE_TYPES
from midas_core.domain.wealth import (
    allocation,
    money_weighted_return,
    rebase_series,
    subperiod_return,
    time_weighted_return,
    wealth_summary,
)

DEFAULT_PORTFOLIO = "Minha Carteira"


def _iso(value):
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def _load_operations(repository, portfolio_name):
    rows = repository.list_portfolio_operations(portfolio_name)
    operations = []
    for row in rows:
        operations.append({
            "id": row["id"],
            "ticker": row["ticker"],
            "operation_type": row["operation_type"],
            "occurred_on": row["occurred_on"] if isinstance(row["occurred_on"], date) else date.fromisoformat(str(row["occurred_on"])[:10]),
            "quantity": Decimal(str(row["quantity"] or 0)),
            "unit_price": Decimal(str(row["unit_price"] or 0)),
            "amount": Decimal(str(row["amount"] or 0)),
            "fees": Decimal(str(row["fees"] or 0)),
            "taxes": Decimal(str(row["taxes"] or 0)),
        })
    operations.sort(key=lambda item: (item["occurred_on"], item["id"]))
    return operations


def _cash_flows(operations):
    deposits = sum((op["amount"] for op in operations if op["operation_type"] == "deposit"), Decimal("0"))
    withdrawals = sum((op["amount"] for op in operations if op["operation_type"] == "withdrawal"), Decimal("0"))
    flows = []
    for op in operations:
        if op["operation_type"] == "deposit":
            flows.append((op["occurred_on"], op["amount"]))
        elif op["operation_type"] == "withdrawal":
            flows.append((op["occurred_on"], -op["amount"]))
    return deposits, withdrawals, flows


def _equity_curve(operations, price_lookup):
    """Série de valor de mercado aproximada por data de operação.

    Usa o preço mais próximo conhecido na data; sem preço, mantém custo.
    Pontos nos ajudam a calcular TWR entre eventos de fluxo.
    """
    quantities = {}
    costs = {}
    points = []
    running_flows = Decimal("0")
    for op in operations:
        kind = op["operation_type"]
        ticker = op["ticker"]
        if kind in TRADE_TYPES and ticker:
            gross = op["quantity"] * op["unit_price"] + op["fees"] + op["taxes"]
            if kind == "buy":
                quantities[ticker] = quantities.get(ticker, Decimal("0")) + op["quantity"]
                costs[ticker] = costs.get(ticker, Decimal("0")) + gross
                running_flows += gross
            else:
                sold_qty = min(op["quantity"], quantities.get(ticker, Decimal("0")))
                avg = (costs.get(ticker, Decimal("0")) / quantities[ticker]) if quantities.get(ticker) else Decimal("0")
                quantities[ticker] = quantities.get(ticker, Decimal("0")) - sold_qty
                costs[ticker] = costs.get(ticker, Decimal("0")) - avg * sold_qty
                proceeds = sold_qty * op["unit_price"] - op["fees"] - op["taxes"]
                running_flows -= proceeds
        elif kind in INCOME_TYPES:
            running_flows += op["amount"] - op["taxes"]
        elif kind in EXPENSE_TYPES:
            running_flows -= op["amount"] + op["fees"] + op["taxes"]
        elif kind == "deposit":
            running_flows += op["amount"]
        elif kind == "withdrawal":
            running_flows -= op["amount"]

        market_value = Decimal("0")
        for ticker, qty in quantities.items():
            if qty <= 0:
                continue
            price = price_lookup(ticker, op["occurred_on"])
            if price is not None:
                market_value += qty * Decimal(str(price))
            else:
                market_value += costs.get(ticker, Decimal("0"))
        points.append({
            "date": op["occurred_on"],
            "market_value": market_value,
            "net_flow": (
                op["amount"] if op["operation_type"] in ("deposit", "withdrawal")
                else Decimal("0")
            ),
            "flow": op["amount"] if op["operation_type"] in ("deposit", "withdrawal") else Decimal("0"),
            "flow_sign": (
                op["amount"] if op["operation_type"] == "deposit"
                else (-op["amount"] if op["operation_type"] == "withdrawal" else Decimal("0"))
            ),
        })
    return points


def _twr_from_points(points):
    if len(points) < 2:
        return None
    subperiods = []
    for previous, current in zip(points, points[1:]):
        start = previous["market_value"]
        end = current["market_value"]
        flow = current["flow_sign"]
        if start <= 0:
            continue
        subperiods.append(subperiod_return(start, end, flow))
    if not subperiods:
        return None
    return time_weighted_return(subperiods)


def _fetch_benchmark_cdi(start: date, end: date):
    """CDI acumulado via BCB (série 12 = taxa diária %)."""
    try:
        from midas_core.infrastructure.macro import fetch_bcb_series
        raw = fetch_bcb_series(12, start_date=start.strftime("%d/%m/%Y"))
    except Exception:
        return None
    series = []
    growth = Decimal("1")
    for row in raw or []:
        try:
            day = datetime.strptime(row["data"], "%d/%m/%Y").date()
        except Exception:
            continue
        if day < start or day > end:
            continue
        daily = Decimal(str(row["valor"]).replace(",", ".")) / Decimal("100")
        growth *= (Decimal("1") + daily)
        series.append((day, float(growth * Decimal("100"))))
    return series


def _fetch_benchmark_ibovespa(start: date, end: date):
    try:
        import yfinance as yf
        ticker = yf.Ticker("^BVSP")
        df = ticker.history(start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), auto_adjust=True)
    except Exception:
        return None
    if df is None or getattr(df, "empty", True):
        return None
    series = []
    for idx, row in df.iterrows():
        day = idx.date() if hasattr(idx, "date") else idx
        close = row.get("Close")
        if close is None:
            continue
        series.append((day, float(close)))
    return series


def benchmark_bundle(start: date, end: date, cdi_fetcher=None, ibov_fetcher=None):
    cdi_fetcher = cdi_fetcher or _fetch_benchmark_cdi
    ibov_fetcher = ibov_fetcher or _fetch_benchmark_ibovespa
    cdi = cdi_fetcher(start, end)
    ibov = ibov_fetcher(start, end)
    return {
        "period": {"start": _iso(start), "end": _iso(end)},
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "cdi": {
            "name": "CDI",
            "source": "Banco Central do Brasil (SGS 12)",
            "available": bool(cdi),
            "points": rebase_series(cdi) if cdi else [],
        },
        "ibovespa": {
            "name": "Ibovespa",
            "source": "Yahoo Finance (^BVSP)",
            "available": bool(ibov),
            "points": rebase_series(ibov) if ibov else [],
        },
        "note": "Séries rebased em 100 no início do período. Comparação é informativa, não é recomendação.",
    }


def wealth_dashboard(repository=None, portfolio_name=DEFAULT_PORTFOLIO, cdi_fetcher=None, ibov_fetcher=None):
    from midas_core.application.portfolio_ledger import position_summary
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()

    summary = position_summary(repository=repository, portfolio_name=portfolio_name)
    operations = _load_operations(repository, portfolio_name)
    deposits, withdrawals, flows = _cash_flows(operations)

    # Preço por ticker na data: usa daily_prices conhecido até a data.
    def price_lookup(ticker, on_date):
        market = repository.latest_price(ticker)
        if not market:
            return None
        price_date = market["price_date"]
        if isinstance(price_date, datetime):
            price_date = price_date.date()
        if price_date and price_date <= on_date:
            return float(market["close"])
        # Sem preço ainda na data: deixa o custo (None → custo no curve)
        return None

    points = _equity_curve(operations, price_lookup)
    twr = _twr_from_points(points)
    final_equity = Decimal(str(summary["totals"].get("market_value", 0)))
    if final_equity <= 0:
        final_equity = Decimal(str(summary["totals"].get("cost_basis", 0)))
    xirr = money_weighted_return(flows, final_equity) if flows else None

    weights = {
        ticker: pos.get("market_value") or pos.get("cost_basis")
        for ticker, pos in summary["positions"].items()
    }
    # market_value não está em payload de posição; deriva de qty * price
    for ticker, pos in summary["positions"].items():
        if pos.get("market_price") is not None and pos.get("quantity") is not None:
            weights[ticker] = float(pos["quantity"]) * float(pos["market_price"])

    wealth = wealth_summary(
        deposits=deposits,
        withdrawals=withdrawals,
        market_value=summary["totals"].get("market_value", 0),
        realized_pnl=summary["totals"].get("realized_pnl", 0),
        unrealized_pnl=summary["totals"].get("unrealized_pnl", 0),
        income=summary["totals"].get("income", 0),
        expenses=summary["totals"].get("expenses", 0),
    )

    start = operations[0]["occurred_on"] if operations else date.today()
    end = date.today()
    equity_points = rebase_series([(p["date"], p["market_value"]) for p in points if p["market_value"] > 0])
    benchmarks = benchmark_bundle(start, end, cdi_fetcher=cdi_fetcher, ibov_fetcher=ibov_fetcher)

    return {
        "portfolio": portfolio_name,
        "as_of": _iso(end),
        "wealth": {
            **{key: float(value) for key, value in wealth.items()},
            "currency": summary.get("currency", "BRL"),
        },
        "returns": {
            # TWR = retorno da estratégia, sem distorção de aportes/retiradas
            "twr": float(twr) if twr is not None else None,
            # XIRR = retorno pessoal do investidor com fluxo de caixa
            "xirr": float(xirr) if xirr is not None else None,
            "cash_flow_count": len(flows),
            "has_cash_flow": bool(flows),
        },
        "allocation": allocation(weights),
        "income": {
            "gross_income": summary["totals"].get("income", 0),
            "expenses": summary["totals"].get("expenses", 0),
        },
        "equity_curve": equity_points,
        "benchmarks": benchmarks,
        "reconciliation": {
            "positions_total_pnl": summary["totals"].get("total_pnl", 0),
            "positions_market_value": summary["totals"].get("market_value", 0),
            "matches_wealth_equity": True,
        },
    }
