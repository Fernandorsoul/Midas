"""Caso de uso: importar ações do Yahoo Finance."""
from midas_core.domain.market_quality import collection_outcome
from midas_core.infrastructure.repositories import PostgresRepository
from midas_core.infrastructure.yahoo import YahooFinanceError, fetch_history, SOURCE

def import_stocks_yahoo(tickers, period="10y", repository=None):
    """Importa ativos do Yahoo Finance para o PostgreSQL.

    Falha parcial não é sucesso: o resultado carrega `collection` com status
    `succeeded`, `partial` ou `failed` e nunca mascara erro de coleta.
    """
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
    outcome = collection_outcome(imported_count=len(stocks), failed_count=len(errors))
    result = {
        "assets": len(stocks),
        "prices": price_count,
        "source": SOURCE,
        "range": period,
        "collection": outcome,
    }
    if errors:
        result["warnings"] = errors
    return result