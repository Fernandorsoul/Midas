"""Verificações de qualidade em um único comando.

Executa (na ordem): sintaxe JS, testes Python e healthcheck de bancos.
Uso: python scripts/check_quality.py [--skip-js] [--skip-tests] [--skip-health]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(title, command, cwd=ROOT):
    print(f"\n=== {title} ===", flush=True)
    result = subprocess.run(command, cwd=cwd, shell=False)
    return result.returncode == 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="Checks de qualidade do Midas")
    parser.add_argument("--skip-js", action="store_true")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--skip-health", action="store_true")
    args = parser.parse_args(argv)

    failures = []
    if not args.skip_js:
        if not run("Sintaxe JavaScript", ["docker", "compose", "run", "--rm", "--no-deps",
                                          "--entrypoint", "sh", "dev", "-c", "yarn run check"]):
            failures.append("js")
    if not args.skip_tests:
        if not run("Testes Python", ["docker", "compose", "run", "--rm", "--no-deps",
                                     "--entrypoint", "python", "dev", "-m", "unittest",
                                     "discover", "-p", "test_*.py", "-v"]):
            failures.append("tests")
    if not args.skip_health:
        if not run("Healthcheck dos bancos", ["docker", "compose", "run", "--rm", "--no-deps",
                                              "--entrypoint", "python", "dev",
                                              "scripts/check_databases.py"]):
            failures.append("health")

    if failures:
        print(f"\nFALHOU: {', '.join(failures)}", file=sys.stderr)
        return 1
    print("\nTodas as verificações passaram.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
