"""Regras puras para transformar preços em variáveis do modelo."""
from datetime import datetime, timezone
import math

import numpy as np

FEATURE_NAMES = ("momentum_6m", "momentum_12m", "volatility", "drawdown")
SUPPORTED_HORIZONS = (12, 24, 36)

def month_end_series(rows):
    """Retorna o último preço ajustado disponível de cada mês."""
    months = {}
    for row in rows:
        price_date = row["price_date"]
        value = row.get("adjusted_close") or row.get("close")
        if value is None or float(value) <= 0:
            continue
        months[(price_date.year, price_date.month)] = (
            datetime(price_date.year, price_date.month, price_date.day, tzinfo=timezone.utc),
            float(value),
        )
    return [months[key] for key in sorted(months)]

def feature_vector(values, index):
    """Calcula variáveis usando exclusivamente observações até index."""
    if index < 12:
        raise ValueError("São necessários pelo menos 13 fechamentos mensais.")
    window = np.asarray(values[index - 12:index + 1], dtype=float)
    returns = np.diff(np.log(window))
    return {
        "momentum_6m": float(values[index] / values[index - 6] - 1),
        "momentum_12m": float(values[index] / values[index - 12] - 1),
        "volatility": float(np.std(returns) * math.sqrt(12)),
        "drawdown": float(values[index] / np.max(window) - 1),
    }

def build_samples(series, ticker, horizon):
    if horizon not in SUPPORTED_HORIZONS:
        raise ValueError("Horizonte inválido.")
    dates = [item[0] for item in series]
    values = [item[1] for item in series]
    return [
        {
            "ticker": ticker,
            "as_of": dates[index],
            "label_end": dates[index + horizon],
            "horizon_months": horizon,
            "features": feature_vector(values, index),
            "target": float(values[index + horizon] / values[index] - 1),
        }
        for index in range(12, len(values) - horizon)
    ]

def latest_features(series):
    return feature_vector([item[1] for item in series], len(series) - 1) if len(series) >= 13 else None
