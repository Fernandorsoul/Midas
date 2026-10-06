"""Pontos de entrada de linha de comando."""
import argparse
from pathlib import Path

from midas_core.application.datasets import publish_dataset
from midas_core.application.market_import import import_stocks
from midas_core.application.training import train
from midas_core.infrastructure.brapi import VALID_RANGES

def _tickers_from_file(path):
    tickers = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        content = line.split("#", 1)[0].strip()
        if content:
            tickers.extend(part.strip() for part in content.split(",") if part.strip())
    return tickers

def import_market_main():
    parser = argparse.ArgumentParser(description="Importa ações brasileiras da API pública brapi.dev.")
    parser.add_argument("tickers", nargs="*", help="Códigos da B3, por exemplo PETR4 VALE3")
    parser.add_argument("--file", help="Arquivo com um ticker por linha")
    parser.add_argument("--range", dest="price_range", choices=sorted(VALID_RANGES), default="10y")
    arguments = parser.parse_args()
    tickers = list(arguments.tickers)
    if arguments.file:
        tickers.extend(_tickers_from_file(arguments.file))
    if not tickers:
        parser.error("informe tickers ou use --file")
    result = import_stocks(tickers, arguments.price_range)
    print(
        f"Importação concluída: {result['assets']} ativo(s), "
        f"{result['prices']} cotação(ões), fonte {result['source']}."
    )

def dataset_main():
    parser = argparse.ArgumentParser(description="Cria dataset mensal e treina o modelo do Midas.")
    parser.add_argument("--horizon", type=int, action="append", choices=(12, 24, 36))
    arguments = parser.parse_args()
    horizons = tuple(arguments.horizon or [12])
    dataset_id, sample_count = publish_dataset(horizons)
    print(f"Dataset publicado: {dataset_id} ({sample_count} amostras)")
    for horizon in horizons:
        print(f"Experimento {horizon} meses:", train(dataset_id, horizon))

def training_main():
    parser = argparse.ArgumentParser(description="Treina um snapshot existente.")
    parser.add_argument("dataset_id")
    parser.add_argument("--horizon", type=int, choices=(12, 24, 36), default=12)
    arguments = parser.parse_args()
    print("Experimento salvo:", train(arguments.dataset_id, arguments.horizon))
