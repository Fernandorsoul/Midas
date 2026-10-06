"""Caso de uso: publicar dados mensais para treinamento."""
from datetime import datetime, timezone
import uuid

from midas_core.domain.features import SUPPORTED_HORIZONS, build_samples, month_end_series
from midas_core.infrastructure.repositories import MongoRepository, PostgresRepository
from midas_core.infrastructure.yahoo import fetch_historical_fundamentals, YahooFinanceError

# Ano mínimo para dados fundamentalistas
MIN_FUNDAMENTAL_YEAR = 2015

def publish_dataset(horizons=(12,), source=None, tickers=None, mongo_repository=None, postgres_repository=None):
    horizons = tuple(dict.fromkeys(horizons))
    if not horizons or any(value not in SUPPORTED_HORIZONS for value in horizons):
        raise ValueError("Horizontes aceitos: 6, 12, 24 e 36 meses.")
    mongo_repository = mongo_repository or MongoRepository()
    postgres_repository = postgres_repository or PostgresRepository()

    # Se não especificado, usa a fonte com mais dados
    if source is None:
        source = _best_source(postgres_repository)

    grouped = {}
    for row in postgres_repository.training_prices(source):
        ticker = row["ticker"]
        # Filtrar por tickers se especificado
        if tickers and ticker not in tickers:
            continue
        grouped.setdefault(ticker, []).append(row)
    if not grouped:
        raise ValueError(f"Não há cotações da fonte {source} no PostgreSQL.")

    # Buscar fundamentos históricos para cada ticker
    fundamentals_cache = {}
    for ticker in grouped:
        try:
            fundamentals_cache[ticker] = fetch_historical_fundamentals(ticker)
        except (YahooFinanceError, Exception):
            fundamentals_cache[ticker] = {}  # Usar valores neutros

    dataset_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc)
    samples = []
    covered_horizons = set()
    for ticker, prices in grouped.items():
        series = month_end_series(prices)
        fundamentals = fundamentals_cache.get(ticker, {})
        for horizon in horizons:
            generated = build_samples(series, ticker, horizon, fundamentals, MIN_FUNDAMENTAL_YEAR)
            if generated:
                covered_horizons.add(horizon)
            for sample in generated:
                sample["dataset_id"] = dataset_id
            samples.extend(generated)

    missing = set(horizons) - covered_horizons
    if missing:
        labels = ", ".join(f"{item} meses" for item in sorted(missing))
        raise ValueError(f"Histórico insuficiente para: {labels}")

    metadata = {
        "_id": dataset_id,
        "name": "brapi-monthly-adjusted",
        "version": created_at.isoformat(),
        "source": f"{source}:daily_prices.adjusted_close",
        "is_demo": False,
        "created_at": created_at,
        "horizons": list(horizons),
        "tickers": sorted(grouped),
        "samples": len(samples),
    }
    mongo_repository.publish_dataset(metadata, samples)
    return dataset_id, len(samples)

def _best_source(repository):
    """Retorna a fonte com mais ativos cadastrados."""
    with repository._connector() as connection:
        result = connection.execute(
            """SELECT source, COUNT(DISTINCT asset_id) as cnt
               FROM daily_prices
               WHERE source IN ('brapi.dev', 'yahoo.finance')
               GROUP BY source
               ORDER BY cnt DESC
               LIMIT 1"""
        ).fetchone()
    return result["source"] if result else "brapi.dev"
