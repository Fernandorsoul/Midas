"""Executor de migrações PostgreSQL versionadas e idempotentes.

Registra cada migração aplicada em `schema_migrations`. Uma migração já
registrada não é reaplicada. Inconsistência (arquivo alterado após aplicação)
falha com diagnóstico acionável — nunca pede para apagar o volume.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "infra" / "postgres" / "migrations"

BOOTSTRAP_MARKER = "001-persistent-portfolio.sql"  # primeiro arquivo do fluxo versionado


def connect():
    return psycopg.connect(
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "midas"),
        user=os.getenv("POSTGRES_USER", "midas_admin"),
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
        row_factory=psycopg.rows.dict_row,
    )


def ensure_tracking_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename text PRIMARY KEY,
            checksum text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    connection.commit()


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def applied_migrations(connection):
    rows = connection.execute(
        "SELECT filename, checksum FROM schema_migrations ORDER BY filename"
    ).fetchall()
    return {row["filename"]: row["checksum"] for row in rows}


def pending_migrations(connection):
    ensure_tracking_table(connection)
    done = applied_migrations(connection)
    pending = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        name = path.name
        checksum = file_checksum(path)
        if name not in done:
            pending.append((path, checksum, None))
        elif done[name] != checksum:
            raise RuntimeError(
                f"Inconsistência: a migração {name} foi alterada após ser aplicada. "
                f"Crie uma nova migração em vez de editar a aplicada. "
                f"Esperado {done[name][:12]}…, encontrado {checksum[:12]}…"
            )
    return pending


def apply_pending(check_only=False):
    with connect() as connection:
        pending = pending_migrations(connection)
        if not pending:
            print("Nenhuma migração pendente.")
            return 0
        for path, checksum, _ in pending:
            if check_only:
                print(f"Pendente: {path.name}")
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                # Migrações já embutem BEGIN/COMMIT; execute o arquivo inteiro.
                connection.execute(sql)
                connection.execute(
                    "INSERT INTO schema_migrations(filename, checksum) VALUES (%s, %s)",
                    (path.name, checksum),
                )
                connection.commit()
            except Exception as error:
                connection.rollback()
                raise RuntimeError(
                    f"Falha ao aplicar {path.name}: {error}. "
                    "O banco foi mantido no estado anterior (transação revertida). "
                    "Corrija a migração e execute de novo; não é necessário apagar o volume."
                ) from error
            print(f"Applied: {path.name}")
        return len(pending)


def status():
    with connect() as connection:
        ensure_tracking_table(connection)
        done = applied_migrations(connection)
        pending = pending_migrations(connection)
        print(f"Aplicadas: {len(done)}")
        for name in sorted(done):
            print(f"  ✓ {name}")
        print(f"Pendentes: {len(pending)}")
        for path, _, _ in pending:
            print(f"  · {path.name}")


def baseline():
    """Registra todas as migrações atuais como aplicadas (para bancos já migrados)."""
    with connect() as connection:
        ensure_tracking_table(connection)
        count = 0
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            checksum = file_checksum(path)
            connection.execute(
                """INSERT INTO schema_migrations(filename, checksum) VALUES (%s, %s)
                   ON CONFLICT (filename) DO NOTHING""",
                (path.name, checksum),
            )
            count += 1
        connection.commit()
        print(f"Baseline: {count} migrações registradas.")
        return count


def main(argv=None):
    parser = argparse.ArgumentParser(description="Migrações PostgreSQL do Midas")
    parser.add_argument("--check", action="store_true", help="Lista pendentes sem aplicar")
    parser.add_argument("--status", action="store_true", help="Mostra estado das migrações")
    parser.add_argument("--baseline", action="store_true",
                        help="Registra migrações existentes como aplicadas sem executá-las")
    args = parser.parse_args(argv)
    if args.status:
        status()
        return 0
    if args.baseline:
        baseline()
        return 0
    apply_pending(check_only=args.check)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, KeyError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        sys.exit(1)
