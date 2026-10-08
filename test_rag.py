import unittest
from unittest.mock import MagicMock, patch

from midas_core.domain.rag import (
    DEFAULT_MAX_CHUNKS,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    apply_limits,
    cosine,
    embed_text,
    score_hybrid,
)


class EmbeddingTests(unittest.TestCase):
    def test_model_and_dimension(self):
        self.assertEqual(EMBEDDING_MODEL, "local-hash-256")
        self.assertEqual(EMBEDDING_DIM, 256)

    def test_embedding_is_deterministic_and_normalized(self):
        a = embed_text("posição e preço médio da carteira")
        b = embed_text("posição e preço médio da carteira")
        self.assertEqual(a, b)
        self.assertEqual(len(a), EMBEDDING_DIM)
        norm = sum(x * x for x in a) ** 0.5
        self.assertAlmostEqual(norm, 1.0, places=5)

    def test_different_texts_differ(self):
        a = embed_text("regras de autenticação e sessão")
        b = embed_text("dashboard patrimonial e benchmarks")
        self.assertNotEqual(a, b)
        self.assertLess(cosine(a, b), 0.99)

    def test_cosine_self_is_one(self):
        v = embed_text("livro de operações")
        self.assertAlmostEqual(cosine(v, v), 1.0, places=6)

    def test_score_hybrid_combines_signals(self):
        self.assertAlmostEqual(score_hybrid(1.0, 1.0), 1.0, places=6)
        self.assertLess(score_hybrid(1.0, 0.0), 1.0)
        self.assertGreater(score_hybrid(0.8, 0.8), score_hybrid(0.2, 0.2))


class LimitTests(unittest.TestCase):
    def test_default_limit_is_three(self):
        self.assertEqual(DEFAULT_MAX_CHUNKS, 3)

    def test_apply_limits_caps_and_keeps_source(self):
        chunks = [
            {"module": "portfolio", "source_path": "docs/rag/03-portfolio.md",
             "chunk_index": i, "title": f"t{i}", "score": 1 - i * 0.1, "content": "x"}
            for i in range(10)
        ]
        limited = apply_limits(chunks, 3)
        self.assertEqual(len(limited), 3)
        for chunk in limited:
            self.assertIn("source_path", chunk)
            self.assertIn("module", chunk)

    def test_apply_limits_never_returns_zero(self):
        self.assertEqual(len(apply_limits([], 0)), 0)
        self.assertEqual(len(apply_limits([{"module": "m", "source_path": "p", "chunk_index": 0, "title": "t", "score": 1, "content": "c"}], 0)), 1)


class RetrievalContractTests(unittest.TestCase):
    def test_retrieve_without_db_fails_closed_on_empty_query(self):
        from midas_core.application import rag_retrieval
        with self.assertRaises(ValueError):
            rag_retrieval.retrieve("   ")

    def test_query_script_exists(self):
        from pathlib import Path
        self.assertTrue(Path("scripts/query_rag.py").exists())
        self.assertTrue(Path("infra/rag-postgres/002-embedding-index.sql").exists())


class HybridQueryMockTests(unittest.TestCase):
    def test_retrieve_prefers_module_and_limits_chunks(self):
        from midas_core.application import rag_retrieval

        rows = [
            {
                "module": "portfolio", "source_path": "docs/rag/03-portfolio.md",
                "chunk_index": 0, "title": "Posição", "content": "preço médio e P&L",
                "content_hash": "abc", "embedding_model": "local-hash-256",
                "text_score": 0.9, "vector_score": 0.8,
            },
            {
                "module": "portfolio", "source_path": "docs/rag/03-portfolio.md",
                "chunk_index": 1, "title": "Operações", "content": "compra e venda",
                "content_hash": "def", "embedding_model": "local-hash-256",
                "text_score": 0.5, "vector_score": 0.4,
            },
            {
                "module": "web-ui", "source_path": "docs/rag/05-web-ui.md",
                "chunk_index": 0, "title": "UI", "content": "toasts",
                "content_hash": "ghi", "embedding_model": "local-hash-256",
                "text_score": 0.2, "vector_score": 0.1,
            },
        ]
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = rows
        connection.__enter__ = lambda s: connection
        connection.__exit__ = lambda s, *a: False

        with patch.object(rag_retrieval, "connect", return_value=connection):
            result = rag_retrieval.retrieve("preço médio", module="portfolio", max_chunks=3)

        self.assertLessEqual(len(result["chunks"]), 3)
        self.assertEqual(result["embedding_model"], EMBEDDING_MODEL)
        self.assertTrue(all(c["source_path"] for c in result["chunks"]))
        self.assertTrue(all(c["module"] == "portfolio" for c in result["chunks"]))
        sql = connection.execute.call_args[0][0]
        self.assertIn("module = %s", sql)


if __name__ == "__main__":
    unittest.main()
