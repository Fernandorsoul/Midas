"""Contrato de embeddings e recuperação híbrida do RAG.

Modelo registrado: `local-hash-256` — embedding determinístico de bag-of-words
hasheado em 256 dimensões. Não envia conteúdo a provedores externos e não usa
segredos. A dimensão é fixa para permitir índice vetorial pgvector.

Família de consulta: filtro de módulo -> busca textual -> similaridade vetorial
-> limite de chunks (padrão 3).
"""
from __future__ import annotations

import hashlib
import math
import re

EMBEDDING_MODEL = "local-hash-256"
EMBEDDING_DIM = 256
DEFAULT_MAX_CHUNKS = 3

_TOKEN = re.compile(r"[a-z0-9áàâãéêíóôõúüç]+", re.IGNORECASE)
_STOP = frozenset({
    "a", "o", "as", "os", "um", "uma", "de", "do", "da", "dos", "das",
    "e", "em", "no", "na", "nos", "nas", "para", "por", "com", "sem",
    "que", "se", "não", "nao", "ou", "ao", "à", "the", "and", "of",
})


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in _STOP]


def embed_text(text: str) -> list[float]:
    """Embedding determinístico L2-normalizado (dimensão EMBEDDING_DIM)."""
    vector = [0.0] * EMBEDDING_DIM
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector))
    if norm > 0:
        vector = [v / norm for v in vector]
    return vector


def cosine(a, b) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def score_hybrid(text_score: float, vector_score: float, text_weight: float = 0.45) -> float:
    """Combina relevância textual e vetorial (ambas em [0,1] aprox.)."""
    return text_weight * max(0.0, min(1.0, text_score)) + (1.0 - text_weight) * max(0.0, min(1.0, vector_score))


def apply_limits(chunks, max_chunks: int = DEFAULT_MAX_CHUNKS):
    """Corta o resultado ao limite e garante fonte/caminho em cada chunk."""
    limited = list(chunks)[: max(1, int(max_chunks))]
    normalized = []
    for chunk in limited:
        normalized.append({
            "module": chunk.get("module"),
            "source_path": chunk.get("source_path"),
            "chunk_index": chunk.get("chunk_index"),
            "title": chunk.get("title"),
            "score": chunk.get("score"),
            "content": chunk.get("content"),
        })
    return normalized
