"""Screener de oportunidade: score transparente, sem recomendação de compra.

Critérios explícitos e pesos fixos. Cada ativo recebe score em [0, 1] e
uma explicação dos fatores. Linguagem de pesquisa: não é sinal de trade.
"""
from __future__ import annotations

from dataclasses import dataclass

DISCLAIMER = (
    "Ferramenta de pesquisa e triagem. Não é recomendação de compra/venda "
    "nem garantia de retorno. Confira fonte, data e sua própria análise antes de decidir."
)

# Pesos devem somar 1.0
CRITERIA_WEIGHTS = {
    "momentum": 0.30,
    "drawdown": 0.20,
    "volatility": 0.20,
    "liquidity": 0.15,
    "data_quality": 0.15,
}


@dataclass(frozen=True)
class CriterionScore:
    name: str
    weight: float
    raw: float
    normalized: float
    note: str


def _clamp(value: float, low=0.0, high=1.0) -> float:
    return max(low, min(high, float(value)))


def score_momentum(momentum_12m: float | None) -> CriterionScore:
    """Momentum 12m positivo pontua mais; sem dado, neutro-baixo."""
    if momentum_12m is None:
        return CriterionScore("momentum", CRITERIA_WEIGHTS["momentum"], None, 0.3, "momentum indisponível")
    raw = float(momentum_12m)
    normalized = _clamp(0.5 + raw / 2)  # +100% -> 1.0; -100% -> 0.0
    note = f"momentum 12m {raw * 100:.1f}%"
    return CriterionScore("momentum", CRITERIA_WEIGHTS["momentum"], raw, normalized, note)


def score_drawdown(drawdown: float | None) -> CriterionScore:
    """Drawdown menos profundo pontua mais (risco de queda menor)."""
    if drawdown is None:
        return CriterionScore("drawdown", CRITERIA_WEIGHTS["drawdown"], None, 0.35, "drawdown indisponível")
    raw = float(drawdown)  # tipicamente <= 0
    normalized = _clamp(1.0 + raw)  # 0 -> 1.0; -1 -> 0.0
    note = f"drawdown {raw * 100:.1f}%"
    return CriterionScore("drawdown", CRITERIA_WEIGHTS["drawdown"], raw, normalized, note)


def score_volatility(volatility: float | None) -> CriterionScore:
    """Volatilidade moderada é preferida: muito baixa ou muito alta pontua menos."""
    if volatility is None:
        return CriterionScore("volatility", CRITERIA_WEIGHTS["volatility"], None, 0.35, "volatilidade indisponível")
    raw = float(volatility)
    # pico em ~15% a.a.; 0% -> 0.3; 15% -> 1.0; 45%+ -> ~0.2
    normalized = _clamp(1.0 - abs(raw - 0.15) / 0.45)
    note = f"volatilidade {raw * 100:.1f}%"
    return CriterionScore("volatility", CRITERIA_WEIGHTS["volatility"], raw, normalized, note)


def score_liquidity(volume: float | None, avg_volume: float | None = None) -> CriterionScore:
    """Volume simples: sem dado pontua baixo; acima de 1e6 pontua cheio."""
    if volume is None or volume <= 0:
        return CriterionScore("liquidity", CRITERIA_WEIGHTS["liquidity"], None, 0.2, "volume indisponível")
    raw = float(volume)
    # escala log: 1e4 -> 0.2; 1e6 -> ~1.0
    import math
    normalized = _clamp((math.log10(raw) - 4) / 2)
    note = f"volume {raw:,.0f}"
    return CriterionScore("liquidity", CRITERIA_WEIGHTS["liquidity"], raw, normalized, note)


def score_data_quality(source: str | None, price_date: str | None, stale: bool | None) -> CriterionScore:
    """Fonte oficial e preço fresco pontuam melhor."""
    official = source in ("yahoo.finance", "brapi.dev")
    if source is None or price_date is None:
        return CriterionScore("data_quality", CRITERIA_WEIGHTS["data_quality"], None, 0.2, "dados incompletos")
    if stale:
        normalized = 0.45
        note = f"preço atrasado ({source}, {price_date})"
    elif official:
        normalized = 1.0
        note = f"fonte oficial ({source}, {price_date})"
    else:
        normalized = 0.6
        note = f"fonte experimental ({source}, {price_date})"
    return CriterionScore("data_quality", CRITERIA_WEIGHTS["data_quality"], None, normalized, note)


def build_score(features: dict) -> tuple[float, list[CriterionScore]]:
    """Calcula score composto e fatores explicativos."""
    factors = [
        score_momentum(features.get("momentum_12m")),
        score_drawdown(features.get("drawdown")),
        score_volatility(features.get("volatility")),
        score_liquidity(features.get("volume"), features.get("avg_volume")),
        score_data_quality(
            features.get("source"),
            features.get("price_date"),
            features.get("stale"),
        ),
    ]
    score = sum(f.weight * f.normalized for f in factors)
    return round(score, 4), factors


def explain(factors: list[CriterionScore]) -> dict:
    ordered = sorted(factors, key=lambda f: f.weight * f.normalized, reverse=True)
    return {
        "criteria": [
            {
                "name": f.name,
                "weight": f.weight,
                "normalized": round(f.normalized, 4),
                "contribution": round(f.weight * f.normalized, 4),
                "note": f.note,
            }
            for f in ordered
        ],
        "top_drivers": [f.name for f in ordered[:3]],
        "disclaimer": DISCLAIMER,
    }


def screen_assets(assets, min_volume=None, category=None, sector=None, query=None, limit=20):
    """Filtra, pontua e ordena ativos. `assets` é lista de dicts com features."""
    results = []
    for asset in assets:
        if category and asset.get("category") != category:
            continue
        if sector and asset.get("sector") != sector:
            continue
        if query:
            q = query.lower()
            if q not in (asset.get("ticker") or "").lower() and q not in (asset.get("name") or "").lower():
                continue
        volume = asset.get("volume")
        if min_volume is not None and (volume is None or volume < min_volume):
            continue
        features = {
            "momentum_12m": asset.get("momentum_12m"),
            "drawdown": asset.get("drawdown"),
            "volatility": asset.get("volatility"),
            "volume": volume,
            "source": asset.get("source"),
            "price_date": asset.get("price_date"),
            "stale": asset.get("stale"),
        }
        score, factors = build_score(features)
        results.append({
            "ticker": asset.get("ticker"),
            "name": asset.get("name"),
            "category": asset.get("category"),
            "sector": asset.get("sector"),
            "price": asset.get("price"),
            "price_date": asset.get("price_date"),
            "source": asset.get("source"),
            "score": score,
            "explanation": explain(factors),
        })
    results.sort(key=lambda item: (-item["score"], item.get("ticker") or ""))
    limit = max(1, min(int(limit or 20), 50))
    return {
        "results": results[:limit],
        "total_scored": len(results),
        "criteria_weights": dict(CRITERIA_WEIGHTS),
        "disclaimer": DISCLAIMER,
    }
