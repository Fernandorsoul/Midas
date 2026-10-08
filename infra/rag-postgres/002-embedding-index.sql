-- Índice vetorial para o modelo local-hash-256 (dimensão 256).
-- Só faz sentido após a dimensão estar fixa no contrato de embeddings.
BEGIN;
ALTER TABLE rag_chunks ALTER COLUMN embedding TYPE vector(256)
    USING embedding::vector(256);
CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx
    ON rag_chunks USING hnsw (embedding vector_cosine_ops);
COMMIT;
