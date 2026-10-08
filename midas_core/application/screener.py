"""Caso de uso do screener de oportunidade a partir dos dados de mercado."""
from __future__ import annotations

from midas_core.domain.market_quality import PriceMetadata, describe_price
from midas_core.domain.screener import DISCLAIMER, screen_assets


def _features_from_asset(asset):
    from midas_core.domain.features import latest_features, month_end_series

    prices = asset.get("prices") or []
    last = prices[-1] if prices else None
    metadata = None
    if last is not None:
        metadata = PriceMetadata(
            source=last.get("source"),
            price_date=last.get("price_date"),
            ingested_at=last.get("ingested_at"),
            close=float(last.get("close")) if last.get("close") is not None else None,
            adjusted_close=float(last.get("adjusted_close")) if last.get("adjusted_close") is not None else None,
        )
    quality = describe_price(metadata)
    factors = latest_features(month_end_series(prices)) or {}
    return {
        "ticker": asset.get("ticker"),
        "name": asset.get("name"),
        "category": asset.get("category"),
        "sector": asset.get("sector"),
        "price": quality.get("close"),
        "price_date": quality.get("price_date"),
        "source": quality.get("source"),
        "stale": quality.get("stale"),
        "momentum_12m": factors.get("momentum_12m"),
        "drawdown": factors.get("drawdown"),
        "volatility": factors.get("volatility"),
        "volume": asset.get("volume") or (last.get("volume") if last else None),
    }


def run_screener(
    repository=None,
    query=None,
    category=None,
    sector=None,
    min_volume=None,
    limit=20,
):
    """Pontua ativos com critérios explícitos a partir do universo importado."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    assets = repository.assets_with_prices()
    prepared = [_features_from_asset(asset) for asset in assets]
    result = screen_assets(
        prepared,
        min_volume=min_volume,
        category=category,
        sector=sector,
        query=query,
        limit=limit,
    )
    result["disclaimer"] = DISCLAIMER
    result["universe"] = len(assets)
    return result
