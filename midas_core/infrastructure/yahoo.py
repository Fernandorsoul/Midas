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

def fetch_dividends(ticker: str) -> dict:
    """Busca dados de dividendos do Yahoo Finance."""
    yahoo_ticker = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(yahoo_ticker)
        info = stock.info
        dividends = stock.dividends
    except Exception as e:
        raise YahooFinanceError(f"Erro ao buscar dividendos de {ticker}: {e}")

    # Dividendos dos últimos12 meses
    annual_dividend = None
    if not dividends.empty:
        # Somar dividendos dos últimos12 meses
        from datetime import datetime, timedelta
        one_year_ago = datetime.now() - timedelta(days=365)
        recent_dividends = dividends[dividends.index >= one_year_ago]
        if not recent_dividends.empty:
            annual_dividend = float(recent_dividends.sum())

    # Dividend yield
    dividend_yield = info.get("dividendYield")
    if dividend_yield is not None:
        dividend_yield = float(dividend_yield)

    # Preço atual
    price = info.get("regularMarketPrice") or info.get("previousClose")
    if price is not None:
        price = float(price)

    return {
        "annual_dividend": annual_dividend,
        "dividend_yield": dividend_yield,
        "price": price,
    }
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

def fetch_historical_fundamentals(ticker: str) -> dict:
    """Busca dados fundamentalistas históricos do Yahoo Finance.
    
    Retorna um dicionário com dados anuais e trimestrais dos últimos10 anos.
    """
    yahoo_ticker = normalize_ticker(ticker)
    try:
        stock = yf.Ticker(yahoo_ticker)
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        quarterly_financials = stock.quarterly_financials
        quarterly_balance_sheet = stock.quarterly_balance_sheet
    except Exception as e:
        raise YahooFinanceError(f"Erro ao buscar fundamentos históricos de {ticker}: {e}")

    if financials.empty and quarterly_financials.empty:
        return {}

    result = {}
    
    # Processar dados anuais
    for date in financials.columns:
        year = date.year
        if year < 2015:  # Limitar a10 anos
            continue
        _process_financial_data(result, year, financials, balance_sheet, date)
    
    # Processar dados trimestrais (para anos não cobertos pelos anuais)
    if quarterly_financials is not None and not quarterly_financials.empty:
        for date in quarterly_financials.columns:
            year = date.year
            if year < 2015:  # Limitar a10 anos
                continue
            # Só usar trimestral se não tiver anual para aquele ano
            if year not in result:
                _process_financial_data(result, year, quarterly_financials, quarterly_balance_sheet, date)
    
    return result

def _process_financial_data(result, year, financials, balance_sheet, date):
    """Processa dados financeiros de uma data específica."""
    # Lucro líquido
    net_income = None
    if "Net Income" in financials.index:
        val = financials.loc["Net Income", date]
        if not _is_nan(val):
            net_income = float(val)
    
    # Receita
    revenue = None
    if "Total Revenue" in financials.index:
        val = financials.loc["Total Revenue", date]
        if not _is_nan(val):
            revenue = float(val)
    
    # Patrimônio líquido
    equity = None
    if "Stockholders Equity" in balance_sheet.index:
        val = balance_sheet.loc["Stockholders Equity", date]
        if not _is_nan(val):
            equity = float(val)
    
    # Calcular métricas
    net_margin = None
    if net_income and revenue and revenue > 0:
        net_margin = net_income / revenue
    
    roe = None
    if net_income and equity and equity > 0:
        roe = net_income / equity
    
    # Dívida/Patrimônio
    debt_to_equity = None
    total_debt = None
    if "Total Debt" in balance_sheet.index:
        val = balance_sheet.loc["Total Debt", date]
        if not _is_nan(val):
            total_debt = float(val)
    if total_debt and equity and equity > 0:
        debt_to_equity = total_debt / equity
    
    # Lucro por ação (aproximado)
    eps = None
    if "Basic EPS" in financials.index:
        val = financials.loc["Basic EPS", date]
        if not _is_nan(val):
            eps = float(val)
    
    result[year] = {
        "net_margin": net_margin,
        "roe": roe,
        "net_income": net_income,
        "revenue": revenue,
        "equity": equity,
        "debt_to_equity": debt_to_equity,
        "eps": eps,
    }

def _is_nan(value):
    """Verifica se um valor é NaN."""
    if value is None:
        return True
    try:
        import math
        return math.isnan(float(value))
    except (TypeError, ValueError):
        return True