"""Regras puras para transformar preços em variáveis do modelo."""
from datetime import datetime, timezone
import math

import numpy as np

FEATURE_NAMES = (
    "momentum_6m", "momentum_12m", "volatility", "drawdown",
    "rsi_14m", "macd_signal", "sma_ratio_12m", "bb_position", "atr_ratio",
    "net_margin_1y", "net_margin_2y", "roe_1y", "roe_2y"
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

def _adx(values, period=14):
    """Calcula ADX (Average Directional Index)."""
    if len(values) < period * 2:
        return None
    # Simplificação: usamos a direção das variações
    deltas = np.diff(values[-(period * 2):])
    up_moves = np.where(deltas > 0, deltas, 0)
    down_moves = np.where(deltas < 0, -deltas, 0)
    avg_up = np.mean(up_moves[-period:])
    avg_down = np.mean(down_moves[-period:])
    if avg_up + avg_down == 0:
        return 0.0
    dx = abs(avg_up - avg_down) / (avg_up + avg_down) * 100
    return float(dx)

def _stochastic_k(values, period=14):
    """Calcula Stochastic %K."""
    if len(values) < period:
        return None
    window = values[-period:]
    lowest = np.min(window)
    highest = np.max(window)
    if highest == lowest:
        return 50.0
    k = (values[-1] - lowest) / (highest - lowest) * 100
    return float(max(0.0, min(100.0, k)))

def _williams_r(values, period=14):
    """Calcula Williams %R."""
    if len(values) < period:
        return None
    window = values[-period:]
    lowest = np.min(window)
    highest = np.max(window)
    if highest == lowest:
        return -50.0
    r = (highest - values[-1]) / (highest - lowest) * -100
    return float(max(-100.0, min(0.0, r)))

def _obv_slope(values, period=10):
    """Calcula inclinação do OBV (simplificado)."""
    if len(values) < period + 1:
        return None
    # Simplificação: usamos a direção do preço como proxy
    returns = np.diff(values[-(period + 1):])
    up_days = np.sum(returns > 0)
    down_days = np.sum(returns < 0)
    if up_days + down_days == 0:
        return 0.0
    slope = (up_days - down_days) / (up_days + down_days)
    return float(slope)

def _mfi(values, period=14):
    """Calcula MFI (Money Flow Index) simplificado."""
    if len(values) < period + 1:
        return None
    # Simplificação: usamos RSI como proxy
    return _rsi(values, period)

def feature_vector(values, index, fundamentals=None, as_of_date=None):
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
    # Features fundamentalistas históricas
    if fundamentals and as_of_date:
        year = as_of_date.year
        # Margem líquida do ano anterior
        prev_year = fundamentals.get(year - 1, {})
        features["net_margin_1y"] = prev_year.get("net_margin") if prev_year.get("net_margin") is not None else 0.10
        # Margem líquida de2 anos atrás
        prev2_year = fundamentals.get(year - 2, {})
        features["net_margin_2y"] = prev2_year.get("net_margin") if prev2_year.get("net_margin") is not None else 0.10
        # ROE do ano anterior
        features["roe_1y"] = prev_year.get("roe") if prev_year.get("roe") is not None else 0.15
        # ROE de2 anos atrás
        features["roe_2y"] = prev2_year.get("roe") if prev2_year.get("roe") is not None else 0.15
    else:
        features["net_margin_1y"] = 0.10  # Neutro se não disponível
        features["net_margin_2y"] = 0.10  # Neutro se não disponível
        features["roe_1y"] = 0.15  # Neutro se não disponível
        features["roe_2y"] = 0.15  # Neutro se não disponível
    return features

def build_samples(series, ticker, horizon, fundamentals=None):
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
            "features": feature_vector(values, index, fundamentals, dates[index]),
            "target": float(values[index + horizon] / values[index] - 1),
        }
        for index in range(12, len(values) - horizon)
    ]

def latest_features(series, fundamentals=None):
    dates = [item[0] for item in series]
    return feature_vector([item[1] for item in series], len(series) - 1, fundamentals, dates[-1] if dates else None) if len(series) >= 13 else None
