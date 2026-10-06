"""Configura BRAPI_TOKEN localmente sem mostrar o valor no terminal."""
from getpass import getpass
import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

def main():
    token = getpass("Token da brapi.dev: ").strip()
    if not token:
        raise SystemExit("Token vazio; nenhuma alteração realizada.")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    updated = []
    replaced = False
    for line in lines:
        if line.startswith("BRAPI_TOKEN="):
            updated.append(f"BRAPI_TOKEN={token}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"BRAPI_TOKEN={token}")
    ENV_FILE.write_text("\n".join(updated) + "\n", encoding="utf-8")
    os.chmod(ENV_FILE, 0o600)
    print("BRAPI_TOKEN salvo no .env com permissão 600.")

if __name__ == "__main__":
    main()
