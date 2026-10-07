"""Aplica migrations PostgreSQL pela instância Docker local, em ordem de nome."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
for migration in sorted((ROOT / "infra" / "postgres" / "migrations").glob("*.sql")):
    subprocess.run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "midas_admin", "-d", "midas", "-v", "ON_ERROR_STOP=1", "-f", f"/app/{migration.relative_to(ROOT).as_posix()}"],
        cwd=ROOT,
        check=True,
    )
    print(f"Applied: {migration.name}")
