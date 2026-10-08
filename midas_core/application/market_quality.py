"""Caso de uso de proveniência e qualidade dos dados de mercado."""
from midas_core.domain.market_quality import (
    SOURCE_POLICY,
    PriceMetadata,
    collection_outcome,
    describe_price,
    resolve_price_source,
)


def market_quality_report(repository=None):
    """Resume fonte, data de mercado e frescor por ativo."""
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    assets = repository.assets_with_prices()
    rows = []
    for asset in assets:
        prices = asset.get("prices") or []
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
        description = describe_price(metadata)
        description["ticker"] = asset["ticker"]
        description["name"] = asset.get("name")
        description["series_source"] = resolve_price_source([price["source"] for price in prices])
        description["series_points"] = len(prices)
        rows.append(description)
    stale_count = sum(1 for row in rows if row.get("stale"))
    return {
        "policy": SOURCE_POLICY,
        "assets": rows,
        "summary": {
            "total": len(rows),
            "stale": stale_count,
            "missing": sum(1 for row in rows if row.get("quality") == "missing"),
        },
    }
