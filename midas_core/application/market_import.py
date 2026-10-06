"""Caso de uso: importar ações da brapi.dev."""
from datetime import datetime, timezone

from midas_core.config import Settings
from midas_core.domain.entities import ImportedStock, PricePoint
from midas_core.infrastructure.brapi import (
    BrapiClient,
    MarketAPIError,
    SOURCE,
    normalize_tickers,
)
from midas_core.infrastructure.repositories import PostgresRepository

def _items_by_symbol(payload):
    items = {}
    for item in payload["results"]:
        if not isinstance(item, dict) or not isinstance(item.get("symbol"), str):
            continue
        items[item["symbol"].upper()] = item
        requested = item.get("requestedSymbol")
        if isinstance(requested, str):
            items[requested.upper()] = item
    return items

def _parse_price(point):
    timestamp = point.get("date")
    close = point.get("close")
    if not isinstance(timestamp, (int, float)) or not isinstance(close, (int, float)) or close <= 0:
        return None
    adjusted = point.get("adjustedClose")
    if not isinstance(adjusted, (int, float)) or adjusted <= 0:
        adjusted = None
    volume = point.get("volume")
    if not isinstance(volume, (int, float)) or volume < 0:
        volume = None
    return PricePoint(
        datetime.fromtimestamp(timestamp, timezone.utc).date(),
        float(close),
        float(adjusted) if adjusted is not None else None,
        float(volume) if volume is not None else None,
    )

def import_stocks(tickers, price_range="5y", client=None, repository=None):
    requested = normalize_tickers(tickers)
    if client is None:
        client = BrapiClient(token=Settings.from_environment().brapi_token)
    repository = repository or PostgresRepository()
    quote_payload = {"results": []}
    history_payload = {"results": []}
    # O plano gratuito aceita um ticker por requisição. Processar individualmente
    # mantém a importação compatível e permite identificar falhas por ativo.
    for ticker in requested:
        quote_payload["results"].extend(client.quotes([ticker])["results"])
        history_payload["results"].extend(
            client.historical([ticker], price_range)["results"]
        )
    quotes = _items_by_symbol(quote_payload)
    histories = _items_by_symbol(history_payload)
    missing = [ticker for ticker in requested if ticker not in quotes or ticker not in histories]
    if missing:
        raise MarketAPIError("A API não retornou todos os ativos: " + ", ".join(missing))

    stocks = []
    for requested_ticker in requested:
        quote = quotes[requested_ticker]
        ticker = quote["symbol"].upper()
        quote_data = quote.get("data") or {}
        name = quote_data.get("shortName") or quote_data.get("longName") or ticker
        raw_points = (histories[requested_ticker].get("data") or {}).get("historicalDataPrice") or []
        prices = tuple(price for point in raw_points if (price := _parse_price(point)) is not None)
        if not prices:
            raise MarketAPIError(f"A API não retornou histórico diário válido para {ticker}.")
        stocks.append(ImportedStock(ticker, name, prices))

    price_count = repository.save_stocks(stocks, SOURCE)
    return {"assets": len(stocks), "prices": price_count, "source": SOURCE, "range": price_range}
