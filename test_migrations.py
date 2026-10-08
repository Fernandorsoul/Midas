import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import scripts.migrate_postgres as migrate


class ChecksumTests(unittest.TestCase):
    def test_file_checksum_stable(self):
        path = Path("infra/postgres/migrations/001-persistent-portfolio.sql")
        a = migrate.file_checksum(path)
        b = migrate.file_checksum(path)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)

    def test_migrations_dir_exists(self):
        self.assertTrue(migrate.MIGRATIONS_DIR.exists())
        self.assertTrue(list(migrate.MIGRATIONS_DIR.glob("*.sql")))


class PendingTests(unittest.TestCase):
    def test_detects_checksum_drift(self):
        connection = MagicMock()
        connection.execute.return_value.fetchall.return_value = [
            {"filename": "001-persistent-portfolio.sql", "checksum": "deadbeef"}
        ]
        with patch.object(migrate, "applied_migrations", return_value={
            "001-persistent-portfolio.sql": "deadbeef"
        }):
            with self.assertRaisesRegex(RuntimeError, "alterada após ser aplicada"):
                migrate.pending_migrations(connection)

    def test_lists_new_migrations(self):
        connection = MagicMock()
        with patch.object(migrate, "applied_migrations", return_value={}):
            pending = migrate.pending_migrations(connection)
        self.assertGreaterEqual(len(pending), 1)
        self.assertTrue(pending[0][0].name.endswith(".sql"))


class CheckQualityScriptTests(unittest.TestCase):
    def test_script_exists(self):
        self.assertTrue(Path("scripts/check_quality.py").exists())
        self.assertTrue(Path("scripts/validate_rag.py").exists())
        self.assertTrue(Path(".github/workflows/ci.yml").exists())


if __name__ == "__main__":
    unittest.main()
