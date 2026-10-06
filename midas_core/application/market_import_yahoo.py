"""Caso de uso: importar ações do Yahoo Finance."""
from midas_core.domain.entities import ImportedStock
from midas_core.infrastructure.repositories import PostgresRepository
from midas_core.infrastructure.yahoo import YahooFinanceError, fetch_history, SOURCE

def import_stocks_yahoo(tickers, period="10y", repository=None):
    """Importa ativos do Yahoo Finance para o PostgreSQL."""
    repository = repository or PostgresRepository()

    stocks = []
    errors = []
    for ticker in tickers:
        try:
            stock = fetch_history(ticker, period)
            stocks.append(stock)
        except (YahooFinanceError, ValueError) as e:
            errors.append(f"{ticker}: {e}")

    if not stocks:
        raise YahooFinanceError(f"Nenhum ativo importado. Erros: {'; '.join(errors)}")

    price_count = repository.save_stocks(stocks, SOURCE)
    result = {
        "assets": len(stocks),
        "prices": price_count,
        "source": SOURCE,
        "range": period,
    }
    if errors:
        result["warnings"] = errors
    return result