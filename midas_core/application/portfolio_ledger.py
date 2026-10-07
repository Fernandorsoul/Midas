"""Caso de uso do livro de operações: validação, persistência e posição/P&L.

A interface HTTP não calcula regras financeiras; este módulo orquestra o
domínio e o repositório e devolve payloads prontos para JSON.
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from midas_core.domain.portfolio import (
    OPERATION_TYPES,
    CASHFLOW_TYPES,
    INCOME_TYPES,
    EXPENSE_TYPES,
    TRADE_TYPES,
    Operation,
    calculate_position,
)

DEFAULT_PORTFOLIO = "Minha Carteira"
DEFAULT_CURRENCY = "BRL"
MAX_NOTES_LENGTH = 500


def _to_decimal(value, field, allow_empty=False):
    if value is None or value == "":
        if allow_empty:
            return Decimal("0")
        raise ValueError(f"{field} é obrigatório.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as error:
        raise ValueError(f"{field} inválido.") from error
    if not number.is_finite():
        raise ValueError(f"{field} inválido.")
    return number


def _parse_date(value):
    if not value or not isinstance(value, str):
        raise ValueError("Data da operação é obrigatória (AAAA-MM-DD).")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("Data da operação inválida (use AAAA-MM-DD).") from error


def _normalize_type(value):
    if not value or not isinstance(value, str):
        raise ValueError("Tipo de operação é obrigatório.")
    kind = value.strip().lower()
    if kind not in OPERATION_TYPES:
        raise ValueError("Tipo de operação inválido.")
    return kind


def parse_operation_payload(payload, partial=False):
    """Converte um payload HTTP em campos validados de operação."""
    if not isinstance(payload, dict):
        raise ValueError("Envie um objeto JSON válido.")

    fields = {}
    if "operation_type" in payload or not partial:
        fields["operation_type"] = _normalize_type(payload.get("operation_type"))
    if "occurred_on" in payload or not partial:
        fields["occurred_on"] = _parse_date(payload.get("occurred_on"))

    kind = fields.get("operation_type")
    if partial and kind is None:
        raise ValueError("Tipo de operação é obrigatório.")

    ticker = payload.get("ticker")
    if ticker is not None:
        ticker = str(ticker).strip().upper()
        if not ticker:
            raise ValueError("Ticker inválido.")
        fields["ticker"] = ticker
    elif not partial:
        fields["ticker"] = None

    for name, label in (
        ("quantity", "Quantidade"),
        ("unit_price", "Preço unitário"),
        ("amount", "Valor"),
        ("fees", "Taxas"),
        ("taxes", "Impostos"),
    ):
        if name in payload or not partial:
            fields[name] = _to_decimal(payload.get(name), label, allow_empty=True)

    currency = payload.get("currency", DEFAULT_CURRENCY if not partial else None)
    if currency is not None:
        currency = str(currency).strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("Moeda inválida. Use um código de três letras, como BRL.")
        fields["currency"] = currency

    notes = payload.get("notes")
    if notes is not None:
        notes = str(notes).strip()
        if len(notes) > MAX_NOTES_LENGTH:
            raise ValueError("Observação muito longa.")
        fields["notes"] = notes or None
    elif not partial:
        fields["notes"] = None

    _validate_field_combination(fields, kind, partial=partial)
    return fields


def _validate_field_combination(fields, kind, partial=False):
    if kind in TRADE_TYPES or (partial and kind is None):
        if not partial and fields.get("ticker") is None:
            raise ValueError("Compra e venda exigem ticker.")
        if not partial and fields.get("quantity", Decimal("0")) <= 0:
            raise ValueError("Compra e venda exigem quantidade positiva.")
    elif kind in INCOME_TYPES | EXPENSE_TYPES:
        if not partial and fields.get("ticker") is None:
            raise ValueError("Proventos, taxas e impostos exigem ticker.")
        if not partial and fields.get("amount", Decimal("0")) <= 0:
            raise ValueError("Proventos, taxas e impostos exigem valor positivo.")
    elif kind in CASHFLOW_TYPES:
        if fields.get("ticker"):
            raise ValueError("Aporte e retirada não usam ticker.")
        if not partial and fields.get("amount", Decimal("0")) <= 0:
            raise ValueError("Aporte e retirada exigem valor positivo.")


def _operation_from_fields(kind, fields):
    return Operation(
        operation_type=kind,
        occurred_on=fields["occurred_on"],
        quantity=fields.get("quantity", Decimal("0")),
        unit_price=fields.get("unit_price", Decimal("0")),
        amount=fields.get("amount", Decimal("0")),
        fees=fields.get("fees", Decimal("0")),
        taxes=fields.get("taxes", Decimal("0")),
        currency=fields.get("currency", DEFAULT_CURRENCY),
        notes=fields.get("notes"),
    )


def _load_operation(repository, operation_id):
    row = repository.get_portfolio_operation(operation_id)
    if row is None:
        raise ValueError("Operação não encontrada.")
    return row


def _operations_for_ledger(repository, portfolio_name, ticker=None):
    rows = repository.list_portfolio_operations(portfolio_name, ticker=ticker)
    result = []
    for row in rows:
        operation = _operation_from_fields(row["operation_type"], {
            "occurred_on": row["occurred_on"],
            "quantity": row["quantity"],
            "unit_price": row["unit_price"],
            "amount": row["amount"],
            "fees": row["fees"],
            "taxes": row["taxes"],
            "currency": row["currency"],
            "notes": row["notes"],
        })
        result.append({"id": row["id"], "operation": operation, "ticker": row["ticker"]})
    return result


def _ledger_operations(entries, exclude_id=None):
    return [entry["operation"] for entry in entries if entry["id"] != exclude_id]


def _row_to_api(row):
    return {
        "id": row["id"],
        "ticker": row["ticker"],
        "operation_type": row["operation_type"],
        "occurred_on": row["occurred_on"].isoformat() if hasattr(row["occurred_on"], "isoformat") else str(row["occurred_on"]),
        "quantity": float(row["quantity"]),
        "unit_price": float(row["unit_price"]),
        "amount": float(row["amount"]),
        "fees": float(row["fees"]),
        "taxes": float(row["taxes"]),
        "currency": row["currency"],
        "notes": row["notes"],
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
    }


def _summary_to_api(summary, market_price=None, currency=DEFAULT_CURRENCY):
    return {
        "quantity": float(summary.quantity),
        "cost_basis": float(summary.cost_basis),
        "average_cost": float(summary.average_cost),
        "realized_pnl": float(summary.realized_pnl),
        "unrealized_pnl": None if summary.unrealized_pnl is None else float(summary.unrealized_pnl),
        "income": float(summary.income),
        "expenses": float(summary.expenses),
        "net_cash_flow": float(summary.net_cash_flow),
        "total_pnl": float(summary.total_pnl),
        "market_price": None if market_price is None else float(market_price),
        "currency": currency,
    }


def list_operations(repository=None, portfolio_name=DEFAULT_PORTFOLIO, ticker=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    rows = repository.list_portfolio_operations(portfolio_name, ticker=ticker)
    return {"operations": [_row_to_api(row) for row in rows]}


def record_operation(payload, repository=None, portfolio_name=DEFAULT_PORTFOLIO):
    """Lança uma operação validando o livro resultante (sem venda descoberta)."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    fields = parse_operation_payload(payload)
    kind = fields["operation_type"]
    ticker = fields.get("ticker")
    if kind in TRADE_TYPES | INCOME_TYPES | EXPENSE_TYPES and not ticker:
        raise ValueError("Operação de ativo exige ticker.")

    operation = _operation_from_fields(kind, fields)
    if ticker:
        ledger = _ledger_operations(_operations_for_ledger(repository, portfolio_name, ticker=ticker))
        ledger.append(operation)
        calculate_position(ledger)

    row = repository.insert_portfolio_operation(
        portfolio_name=portfolio_name,
        ticker=ticker,
        operation_type=kind,
        occurred_on=fields["occurred_on"],
        quantity=fields.get("quantity", Decimal("0")),
        unit_price=fields.get("unit_price", Decimal("0")),
        amount=fields.get("amount", Decimal("0")),
        fees=fields.get("fees", Decimal("0")),
        taxes=fields.get("taxes", Decimal("0")),
        currency=fields.get("currency", DEFAULT_CURRENCY),
        notes=fields.get("notes"),
    )
    return {"operation": _row_to_api(row), "message": "Operação registrada."}


