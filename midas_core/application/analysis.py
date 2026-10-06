"""Caso de uso: montar o ranking apresentado pela API."""
import numpy as np

from midas_core.domain.features import SUPPORTED_HORIZONS, latest_features, month_end_series
from midas_core.domain.regression import from_artifact, predict
from midas_core.infrastructure.repositories import MongoRepository, PostgresRepository
from midas_core.infrastructure.yahoo import fetch_fundamentals, YahooFinanceError

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
        asset["chart"] = [float(price["close"]) for price in prices[-756:]]
        asset["price"] = float(prices[-1]["close"]) if prices else None
        asset["price_date"] = prices[-1]["price_date"].isoformat() if prices else None
        asset["source"] = prices[-1]["source"] if prices else None
        # Buscar fundamentos para o ativo
        try:
            fundamentals = fetch_fundamentals(asset["ticker"])
        except (YahooFinanceError, Exception):
            fundamentals = None
        asset["_features"] = latest_features(month_end_series(prices), fundamentals)

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
