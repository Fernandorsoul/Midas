"""Caso de uso: montar o ranking apresentado pela API."""
import numpy as np

from midas_core.domain.features import SUPPORTED_HORIZONS, latest_features, month_end_series
from midas_core.domain.market_quality import PriceMetadata, assert_consistent_series, describe_price, resolve_price_source
from midas_core.domain.regression import from_artifact, predict
from midas_core.infrastructure.repositories import MongoRepository, PostgresRepository
from midas_core.infrastructure.yahoo import fetch_historical_fundamentals, YahooFinanceError

MINIMUM_DRAWDOWN = -0.05
MINIMUM_RANK_CORRELATION = 0.10
MINIMUM_RELATIVE_MAE_IMPROVEMENT = 0.02

def _estimate(artifact, features):
    names = artifact["parameters"]["features"]
    values = np.asarray([features[name] for name in names], dtype=float)
    return float(predict(from_artifact(artifact), values)[0])

def _is_validated(metrics, artifact):
    return bool(
        metrics
        and artifact
        and artifact.get("parameters", {}).get("model_version") == 5
        and metrics.get("mae_improvement", -1) >= MINIMUM_RELATIVE_MAE_IMPROVEMENT
        and metrics.get("rank_correlation", -1) >= MINIMUM_RANK_CORRELATION
    )

def build_report(horizon, mongo_repository=None, postgres_repository=None):
    if horizon not in SUPPORTED_HORIZONS:
        raise ValueError("Horizonte deve ser 12, 24 ou 36 meses.")
    mongo_repository = mongo_repository or MongoRepository()
    postgres_repository = postgres_repository or PostgresRepository()

    assets = postgres_repository.assets_with_prices()
    for asset in assets:
        prices = asset.pop("prices")
        sources = [price["source"] for price in prices]
        series_source = assert_consistent_series(sources) or resolve_price_source(sources)
        last = prices[-1] if prices else None
        metadata = None
        if last is not None:
            metadata = PriceMetadata(
                source=last["source"],
                price_date=last["price_date"],
                ingested_at=last.get("ingested_at"),
                close=float(last["close"]) if last.get("close") is not None else None,
                adjusted_close=float(last["adjusted_close"]) if last.get("adjusted_close") is not None else None,
            )
        market_data = describe_price(metadata)
        market_data["series_source"] = series_source
        market_data["series_points"] = len(prices)
        asset["market_data"] = market_data
        # Exibição usa fechamento; treino usa ajustado quando existe.
        asset["chart"] = [float(price["close"]) for price in prices[-756:]]
        asset["price"] = market_data["close"]
        asset["price_date"] = market_data["price_date"]
        asset["source"] = market_data["source"]
        asset["_features"] = latest_features(month_end_series(prices))

    metrics = artifact = run_date = None
    for run in postgres_repository.model_runs(horizon):
        candidate_artifact = mongo_repository.artifact_for_run(run)
        if candidate_artifact:
            metrics = run["metrics"]
            artifact = candidate_artifact
            run_date = run["created_at"].isoformat()
            break

    validated = _is_validated(metrics, artifact)
    quantiles = (artifact or {}).get("parameters", {}).get("residual_quantiles", {})
    for asset in assets:
        features = asset.pop("_features")
        asset["opportunity"] = None
        if artifact is None or features is None:
            continue
        estimate = _estimate(artifact, features)
        lower = estimate + quantiles.get("p10", 0)
        upper = estimate + quantiles.get("p90", 0)
        asset["opportunity"] = {
            "estimate": estimate,
            "estimate_low": min(lower, upper),
            "estimate_high": max(lower, upper),
            "drawdown": features["drawdown"],
            "momentum_12m": features["momentum_12m"],
            "volatility": features["volatility"],
            "validated": validated,
            "candidate": validated
            and features["drawdown"] <= MINIMUM_DRAWDOWN
            and estimate > 0,
        }

    assets.sort(key=lambda asset: (
        not bool(asset["opportunity"] and asset["opportunity"]["candidate"]),
        -(asset["opportunity"]["estimate"] if asset["opportunity"] else float("-inf")),
        asset["ticker"],
    ))
    return {
        "assets": assets,
        "horizon": horizon,
        "metrics": metrics,
        "dataset_count": mongo_repository.dataset_count(),
        "model_validated": validated,
        "model_run_date": run_date,
        "method": "temporal-model-selection-v3" if artifact else None,
    }

def set_favorite(asset_id, saved, repository=None):
    (repository or PostgresRepository()).set_favorite(asset_id, saved)

def build_portfolio_report(horizon, portfolio_tickers=None, mongo_repository=None, postgres_repository=None):
    """Constrói relatório focado na carteira do usuário."""
    if portfolio_tickers is None:
        portfolio_tickers = (postgres_repository or PostgresRepository()).portfolio_tickers()
    
    if not portfolio_tickers:
        return {"portfolio": [], "portfolio_tickers": [], "horizon": horizon, "metrics": None, "model_validated": False, "model_run_date": None, "method": None}
    
    # Gerar relatório completo (sem fundamentos para performance)
    full_report = build_report(horizon, mongo_repository, postgres_repository)
    
    # Filtrar apenas ativos da carteira
    portfolio_assets = []
    found_tickers = set()
    for asset in full_report["assets"]:
        if asset["ticker"] in portfolio_tickers:
            portfolio_assets.append(asset)
            found_tickers.add(asset["ticker"])
    
    # Adicionar ativos que estão na carteira mas não no banco
    for ticker in portfolio_tickers:
        if ticker not in found_tickers:
            portfolio_assets.append({
                "ticker": ticker,
                "name": ticker,
                "category": "stock",
                "sector": "Não informado",
                "favorite": False,
                "chart": [],
                "price": None,
                "price_date": None,
                "source": None,
                "market_data": describe_price(None),
                "opportunity": None,
                "status": "Sem dados - adicione via Yahoo Finance",
            })
    
    # Ordenar por estimativa (melhor primeiro)
    portfolio_assets.sort(key=lambda x: (
        -(x["opportunity"]["estimate"] if x["opportunity"] else float("-inf")),
        x["ticker"],
    ))
    
    return {
        "portfolio": portfolio_assets,
        "portfolio_tickers": portfolio_tickers,
        "horizon": horizon,
        "metrics": full_report["metrics"],
        "model_validated": full_report["model_validated"],
        "model_run_date": full_report["model_run_date"],
        "method": full_report["method"],
    }