def edit_operation(operation_id, payload, repository=None, portfolio_name=DEFAULT_PORTFOLIO):
    """Edita uma operação de forma controlada, revalidando o livro completo."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    existing = _load_operation(repository, operation_id)
    fields = parse_operation_payload(payload, partial=True)

    # Tipo e data são obrigatórios na edição controlada.
    if "operation_type" not in fields or "occurred_on" not in fields:
        raise ValueError("Edição exige tipo e data da operação.")

    kind = fields["operation_type"]
    previous_ticker = existing["ticker"]
    ticker = fields.get("ticker", previous_ticker)
    if kind in CASHFLOW_TYPES and ticker:
        raise ValueError("Aporte e retirada não usam ticker.")
    if kind in TRADE_TYPES | INCOME_TYPES | EXPENSE_TYPES and not ticker:
        raise ValueError("Operação de ativo exige ticker.")

    merged = {
        "occurred_on": fields["occurred_on"],
        "quantity": fields.get("quantity", existing["quantity"]),
        "unit_price": fields.get("unit_price", existing["unit_price"]),
        "amount": fields.get("amount", existing["amount"]),
        "fees": fields.get("fees", existing["fees"]),
        "taxes": fields.get("taxes", existing["taxes"]),
        "currency": fields.get("currency", existing["currency"]),
        "notes": fields.get("notes", existing["notes"]),
    }
    operation = _operation_from_fields(kind, merged)

    # Revalida o livro do ativo anterior e do novo, se o ticker mudar.
    tickers_to_check = {ticker} if ticker else set()
    if previous_ticker and previous_ticker != ticker:
        tickers_to_check.add(previous_ticker)
    for item in tickers_to_check:
        ledger = _ledger_operations(
            _operations_for_ledger(repository, portfolio_name, ticker=item),
            exclude_id=operation_id,
        )
        if item == ticker:
            ledger.append(operation)
        calculate_position(ledger)

    row = repository.update_portfolio_operation(
        operation_id,
        ticker=ticker,
        operation_type=kind,
        occurred_on=fields["occurred_on"],
        quantity=merged["quantity"],
        unit_price=merged["unit_price"],
        amount=merged["amount"],
        fees=merged["fees"],
        taxes=merged["taxes"],
        currency=merged["currency"],
        notes=merged["notes"],
    )
    return {"operation": _row_to_api(row), "message": "Operação atualizada."}


def delete_operation(operation_id, repository=None, portfolio_name=DEFAULT_PORTFOLIO):
    """Exclui uma operação revalidando o livro restante."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    existing = _load_operation(repository, operation_id)
    ticker = existing["ticker"]
    if ticker:
        ledger = _ledger_operations(
            _operations_for_ledger(repository, portfolio_name, ticker=ticker),
            exclude_id=operation_id,
        )
        calculate_position(ledger)
    repository.delete_portfolio_operation(operation_id)
    return {"message": "Operação excluída.", "id": operation_id}


