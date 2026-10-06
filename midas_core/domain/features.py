"""Regras puras para transformar preços em variáveis do modelo."""
from datetime import datetime, timezone
import math

import numpy as np

FEATURE_NAMES = (
    "momentum_6m", "momentum_12m", "volatility", "drawdown",
    "rsi_14m", "macd_signal", "sma_ratio_12m", "bb_position", "atr_ratio"
)
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

def _ema(values, period):
    """Calcula EMA (Exponential Moving Average)."""
    if len(values) < period:
        return None
    multiplier = 2.0 / (period + 1)
    ema = np.mean(values[:period])
    for value in values[period:]:
        ema = (value - ema) * multiplier + ema
    return ema

def _rsi(values, period=14):
    """Calcula RSI (Relative Strength Index)."""
    if len(values) < period + 1:
        return None
    deltas = np.diff(values[-(period + 1):])
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)
    avg_gain = np.mean(gains)
    avg_loss = np.mean(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return float(100.0 - (100.0 / (1.0 + rs)))

def _macd_signal(values):
    """Calcula MACD Signal (MACD Line - Signal Line)."""
    if len(values) < 35:  # Precisa de26 +9 períodos
        return None
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    if ema12 is None or ema26 is None:
        return None
    macd_line = ema12 - ema26
    # Para calcular a Signal Line, precisaríamos do histórico do MACD
    # Simplificação: retornamos apenas o MACD Line normalizado
    return float(macd_line / values[-1])

def _sma(values, period):
    """Calcula SMA (Simple Moving Average)."""
    if len(values) < period:
        return None
    return float(np.mean(values[-period:]))

def _bollinger_position(values, period=20, num_std=2):
    """Calcula posição dentro das Bandas de Bollinger (0 a 1)."""
    if len(values) < period:
        return None
    sma = np.mean(values[-period:])
    std = np.std(values[-period:])
    upper = sma + num_std * std
    lower = sma - num_std * std
    if upper == lower:
        return 0.5
    position = (values[-1] - lower) / (upper - lower)
    return float(max(0.0, min(1.0, position)))

def _atr_ratio(values, period=14):
    """Calcula ATR (Average True Range) normalizado pelo preço."""
    if len(values) < period + 1:
        return None
    # Para dados mensais, usamos a variação absoluta
    changes = np.abs(np.diff(values[-(period + 1):]))
    atr = np.mean(changes)
    return float(atr / values[-1]) if values[-1] > 0 else None

def feature_vector(values, index):
    """Calcula variáveis usando exclusivamente observações até index."""
    if index < 12:
        raise ValueError("São necessários pelo menos 13 fechamentos mensais.")
    window = np.asarray(values[index - 12:index + 1], dtype=float)
    returns = np.diff(np.log(window))
    features = {
        "momentum_6m": float(values[index] / values[index - 6] - 1),
        "momentum_12m": float(values[index] / values[index - 12] - 1),
        "volatility": float(np.std(returns) * math.sqrt(12)),
        "drawdown": float(values[index] / np.max(window) - 1),
    }
    # RSI com14 períodos (requer mais dados)
    rsi = _rsi(values[:index + 1], 14)
    features["rsi_14m"] = rsi if rsi is not None else 50.0  # Neutro se não disponível
    # MACD Signal
    macd = _macd_signal(values[:index + 1])
    features["macd_signal"] = macd if macd is not None else 0.0  # Neutro se não disponível
    # SMA ratio (preço atual / SMA12m)
    sma = _sma(values[:index + 1], 12)
    features["sma_ratio_12m"] = float(values[index] / sma) if sma and sma > 0 else 1.0
    # Bollinger Bands position
    bb = _bollinger_position(values[:index + 1], 20)
    features["bb_position"] = bb if bb is not None else 0.5  # Neutro se não disponível
    # ATR ratio
    atr = _atr_ratio(values[:index + 1], 14)
    features["atr_ratio"] = atr if atr is not None else 0.05  # Neutro se não disponível
    return features

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
