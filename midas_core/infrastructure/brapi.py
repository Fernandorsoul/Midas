"""Adaptador HTTP da brapi.dev."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, TypedDict, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE_URL = "https://brapi.dev/api/v2/stocks"
SOURCE = "brapi.dev"
VALID_RANGES = {"1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max"}
TICKER_PATTERN = re.compile(r"^[A-Z0-9]{4,12}$")

class MarketAPIError(RuntimeError):
    pass

class BrapiQuoteData(TypedDict, total=False):
    shortName: str
    longName: str
    currency: str
    regularMarketPrice: float
    regularMarketChange: float
    regularMarketChangePercent: float
    regularMarketVolume: float
    marketCap: float

def normalize_tickers(values):
    tickers = list(dict.fromkeys(value.strip().upper() for value in values))
    if not tickers or any(not TICKER_PATTERN.fullmatch(ticker) for ticker in tickers):
        raise ValueError("Informe códigos válidos, como PETR4, VALE3 ou ITUB4.")
    return tickers

class BrapiClient:
    def __init__(self, token: str | None = None, timeout: int = 30, retries: int = 3):
        raw_token = token or os.getenv("BRAPI_TOKEN") or ""
        clean_token = raw_token.strip()
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()
        self.token = clean_token or None
        self.timeout = timeout
        self.retries = retries

    def quotes(self, tickers):
        return self._get("quote", {"symbols": ",".join(tickers)})

    def fetch_quote(self, ticker: str) -> BrapiQuoteData:
        symbol = normalize_tickers([ticker])[0]
        payload = self.quotes([symbol])
        if not payload["results"]:
            raise MarketAPIError(f"A API não retornou cotação para {symbol}.")
        data = payload["results"][0].get("data")
        if not isinstance(data, dict):
            raise MarketAPIError("A API retornou uma cotação em formato inesperado.")
        return cast(BrapiQuoteData, data)

    def historical(self, tickers, price_range):
        if price_range not in VALID_RANGES:
            raise ValueError(f"Período inválido: {price_range}.")
        return self._get("historical", {
            "symbols": ",".join(tickers),
            "range": price_range,
            "interval": "1d",
            "sortOrder": "asc",
        })

    def _get(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        url = f"{API_BASE_URL}/{path}?{urlencode(params)}"
        headers = {"Accept": "application/json", "User-Agent": "Midas/0.2"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        for attempt in range(self.retries):
            try:
                with urlopen(Request(url, headers=headers), timeout=self.timeout) as response:
                    status = getattr(response, "status", 200)
                    if status < 200 or status >= 300:
                        raise MarketAPIError(f"A API respondeu com HTTP {status}.")
                    payload = json.load(response)
                if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                    raise MarketAPIError("A API retornou um formato inesperado.")
                return payload
            except HTTPError as error:
                if error.code == 429 and attempt + 1 < self.retries:
                    time.sleep(2**attempt)
                    continue
                if error.code in (401, 403):
                    raise MarketAPIError(
                        "A API recusou o acesso. Configure BRAPI_TOKEN para este ativo ou período."
                    ) from error
                raise MarketAPIError(f"A API respondeu com HTTP {error.code}.") from error
            except (URLError, TimeoutError) as error:
                if attempt + 1 < self.retries:
                    time.sleep(2**attempt)
                    continue
                raise MarketAPIError("Não foi possível conectar à brapi.dev.") from error
            except (json.JSONDecodeError, UnicodeError) as error:
                raise MarketAPIError("A API retornou JSON inválido.") from error
        raise MarketAPIError("Não foi possível consultar a brapi.dev.")

def fetch_quote(ticker: str, token: str | None = None) -> BrapiQuoteData:
    return BrapiClient(token=token).fetch_quote(ticker)
