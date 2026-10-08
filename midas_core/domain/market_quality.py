"""Política de fontes e qualidade dos dados de mercado.

Regras puras: fonte primária/fallback, frescor da série e flags de
qualidade. Não faz I/O nem depende de HTTP/bancos.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone

# Política de fontes por tipo de dado.
# Decisão: `enriched` e `macro` permanecem experimentais e fora do pipeline
# principal até terem proveniência e cobertura comparáveis.
SOURCE_POLICY = {
    "prices": {
        "primary": "yahoo.finance",
        "fallbacks": ("brapi.dev",),
        "experimental": ("enriched",),
    },
    "dividends": {
        "primary": "yahoo.finance",
        "fallbacks": (),
        "experimental": (),
    },
    "fundamentals": {
        "primary": "yahoo.finance",
        "fallbacks": (),
        "experimental": ("enriched",),
    },
}

# Fontes aceitas no dataset de treino (pipeline principal).
TRAINING_SOURCES = frozenset({"yahoo.finance", "brapi.dev"})

STALE_AFTER_DAYS = 7


@dataclass(frozen=True)
class PriceMetadata:
    source: str
    price_date: date
    ingested_at: datetime | date | None
    close: float | None
    adjusted_close: float | None

    @property
    def age_days(self):
        as_of = date.today()
        return (as_of - self.price_date).days

    @property
    def is_stale(self):
        return self.age_days > STALE_AFTER_DAYS

    @property
    def has_split_dividend_adjustment(self):
        return self.adjusted_close is not None and self.close is not None and self.adjusted_close != self.close


def resolve_price_source(available_sources):
    """Escolhe a fonte canônica de preços conforme a política.

    Retorna a primária se existir; senão a primeira fallback disponível.
    Fontes experimentais nunca vencem as oficiais.
    """
    available = {str(item).strip().lower() for item in available_sources if item}
    policy = SOURCE_POLICY["prices"]
    if policy["primary"] in available:
        return policy["primary"]
    for fallback in policy["fallbacks"]:
        if fallback in available:
            return fallback
    for experimental in policy["experimental"]:
        if experimental in available:
            return experimental
    return None


def is_official_source(source, kind="prices"):
    policy = SOURCE_POLICY.get(kind, SOURCE_POLICY["prices"])
    return source == policy["primary"] or source in policy["fallbacks"]


def assert_consistent_series(sources):
    """A série exibida de um ticker deve usar uma única fonte."""
    unique = {source for source in sources if source}
    if len(unique) > 1:
        raise ValueError("Série de preços mistura fontes inconsistentes.")
    return next(iter(unique)) if unique else None


def describe_price(metadata, as_of=None):
    """Metadados de proveniência/qualidade para API e interface."""
    if metadata is None:
        return {
            "source": None,
            "price_date": None,
            "ingested_at": None,
            "age_days": None,
            "stale": True,
            "close": None,
            "adjusted_close": None,
            "training_price_field": None,
            "quality": "missing",
        }
    price_date = metadata.price_date
    if as_of is None:
        as_of = date.today()
    age_days = (as_of - price_date).days if price_date else None
    stale = age_days is None or age_days > STALE_AFTER_DAYS
    quality = "ok"
    if stale:
        quality = "stale"
    if metadata.close is None:
        quality = "incomplete"
    return {
        "source": metadata.source,
        "price_date": price_date.isoformat() if hasattr(price_date, "isoformat") else str(price_date),
        "ingested_at": (
            metadata.ingested_at.isoformat()
            if hasattr(metadata.ingested_at, "isoformat")
            else (str(metadata.ingested_at) if metadata.ingested_at else None)
        ),
        "age_days": age_days,
        "stale": stale,
        "close": metadata.close,
        "adjusted_close": metadata.adjusted_close,
        # Treino usa ajustado quando existe; exibição usa fechamento.
        "training_price_field": "adjusted_close" if metadata.adjusted_close is not None else "close",
        "display_price_field": "close",
        "quality": quality,
    }


def collection_outcome(imported_count, failed_count):
    """Resultado honesto de coleta: sucesso nunca mascara falha parcial."""
    if imported_count <= 0 and failed_count > 0:
        return {"status": "failed", "imported": 0, "failed": failed_count}
    if failed_count > 0:
        return {"status": "partial", "imported": imported_count, "failed": failed_count}
    return {"status": "succeeded", "imported": imported_count, "failed": 0}
