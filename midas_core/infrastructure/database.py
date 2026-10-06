"""Fábricas de conexão; nenhum SQL ou regra de negócio vive aqui."""
import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient

from midas_core.config import Settings

def connect_postgres(settings=None):
    settings = settings or Settings.from_environment()
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname="midas",
        user="midas_app",
        password=settings.postgres_password,
        connect_timeout=5,
        row_factory=dict_row,
    )

def connect_mongo(settings=None):
    settings = settings or Settings.from_environment()
    return MongoClient(
        host=settings.mongo_host,
        port=settings.mongo_port,
        username="midas_app",
        password=settings.mongo_password,
        authSource="midas_training",
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )
