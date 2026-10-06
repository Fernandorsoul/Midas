"""Objetos que atravessam as fronteiras da aplicação."""
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class PricePoint:
    price_date: date
    close: float
    adjusted_close: float | None
    volume: float | None

@dataclass(frozen=True)
class ImportedStock:
    ticker: str
    name: str
    prices: tuple[PricePoint, ...]
