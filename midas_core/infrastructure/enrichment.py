"""Enriquecimento de dados históricos de múltiplas fontes públicas."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from midas_core.domain.entities import ImportedStock, PricePoint

# APIs públicas gratuitas
ALPHA_VANTAGE_BASE = "https://www.alphavantage.co/query"
BRAPI_BASE = "https://brapi.dev/api/v2"

class DataEnrichmentError(RuntimeError):
    pass

def fetch_alpha_vantage(ticker: str, api_key: str = "demo") -> list[PricePoint]:
    """Busca dados do Alpha Vantage (gratuito com chave demo)."""
    symbol = f"{ticker}.SA" if not ticker.endswith(".SA") else ticker
    params = {
        "function": "TIME_SERIES_DAILY_ADJUSTED",
        "symbol": symbol,
        "outputsize": "full",
        "apikey": api_key,
    }
    url = f"{ALPHA_VANTAGE_BASE}?{urlencode(params)}"
    
    try:
        with urlopen(Request(url, headers={"User-Agent": "Midas/0.3"}), timeout=30) as response:
            data = json.load(response)
    except Exception as e:
        raise DataEnrichmentError(f"Erro ao buscar dados do Alpha Vantage para {ticker}: {e}")
    
    if "Error Message" in data:
        raise DataEnrichmentError(f"Alpha Vantage: {data['Error Message']}")
    
    if "Note" in data:  # Rate limit
        raise DataEnrichmentError("Alpha Vantage: rate limit atingido")
    
    time_series = data.get("Time Series (Daily)", {})
    if not time_series:
        raise DataEnrichmentError(f"Alpha Vantage: nenhum dado encontrado para {ticker}")
    
    prices = []
    for date_str, values in time_series.items():
        try:
            close = float(values.get("4. close", 0))
            adjusted = float(values.get("5. adjusted close", close))
            volume = float(values.get("6. volume", 0))
            
            if close <= 0:
                continue
            
            price_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            prices.append(PricePoint(
                price_date=price_date,
                close=close,
                adjusted_close=adjusted if adjusted > 0 else None,
                volume=volume if volume >= 0 else None,
            ))
        except (ValueError, TypeError):
            continue
    
    return sorted(prices, key=lambda p: p.price_date)

def fetch_brapi_historical(ticker: str, token: str = None, period: str = "10y") -> list[PricePoint]:
    """Busca dados históricos do brapi.dev."""
    import os
    token = token or os.getenv("BRAPI_TOKEN", "")
    
    params = {
        "symbols": ticker,
        "range": period,
        "interval": "1d",
        "sortOrder": "asc",
    }
    url = f"{BRAPI_BASE}/stocks/historical?{urlencode(params)}"
    headers = {
        "Accept": "application/json",
        "User-Agent": "Midas/0.3",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            data = json.load(response)
    except HTTPError as e:
        if e.code == 401:
            raise DataEnrichmentError("brapi.dev: token inválido ou ausente")
        raise DataEnrichmentError(f"brapi.dev: HTTP {e.code}")
    except Exception as e:
        raise DataEnrichmentError(f"Erro ao buscar dados do brapi.dev para {ticker}: {e}")
    
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise DataEnrichmentError("brapi.dev: formato inesperado")
    
    results = data["results"]
    if not results or not isinstance(results[0], dict):
        raise DataEnrichmentError(f"brapi.dev: nenhum dado encontrado para {ticker}")
    
    historical = results[0].get("data", {}).get("historicalDataPrice", [])
    if not historical:
        raise DataEnrichmentError(f"brapi.dev: nenhum histórico encontrado para {ticker}")
    
    prices = []
    for point in historical:
        try:
            timestamp = point.get("date")
            close = point.get("close")
            adjusted = point.get("adjustedClose")
            volume = point.get("volume")
            
            if not isinstance(timestamp, (int, float)) or not isinstance(close, (int, float)):
                continue
            if close <= 0:
                continue
            
            price_date = datetime.fromtimestamp(timestamp, timezone.utc).date()
            prices.append(PricePoint(
                price_date=price_date,
                close=float(close),
                adjusted_close=float(adjusted) if isinstance(adjusted, (int, float)) and adjusted > 0 else None,
                volume=float(volume) if isinstance(volume, (int, float)) and volume >= 0 else None,
            ))
        except (ValueError, TypeError):
            continue
    
    return sorted(prices, key=lambda p: p.price_date)

def merge_prices(existing: list[PricePoint], new: list[PricePoint]) -> list[PricePoint]:
    """Merge duas listas de preços, priorizando dados mais recentes."""
    by_date = {}
    for p in existing:
        key = (p.price_date, p.close)
        by_date[key] = p
    
    for p in new:
        key = (p.price_date, p.close)
        if key not in by_date:
            by_date[key] = p
    
    return sorted(by_date.values(), key=lambda p: p.price_date)

def enrich_stock_data(ticker: str, existing_prices: list[PricePoint] = None) -> ImportedStock:
    """Enriquece dados de um ativo buscando de múltiplas fontes."""
    existing_prices = existing_prices or []
    all_prices = list(existing_prices)
    errors = []
    
    # Tentar Yahoo Finance (já implementado)
    try:
        from midas_core.infrastructure.yahoo import fetch_history
        stock = fetch_history(ticker, "max")
        all_prices = merge_prices(all_prices, list(stock.prices))
    except Exception as e:
        errors.append(f"Yahoo Finance: {e}")
    
    # Tentar brapi.dev
    try:
        brapi_prices = fetch_brapi_historical(ticker, period="max")
        all_prices = merge_prices(all_prices, brapi_prices)
    except DataEnrichmentError as e:
        errors.append(f"brapi.dev: {e}")
    
    if not all_prices:
        raise DataEnrichmentError(f"Nenhum dado encontrado para {ticker}. Erros: {'; '.join(errors)}")
    
    # Buscar nome do ativo
    try:
        from midas_core.infrastructure.yahoo import fetch_fundamentals, normalize_ticker
        import yfinance as yf
        yahoo_ticker = normalize_ticker(ticker)
        stock_info = yf.Ticker(yahoo_ticker)
        name = stock_info.info.get("longName") or stock_info.info.get("shortName") or ticker
    except Exception:
        name = ticker
    
    return ImportedStock(
        ticker=ticker,
        name=name,
        prices=tuple(all_prices),
    )

def enrich_all_stocks(tickers: list[str]) -> list[ImportedStock]:
    """Enriquece dados de múltiplos ativos."""
    enriched = []
    errors = []
    
    for ticker in tickers:
        try:
            stock = enrich_stock_data(ticker)
            enriched.append(stock)
            print(f"  {ticker}: {len(stock.prices)} preços")
        except DataEnrichmentError as e:
            errors.append(f"{ticker}: {e}")
            print(f"  {ticker}: ERRO - {e}")
    
    return enriched