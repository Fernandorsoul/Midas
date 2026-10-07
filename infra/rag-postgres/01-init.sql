-- Banco de recuperação semântica do Midas.
-- O conteúdo-fonte continua em docs/rag; esta base é apenas um índice reconstruível.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_chunks (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    module text NOT NULL,
    source_path text NOT NULL,
    chunk_index integer NOT NULL CHECK (chunk_index >= 0),
    title text NOT NULL,
    content text NOT NULL,
    content_hash text NOT NULL,
    token_count integer CHECK (token_count >= 0),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    embedding_model text,
    embedding vector,
    search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('portuguese', coalesce(title, '') || ' ' || content)
    ) STORED,
    indexed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (source_path, chunk_index, content_hash)
);

CREATE INDEX rag_chunks_module_idx ON rag_chunks (module);
CREATE INDEX rag_chunks_source_path_idx ON rag_chunks (source_path);
CREATE INDEX rag_chunks_search_idx ON rag_chunks USING gin (search_vector);

COMMENT ON TABLE rag_chunks IS
  'Índice RAG reconstruível. Não armazenar segredos, .env, dumps ou artefatos gerados.';
COMMENT ON COLUMN rag_chunks.embedding IS
  'Embedding sem dimensão fixa; criar índice vetorial apenas após escolher modelo/dimensão.';
