"""Recuperação híbrida do RAG: filtro de módulo -> texto -> vetor -> limite.

Consulta apenas `docs/rag/` indexados; nunca lê `.env`, dumps ou código bruto.
"""
from __future__ import annotations

import os
import re

import psycopg

from midas_core.domain.rag import (
    DEFAULT_MAX_CHUNKS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    apply_limits,
    embed_text,
    score_hybrid,
)


def connect():
    return psycopg.connect(
        host=os.getenv("RAG_POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("RAG_POSTGRES_PORT", "5433")),
        dbname=os.getenv("RAG_POSTGRES_DB", "midas_rag"),
        user=os.getenv("RAG_POSTGRES_USER", "midas_rag"),
        password=os.environ["RAG_POSTGRES_PASSWORD"],
        row_factory=psycopg.rows.dict_row,
    )


def retrieve(
    query: str,
    module: str | None = None,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    limit_pool: int = 20,
):
    """Busca híbrida. Sem embeddings ainda, degrada para texto puro."""
    if not query or not query.strip():
        raise ValueError("Consulta vazia.")
    max_chunks = max(1, min(int(max_chunks), DEFAULT_MAX_CHUNKS * 2))
    embedding = embed_text(query)
    with connect() as connection:
        sql = """
            SELECT id, module, source_path, chunk_index, title, content, content_hash,
                   embedding_model,
                   ts_rank(search_vector, plainto_tsquery('portuguese', %s)) AS text_score,
                   CASE WHEN embedding IS NULL THEN 0
                        ELSE 1 - (embedding <=> %s::vector)
                   END AS vector_score
            FROM rag_chunks
            WHERE search_vector @@ plainto_tsquery('portuguese', %s)
        """
        params = [query, "[" + ",".join(f"{x:.6f}" for x in embedding) + "]", query]
        if module:
            sql += " AND module = %s"
            params.append(module)
        sql += " ORDER BY text_score DESC LIMIT %s"
        params.append(limit_pool)
        rows = connection.execute(sql, params).fetchall()

        if not rows:
            # Fallback: OR de palavras significativas quando o tsquery não casa.
            words = [w for w in re.findall(r"[0-9a-zA-ZáàâãéêíóôõúüçÁÀÂÃÉÊÍÓÔÕÚÜÇ]+", query) if len(w) >= 3]
            if words:
                like = "%" + words[0][:20] + "%"
                conditions = " OR ".join(["title ILIKE %s", "content ILIKE %s"] * len(words))
                like_params = []
                for word in words[:6]:
                    token = f"%{word[:24]}%"
                    like_params.extend([token, token])
                sql = f"""
                    SELECT id, module, source_path, chunk_index, title, content, content_hash,
                           embedding_model, 0.25 AS text_score,
                           CASE WHEN embedding IS NULL THEN 0
                                ELSE 1 - (embedding <=> %s::vector) END AS vector_score
                    FROM rag_chunks
                    WHERE ({conditions})
                """
                params = ["[" + ",".join(f"{x:.6f}" for x in embedding) + "]"] + like_params
                if module:
                    sql += " AND module = %s"
                    params.append(module)
                sql += " ORDER BY text_score DESC LIMIT %s"
                params.append(limit_pool)
                rows = connection.execute(sql, params).fetchall()

        scored = []
        for row in rows:
            if module and row["module"] != module:
                continue
            scored.append({
                "module": row["module"],
                "source_path": row["source_path"],
                "chunk_index": row["chunk_index"],
                "title": row["title"],
                "content": row["content"],
                "content_hash": row["content_hash"],
                "embedding_model": row["embedding_model"],
                "score": score_hybrid(float(row["text_score"] or 0), float(row["vector_score"] or 0)),
            })
        scored.sort(key=lambda item: item["score"], reverse=True)
        return {
            "query": query,
            "module": module,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "max_chunks": max_chunks,
            "chunks": apply_limits(scored, max_chunks),
            "pool_size": len(scored),
        }


def diagnose():
    """Sanidade do índice sem imprimir segredos."""
    with connect() as connection:
        totals = connection.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(embedding) AS with_embedding,
                      COUNT(DISTINCT module) AS modules
               FROM rag_chunks"""
        ).fetchone()
        return {
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "chunks": totals["total"],
            "chunks_with_embedding": totals["with_embedding"],
            "modules": totals["modules"],
            "default_max_chunks": DEFAULT_MAX_CHUNKS,
        }
