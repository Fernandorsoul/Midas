"""Adaptador HTTP do Yahoo Finance via yfinance."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from dataclasses import dataclass

import yfinance as yf

from midas_core.domain.entities import ImportedStock, PricePoint

SOURCE = "yahoo.finance"
TICKER_PATTERN = re.compile(r"^[A-Z0-9]{4,12}$")

@dataclass(frozen=True)
class FundamentalData:
    """Dados fundamentalistas do ativo."""
    pe_ratio: float | None  # P/L
    pb_ratio: float | None  # P/VP
    dividend_yield: float | None  # Dividend Yield
    net_margin: float | None  # Margem Líquida
    roe: float | None  # ROE
    market_cap: float | None  # Valor de mercado

class YahooFinanceError(RuntimeError):
    pass

def normalize_ticker(ticker: str) -> str:
    """Normaliza ticker brasileiro para formato Yahoo (ex: PETR4 -> PETR4.SA)."""
    ticker = ticker.strip().upper()
    if not TICKER_PATTERN.fullmatch(ticker):
        raise ValueError(f"Ticker inválido: {ticker}")
    if not ticker.endswith(".SA"):
        ticker = f"{ticker}.SA"
    return ticker

def denormalize_ticker(ticker: str) -> str:
    """Remove sufixo .SA do ticker."""
    return ticker.replace(".SA", "")

def fetch_history(ticker: str, period: str = "10y") -> ImportedStock:
    """Busca histórico de preços do Yahoo Finance."""
    yahoo_ticker = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(yahoo_ticker)
        df = stock.history(period=period, auto_adjust=False)
    except Exception as e:
        raise YahooFinanceError(f"Erro ao buscar dados de {ticker}: {e}")

    if df.empty:
        raise YahooFinanceError(f"Nenhum dado encontrado para {ticker}")

    prices = []
    for idx, row in df.iterrows():
        close = float(row["Close"])
        adjusted = float(row.get("Adj Close", close))
        volume = float(row["Volume"]) if "Volume" in row else None

        if close <= 0:
            continue

        price_date = idx.date() if hasattr(idx, "date") else idx
        prices.append(PricePoint(
            price_date=price_date,
            close=close,
            adjusted_close=adjusted if adjusted > 0 else None,
            volume=volume if volume is not None and volume >= 0 else None,
        ))

    if not prices:
        raise YahooFinanceError(f"Nenhum preço válido para {ticker}")

    # Buscar nome do ativo
    try:
        info = stock.info
        name = info.get("longName") or info.get("shortName") or denormalize_ticker(yahoo_ticker)
    except Exception:
        name = denormalize_ticker(yahoo_ticker)

    return ImportedStock(
        ticker=denormalize_ticker(yahoo_ticker),
        name=name,
        prices=tuple(prices),
    )

def fetch_fundamentals(ticker: str) -> FundamentalData:
    """Busca dados fundamentalistas do Yahoo Finance."""
    yahoo_ticker = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(yahoo_ticker)
        info = stock.info
    except Exception as e:
        raise YahooFinanceError(f"Erro ao buscar fundamentos de {ticker}: {e}")

    def safe_float(key):
        value = info.get(key)
        if value is None or not isinstance(value, (int, float)):
            return None
        return float(value)

    return FundamentalData(
        pe_ratio=safe_float("trailingPE"),
        pb_ratio=safe_float("priceToBook"),
        dividend_yield=safe_float("dividendYield"),
        net_margin=safe_float("profitMargins"),
        roe=safe_float("returnOnEquity"),
        market_cap=safe_float("marketCap"),
    )