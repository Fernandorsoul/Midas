"""Gera credenciais locais sem imprimir segredos ou substituir arquivo existente."""
import os
from pathlib import Path
import secrets

target = Path(__file__).resolve().parents[1] / '.env'
values = {name: secrets.token_hex(32) for name in (
    'POSTGRES_PASSWORD', 'POSTGRES_APP_PASSWORD', 'MONGO_ROOT_PASSWORD', 'MONGO_APP_PASSWORD')}
try:
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
except FileExistsError:
    print('.env já existe; credenciais preservadas.')
else:
    with os.fdopen(fd, 'w') as f:
        f.write('\n'.join(f'{key}={value}' for key, value in values.items()) + '\n')
    print('.env criado com permissão 600. Nenhum segredo exibido.')
