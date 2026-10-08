"""Consulta e diagnóstico do RAG híbrido (sem imprimir segredos).

Uso:
  python scripts/query_rag.py "como calcula P&L" [--module portfolio] [--max-chunks 3]
  python scripts/query_rag.py --diagnose
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from midas_core.application.rag_retrieval import diagnose, retrieve  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recuperação híbrida do RAG do Midas")
    parser.add_argument("query", nargs="?", help="Consulta em linguagem natural")
    parser.add_argument("--module", help="Filtro de módulo (ex.: portfolio)")
    parser.add_argument("--max-chunks", type=int, default=3, help="Máximo de chunks (padrão 3)")
    parser.add_argument("--diagnose", action="store_true", help="Mostra estado do índice")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    args = parser.parse_args(argv)

    if args.diagnose:
        info = diagnose()
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    if not args.query:
        parser.error("Informe uma consulta ou --diagnose.")

    result = retrieve(args.query, module=args.module, max_chunks=args.max_chunks)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Modelo: {result['embedding_model']} (dim {result['embedding_dim']})")
    print(f"Pool: {result['pool_size']} · limite: {result['max_chunks']}")
    if not result["chunks"]:
        print("Nenhum chunk encontrado.")
        return 0
    for index, chunk in enumerate(result["chunks"], 1):
        print(f"\n[{index}] score={chunk['score']:.3f} · {chunk['module']} · {chunk['source_path']}#{chunk['chunk_index']}")
        print(f"    {chunk['title']}")
        preview = " ".join((chunk["content"] or "").split())[:220]
        print(f"    {preview}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
