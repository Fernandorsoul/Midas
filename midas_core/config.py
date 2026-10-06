"""Configuração tipada carregada do ambiente."""
from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

@dataclass(frozen=True)
class Settings:
    postgres_host: str
    postgres_port: int
    postgres_password: str
    mongo_host: str
    mongo_port: int
    mongo_password: str
    brapi_token: str | None
    http_host: str
    http_port: int

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            postgres_host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            postgres_port=int(os.getenv("POSTGRES_PORT", "5432")),
            postgres_password=os.environ["POSTGRES_APP_PASSWORD"],
            mongo_host=os.getenv("MONGO_HOST", "127.0.0.1"),
            mongo_port=int(os.getenv("MONGO_PORT", "27017")),
            mongo_password=os.environ["MONGO_APP_PASSWORD"],
            brapi_token=os.getenv("BRAPI_TOKEN"),
            http_host=os.getenv("HTTP_HOST", "127.0.0.1"),
            http_port=int(os.getenv("PORT", "8000")),
        )
