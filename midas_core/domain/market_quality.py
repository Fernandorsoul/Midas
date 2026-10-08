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


# --- Fallback de fontes e classificação de falhas ---

ERROR_TIMEOUT = "timeout"
ERROR_RATE_LIMIT = "rate_limit"
ERROR_AUTH = "auth"
ERROR_NOT_FOUND = "not_found"
ERROR_INVALID = "invalid"
ERROR_UNKNOWN = "unknown"

# Erros que justificam tentar a próxima fonte.
RETRYABLE_ERROR_KINDS = frozenset({ERROR_TIMEOUT, ERROR_RATE_LIMIT, ERROR_UNKNOWN})


def classify_fetch_error(message: str) -> str:
    """Classifica falha de coleta sem expor token/URL sensível."""
    text = (message or "").lower()
    if "429" in text or "rate" in text or "quota" in text or "retry-after" in text:
        return ERROR_RATE_LIMIT
    if "timeout" in text or "timed out" in text or "tempo esgotado" in text or "conectar" in text:
        return ERROR_TIMEOUT
    if "401" in text or "403" in text or "token" in text or "acesso" in text:
        return ERROR_AUTH
    if "404" in text or "nenhum dado" in text or "não retornou" in text or "nao retornou" in text:
        return ERROR_NOT_FOUND
    if "json" in text or "formato" in text or "inesperado" in text:
        return ERROR_INVALID
    return ERROR_UNKNOWN


def should_try_fallback(error_kind: str) -> bool:
    """Fallback quando a falha é transitória/limite; não para ticker inexistente."""
    return error_kind in RETRYABLE_ERROR_KINDS or error_kind == ERROR_INVALID


def next_price_source(already_tried) -> str | None:
    """Próxima fonte oficial de preços ainda não tentada (ordem da política)."""
    policy = SOURCE_POLICY["prices"]
    chain = (policy["primary"],) + tuple(policy["fallbacks"])
    tried = set(already_tried or ())
    for source in chain:
        if source not in tried:
            return source
    return None


def fallback_report(ticker: str, attempts):
    """Resumo seguro da cadeia de fallback por ativo.

    `attempts` = lista de dicts: {source, ok, error_kind, message}.
    """
    used = next((a["source"] for a in attempts if a.get("ok")), None)
    errors = [
        {"source": a["source"], "kind": a.get("error_kind") or ERROR_UNKNOWN,
         "message": (a.get("message") or "")[:200]}
        for a in attempts if not a.get("ok")
    ]
    return {
        "ticker": ticker,
        "used_source": used,
        "attempts": errors,
        "status": "succeeded" if used else "failed",
    }
