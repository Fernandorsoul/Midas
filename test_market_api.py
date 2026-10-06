import json
import unittest
from unittest.mock import patch

from midas_core.application.market_import import import_stocks
from midas_core.infrastructure.brapi import BrapiClient, MarketAPIError, fetch_quote, normalize_tickers

class FakeHTTPResponse:
    status = 200

    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class FakeClient:
    def quotes(self, tickers):
        return {"results": [{"requestedSymbol": "PETR4", "symbol": "PETR4", "data": {"shortName": "Petrobras"}}]}

    def historical(self, tickers, price_range):
        return {"results": [{"requestedSymbol": "PETR4", "symbol": "PETR4", "data": {
            "historicalDataPrice": [{"date": 1704067200, "close": 37.5, "adjustedClose": 34.2, "volume": 1000}]
        }}]}

class FakeRepository:
    def __init__(self):
        self.stocks = None
        self.source = None

    def save_stocks(self, stocks, source):
        self.stocks = stocks
        self.source = source
        return sum(len(stock.prices) for stock in stocks)

class MarketAPITests(unittest.TestCase):
    def test_normalizes_and_deduplicates_tickers(self):
        self.assertEqual(normalize_tickers([" petr4 ", "PETR4", "vale3"]), ["PETR4", "VALE3"])

    def test_rejects_unsafe_ticker(self):
        with self.assertRaises(ValueError):
            normalize_tickers(["PETR4;DROP"])

    def test_import_persists_asset_and_adjusted_price(self):
        repository = FakeRepository()
        result = import_stocks(["PETR4"], "1y", FakeClient(), repository)
        self.assertEqual(result["assets"], 1)
        self.assertEqual(result["prices"], 1)
        price = repository.stocks[0].prices[0]
        self.assertEqual((price.close, price.adjusted_close, price.volume), (37.5, 34.2, 1000.0))
        self.assertEqual(repository.source, "brapi.dev")

    def test_refuses_partial_api_response(self):
        with self.assertRaises(MarketAPIError):
            import_stocks(["PETR4", "VALE3"], "1y", FakeClient(), FakeRepository())

    def test_fetch_quote_uses_v2_endpoint_bearer_header_and_returns_first_data(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["authorization"] = request.headers.get("Authorization")
            captured["timeout"] = timeout
            return FakeHTTPResponse({
                "results": [{
                    "requestedSymbol": "B3SA3",
                    "symbol": "B3SA3",
                    "data": {
                        "shortName": "B3",
                        "currency": "BRL",
                        "regularMarketPrice": 11.25,
                    },
                }],
            })

        with patch("midas_core.infrastructure.brapi.urlopen", fake_urlopen):
            data = BrapiClient(token="test-token", timeout=7).fetch_quote("b3sa3")

        self.assertEqual(data["regularMarketPrice"], 11.25)
        self.assertEqual(captured["authorization"], "Bearer test-token")
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(
            captured["url"],
            "https://brapi.dev/api/v2/stocks/quote?symbols=B3SA3",
        )

    def test_fetch_quote_rejects_missing_data(self):
        with patch(
            "midas_core.infrastructure.brapi.urlopen",
            lambda request, timeout: FakeHTTPResponse({"results": [{"symbol": "B3SA3"}]}),
        ):
            with self.assertRaises(MarketAPIError):
                BrapiClient(token="test-token").fetch_quote("B3SA3")

    def test_module_fetch_quote_uses_client(self):
        with patch(
            "midas_core.infrastructure.brapi.urlopen",
            lambda request, timeout: FakeHTTPResponse({
                "results": [{"symbol": "B3SA3", "data": {"regularMarketPrice": 10.0}}]
            }),
        ):
            self.assertEqual(fetch_quote("B3SA3", token="test-token")["regularMarketPrice"], 10.0)

if __name__ == "__main__":
    unittest.main()
