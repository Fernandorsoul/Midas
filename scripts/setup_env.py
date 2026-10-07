"""Gera credenciais locais sem imprimir segredos ou substituir arquivo existente."""
import os
from pathlib import Path
import secrets

target = Path(__file__).resolve().parents[1] / '.env'
names = (
    'POSTGRES_PASSWORD', 'POSTGRES_APP_PASSWORD', 'MONGO_ROOT_PASSWORD',
    'MONGO_APP_PASSWORD', 'RAG_POSTGRES_PASSWORD',
)
values = {name: secrets.token_hex(32) for name in names}
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    existing = {
        line.partition('=')[0].strip()
        for line in target.read_text(encoding='utf-8').splitlines()
        if line.strip() and not line.lstrip().startswith('#') and '=' in line
    }
    missing = [name for name in names if name not in existing]
    if missing:
        with target.open('a', encoding='utf-8') as f:
            for name in missing:
                f.write(f'{name}={values[name]}\n')
    print('.env já existe; credenciais preservadas.')
else:
    with os.fdopen(fd, 'w') as f:
        f.write('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')
    print('.env criado com permissão 600. Nenhum segredo exibido.')
