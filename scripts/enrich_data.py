"""Enriquece dados históricos buscando de múltiplas fontes públicas."""
import sys
from pathlib import Path

# Adicionar diretório pai ao path para encontrar midas_core
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from midas_core.infrastructure.enrichment import enrich_all_stocks, DataEnrichmentError
from midas_core.infrastructure.repositories import PostgresRepository

def main():
    # Ler universo de ativos
    universe_file = Path(__file__).parent.parent / "config" / "stock-universe.txt"
    tickers = []
    for line in universe_file.read_text(encoding="utf-8").splitlines():
        content = line.split("#", 1)[0].strip()
        if content:
            tickers.append(content.strip())
    
    if not tickers:
        print("Nenhum ticker encontrado no universo.")
        return
    
    print(f"Enriquecendo dados de {len(tickers)} ativos...")
    print("Fontes: Yahoo Finance (max), brapi.dev (max)")
    print()
    
    # Enriquecer dados (apenas últimos5 anos)
    enriched = enrich_all_stocks(tickers, period="5y")
    
    if not enriched:
        print("Nenhum ativo foi enriquecido.")
        return
    
    # Salvar no PostgreSQL
    repo = PostgresRepository()
    total_prices = 0
    
    print()
    print("Salvando no PostgreSQL...")
    for stock in enriched:
        try:
            count = repo.save_stocks([stock], "enriched")
            total_prices += count
            print(f"  {stock.ticker}: {count} preços salvos")
        except Exception as e:
            print(f"  {stock.ticker}: ERRO ao salvar - {e}")
    
    print()
    print(f"Concluído: {len(enriched)} ativos, {total_prices} preços totais")

if __name__ == "__main__":
    main()