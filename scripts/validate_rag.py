"""Validação rápida do RAG: arquivos do manifesto existem e README/roteador ok.

Uso: python scripts/validate_rag.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = ROOT / "docs" / "rag"


def main():
    manifest_path = RAG_ROOT / "rag-manifest.json"
    if not manifest_path.exists():
        print("ERRO: rag-manifest.json ausente.", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []
    entrypoint = RAG_ROOT / manifest.get("entrypoint", "00-router.md")
    if not entrypoint.exists():
        errors.append(f"Roteador ausente: {entrypoint.name}")
    for module in manifest.get("modules", []):
        path = RAG_ROOT / module.get("path", "")
        if not path.exists():
            errors.append(f"Módulo ausente: {module.get('path')}")
        if not module.get("keywords"):
            errors.append(f"Módulo sem keywords: {module.get('id')}")
    if errors:
        for error in errors:
            print(f"ERRO: {error}", file=sys.stderr)
        return 1
    print(f"RAG OK: {len(manifest.get('modules', []))} módulos + roteador.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
