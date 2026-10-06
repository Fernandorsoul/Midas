"""Compatibilidade com os antigos imports de persistência."""
from midas_core.application.analysis import build_report as report, set_favorite
from midas_core.infrastructure.database import connect_mongo as mongo, connect_postgres as postgres

__all__ = ["mongo", "postgres", "report", "set_favorite"]
