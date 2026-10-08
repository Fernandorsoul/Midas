"""Fallback de fontes de preço: Yahoo primário, brapi em falha retratável.

Nunca mascara erro: o resultado traz fonte usada, tentativas e kind seguro.
"""
from __future__ import annotations

from midas_core.domain.market_quality import (
    ERROR_UNKNOWN,
    classify_fetch_error,
    fallback_report,
    next_price_source,
    should_try_fallback,
)

# Ordem de tentativa alinhada a SOURCE_POLICY["prices"].
PRICE_SOURCES = ("yahoo.finance", "brapi.dev")


def _fetch_yahoo(ticker: str, period: str):
    from midas_core.infrastructure.yahoo import fetch_history
    return fetch_history(ticker, period)


def _fetch_brapi(ticker: str, period: str):
    import datetime as _dt

    from midas_core.domain.entities import ImportedStock, PricePoint
    from midas_core.infrastructure.brapi import BrapiClient

    range_map = {"1y": "1y", "2y": "2y", "5y": "5y", "10y": "10y", "max": "max"}
    price_range = range_map.get(period, "5y")
    payload = BrapiClient().historical([ticker], price_range)
    results = payload.get("results") or []
    if not results:
        raise RuntimeError("A brapi não retornou histórico para o ativo.")
    entry = results[0]
    prices = []
    for point in entry.get("historicalDataPrice") or []:
        close = point.get("close")
        price_date = point.get("date")
        if close is None or not price_date:
            continue
        if isinstance(price_date, (int, float)):
            day = _dt.datetime.fromtimestamp(price_date, _dt.timezone.utc).date()
        else:
            day = price_date
        adjusted = point.get("adjustedClose")
        volume = point.get("volume")
        prices.append(PricePoint(
            price_date=day,
            close=float(close),
            adjusted_close=float(adjusted) if adjusted is not None else None,
            volume=float(volume) if volume is not None else None,
        ))
    if not prices:
        raise RuntimeError("A brapi não retornou preços válidos para o ativo.")
    name = entry.get("name") or entry.get("shortName") or ticker
    return ImportedStock(ticker=ticker, name=name, prices=tuple(prices))


_FETCHERS = {
    "yahoo.finance": _fetch_yahoo,
    "brapi.dev": _fetch_brapi,
}


def fetch_price_history(ticker: str, period: str = "5y", fetchers=None):
    """Tenta as fontes oficiais em ordem; para em sucesso.

    Retorna dict com `stock`, `source` e `fallback` (relatório de tentativas).
    Se todas falharem, levanta RuntimeError com mensagem segura.
    """
    fetchers = fetchers or _FETCHERS
    attempts = []
    source = next_price_source([])
    while source:
        fetcher = fetchers.get(source)
        if fetcher is None:
            attempts.append({
                "source": source, "ok": False,
                "error_kind": ERROR_UNKNOWN, "message": "Fonte sem adaptador.",
            })
            source = next_price_source([a["source"] for a in attempts])
            continue
        try:
            stock = fetcher(ticker, period)
            attempts.append({"source": source, "ok": True, "error_kind": None, "message": ""})
            return {
                "stock": stock,
                "source": source,
                "fallback": fallback_report(ticker, attempts),
            }
        except Exception as error:
            message = str(error) or type(error).__name__
            kind = classify_fetch_error(message)
            attempts.append({
                "source": source, "ok": False,
                "error_kind": kind, "message": message,
            })
            if not should_try_fallback(kind):
                break
            source = next_price_source([a["source"] for a in attempts])

    report = fallback_report(ticker, attempts)
    kinds = {a["error_kind"] for a in attempts if not a.get("ok")}
    if "rate_limit" in kinds:
        raise RuntimeError(
            f"Limite de requisições das fontes de mercado atingido para {ticker}. Tente novamente mais tarde."
        )
    if "timeout" in kinds and not attempts[1:]:
        raise RuntimeError(f"Timeout ao consultar fontes de mercado para {ticker}.")
    raise RuntimeError(f"Não foi possível importar cotações de {ticker} em nenhuma fonte oficial.")
