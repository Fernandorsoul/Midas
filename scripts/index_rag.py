"""Indexa a documentação RAG modular no PostgreSQL com pgvector.

O script não gera embeddings: ele atualiza o índice textual e os metadados dos
documentos-fonte. Embeddings devem ser incluídos por uma etapa explícita depois
da escolha do modelo, sem enviar arquivos fora de docs/rag para provedores.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re

import psycopg
from psycopg.types.json import Jsonb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAG_ROOT = PROJECT_ROOT / "docs" / "rag"
HEADING = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def split_sections(source_path: Path):
    """Produz chunks autocontidos por título Markdown."""
    text = source_path.read_text(encoding="utf-8").strip()
    matches = list(HEADING.finditer(text))
    if not matches:
        return [(source_path.stem, text)] if text else []
    chunks = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.start():end].strip()
        if content:
            chunks.append((match.group(2).strip(), content))
    return chunks


def module_for(path: Path) -> str:
    prefix = path.name.split("-", 1)[0]
    return {
        "00": "router", "01": "product", "02": "market-data",
        "03": "portfolio", "04": "quant-research", "05": "web-ui",
        "06": "api-jobs", "07": "storage-security", "08": "roadmap",
        "09": "quality", "10": "codebase-catalog",
    }.get(prefix, "rag-meta")


def connect():
    return psycopg.connect(
        host=os.getenv("RAG_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("RAG_POSTGRES_PORT", "5433")),
        dbname=os.getenv("RAG_POSTGRES_DB", "midas_rag"),
        user=os.getenv("RAG_POSTGRES_USER", "midas_rag"),
        password=os.environ["RAG_POSTGRES_PASSWORD"],
    )


def index_documents(check_only: bool = False):
    documents = sorted(RAG_ROOT.glob("*.md"))
    if not documents:
        raise ValueError("Nenhum documento encontrado em docs/rag.")
    documents_chunks = {}
    for document in documents:
        relative = document.relative_to(PROJECT_ROOT).as_posix()
        document_chunks = []
        for index, (title, content) in enumerate(split_sections(document)):
            document_chunks.append((
                module_for(document), relative, index, title, content,
                hashlib.sha256(content.encode("utf-8")).hexdigest(),
                len(content.split()), Jsonb({"kind": "rag-document"}),
            ))
        documents_chunks[relative] = document_chunks
    if check_only:
        return sum(len(chunks) for chunks in documents_chunks.values())

    indexed = 0
    with connect() as connection:
        with connection.cursor() as cursor:
            for source_path, chunks in documents_chunks.items():
                cursor.execute(
                    "SELECT content_hash FROM rag_chunks WHERE source_path=%s ORDER BY chunk_index",
                    (source_path,),
                )
                current_hashes = [row[0] for row in cursor.fetchall()]
                expected_hashes = [chunk[5] for chunk in chunks]
                if current_hashes == expected_hashes:
                    continue
                cursor.execute("DELETE FROM rag_chunks WHERE source_path=%s", (source_path,))
                if chunks:
                    cursor.executemany(
                        """INSERT INTO rag_chunks(
                            module,source_path,chunk_index,title,content,content_hash,
                            token_count,metadata
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                        chunks,
                    )
                indexed += len(chunks)
    return indexed


def main():
    parser = argparse.ArgumentParser(description="Indexa somente a documentação RAG modular.")
    parser.add_argument("--check", action="store_true", help="Valida os chunks sem conectar ao banco.")
    arguments = parser.parse_args()
    count = index_documents(check_only=arguments.check)
    action = "Chunks validados" if arguments.check else "Chunks indexados ou atualizados"
    print(f"{action}: {count}")


if __name__ == "__main__":
    main()
