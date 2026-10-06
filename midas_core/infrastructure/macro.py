"""Busca dados macroeconômicos de APIs públicas brasileiras com cache."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# APIs públicas do Banco Central do Brasil
BCB_BASE = "https://api.bcb.gov.br/dados/serie/bcdata.sgs"

# Códigos de séries do BCB
BCB_SERIES = {
    "selic": 432,           # Taxa Selic acumulada no mês (% a.a.)
    "ipca": 433,            # IPCA - Variação mensal (%)
    "ipca_12m": 13522,      # IPCA - Variação acumulada em 12 meses (%)
    "dolar": 1,             # Taxa de câmbio USD/BRL (comercial)
    "pib_mensal": 24364,    # PIB mensal (R$ milhões)
    "desemprego": 24369,    # Taxa de desemprego (%)
}

# Cache de dados macroeconômicos
CACHE_DIR = Path(__file__).parent.parent.parent / ".cache" / "macro"
CACHE_TTL = 86400  # 24 horas

class MacroDataError(RuntimeError):
    pass

def _get_cache_path(series_code: int) -> Path:
    """Retorna o caminho do cache para uma série."""
    return CACHE_DIR / f"{series_code}.json"

def _load_from_cache(series_code: int) -> list[dict] | None:
    """Carrega dados do cache se existir e não estiver expirado."""
    cache_path = _get_cache_path(series_code)
    if not cache_path.exists():
        return None
    
    # Verificar se o cache não expirou
    mtime = cache_path.stat().st_mtime
    if time.time() - mtime > CACHE_TTL:
        return None
    
    try:
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

def _save_to_cache(series_code: int, data: list[dict]):
    """Salva dados no cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = _get_cache_path(series_code)
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    except IOError:
        pass  # Falha ao salvar cache não é crítica

def fetch_bcb_series(series_code: int, start_date: str = "01/01/2020") -> list[dict]:
    """Busca série temporal do Banco Central do Brasil com cache."""
    # Tentar carregar do cache primeiro
    cached = _load_from_cache(series_code)
    if cached is not None:
        return cached
    
    url = f"{BCB_BASE}.{series_code}/dados?formato=json&dataInicial={start_date}"
    headers = {"User-Agent": "Midas/0.3"}
    
    try:
        with urlopen(Request(url, headers=headers), timeout=30) as response:
            data = json.load(response)
    except Exception as e:
        raise MacroDataError(f"Erro ao buscar série {series_code} do BCB: {e}")
    
    if not isinstance(data, list):
        raise MacroDataError(f"BCB: formato inesperado para série {series_code}")
    
    # Salvar no cache
    _save_to_cache(series_code, data)
    
    return data

def fetch_selic() -> list[dict]:
    """Busca taxa Selic acumulada no mês."""
    return fetch_bcb_series(BCB_SERIES["selic"])

def fetch_ipca() -> list[dict]:
    """Busca IPCA - Variação mensal."""
    return fetch_bcb_series(BCB_SERIES["ipca"])

def fetch_ipca_12m() -> list[dict]:
    """Busca IPCA - Variação acumulada em 12 meses."""
    return fetch_bcb_series(BCB_SERIES["ipca_12m"])

def fetch_dollar_rate() -> list[dict]:
    """Busca taxa de câmbio USD/BRL."""
    return fetch_bcb_series(BCB_SERIES["dolar"])

def fetch_unemployment() -> list[dict]:
    """Busca taxa de desemprego."""
    return fetch_bcb_series(BCB_SERIES["desemprego"])

def get_macro_features(as_of_date: datetime) -> dict:
    """Retorna features macroeconômicas para uma data específica."""
    features = {}
    
    # Buscar dados do BCB
    try:
        # Selic
        selic_data = fetch_selic()
        if selic_data:
            # Usar o valor mais próximo da data
            selic_value = _find_closest_value(selic_data, as_of_date)
            features["selic"] = selic_value if selic_value is not None else 10.0
        
        # IPCA 12 meses
        ipca_data = fetch_ipca_12m()
        if ipca_data:
            ipca_value = _find_closest_value(ipca_data, as_of_date)
            features["ipca_12m"] = ipca_value if ipca_value is not None else 5.0
        
        # Dólar
        dolar_data = fetch_dollar_rate()
        if dolar_data:
            dolar_value = _find_closest_value(dolar_data, as_of_date)
            features["dolar_brl"] = dolar_value if dolar_value is not None else 5.0
        
        # Desemprego
        desemprego_data = fetch_unemployment()
        if desemprego_data:
            desemprego_value = _find_closest_value(desemprego_data, as_of_date)
            features["desemprego"] = desemprego_value if desemprego_value is not None else 10.0
    
    except MacroDataError:
        # Valores padrão se a API falhar
        features["selic"] = 10.0
        features["ipca_12m"] = 5.0
        features["dolar_brl"] = 5.0
        features["desemprego"] = 10.0
    
    return features

def _find_closest_value(data: list[dict], target_date: datetime) -> float | None:
    """Encontra o valor mais próximo de uma data na série temporal."""
    target_str = target_date.strftime("%d/%m/%Y")
    
    # Converter para datetime para comparação
    target_dt = datetime.strptime(target_str, "%d/%m/%Y")
    
    closest_value = None
    closest_diff = float('inf')
    
    for item in data:
        try:
            item_date = item.get("data")
            item_value = item.get("valor")
            
            if not item_date or item_value is None:
                continue
            
            # Converter data do formato DD/MM/YYYY
            item_dt = datetime.strptime(item_date, "%d/%m/%Y")
            diff = abs((item_dt - target_dt).days)
            
            if diff < closest_diff:
                closest_diff = diff
                closest_value = float(item_value)
        
        except (ValueError, TypeError):
            continue
    
    return closest_value