def position_summary(ticker=None, repository=None, portfolio_name=DEFAULT_PORTFOLIO):
    """Consulta de posição: quantidade, custo, preço médio e P&L separados."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()

    if ticker:
        tickers = [ticker.strip().upper()]
    else:
        rows = repository.list_portfolio_operations(portfolio_name)
        tickers = sorted({row["ticker"] for row in rows if row["ticker"]})

    positions = {}
    totals = {
        "cost_basis": Decimal("0"),
        "realized_pnl": Decimal("0"),
        "unrealized_pnl": Decimal("0"),
        "income": Decimal("0"),
        "expenses": Decimal("0"),
        "net_cash_flow": Decimal("0"),
        "total_pnl": Decimal("0"),
        "market_value": Decimal("0"),
    }
    currency = DEFAULT_CURRENCY

    for item in tickers:
        entries = _operations_for_ledger(repository, portfolio_name, ticker=item)
        operations = _ledger_operations(entries)
        if not operations:
            continue
        market = repository.latest_price(item)
        market_price = market["close"] if market else None
        summary = calculate_position(operations, market_price=market_price)
        currency = operations[-1].currency
        payload = _summary_to_api(summary, market_price=market_price, currency=currency)
        payload["ticker"] = item
        if market:
            payload["price_date"] = market["price_date"].isoformat() if hasattr(market["price_date"], "isoformat") else str(market["price_date"])
            payload["source"] = market["source"]
        else:
            payload["price_date"] = None
            payload["source"] = None
        positions[item] = payload
        totals["cost_basis"] += summary.cost_basis
        totals["realized_pnl"] += summary.realized_pnl
        if summary.unrealized_pnl is not None:
            totals["unrealized_pnl"] += summary.unrealized_pnl
        totals["income"] += summary.income
        totals["expenses"] += summary.expenses
        totals["net_cash_flow"] += summary.net_cash_flow
        totals["total_pnl"] += summary.total_pnl
        if market_price is not None:
            totals["market_value"] += summary.quantity * Decimal(str(market_price))

    # Caixa da carteira (aportes e retiradas) não pertence a um ativo.
    cash_entries = _operations_for_ledger(repository, portfolio_name, ticker=None)
    cash_only = [
        entry["operation"] for entry in cash_entries
        if entry["operation"].operation_type in CASHFLOW_TYPES
    ]
    if cash_only:
        cash_summary = calculate_position(cash_only)
        totals["net_cash_flow"] += cash_summary.net_cash_flow

    return {
        "positions": positions,
        "totals": {key: float(value) for key, value in totals.items()},
        "currency": currency,
        "portfolio": portfolio_name,
    }
