"""Compatibilidade: importador público exposto pela arquitetura modular."""
from midas_core.application.market_import import import_stocks
from midas_core.infrastructure.brapi import BrapiClient, MarketAPIError, normalize_tickers
from midas_core.interfaces.cli import import_market_main

if __name__ == "__main__":
    import_market_main()
