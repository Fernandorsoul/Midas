"""Domínio de usuários: hash de senha e tokens de sessão.

Senhas usam PBKDF2-HMAC-SHA256 (stdlib). Tokens de sessão são guardados
apenas como hash SHA-256 — o valor bruto nunca é persistido ou logado.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import date, datetime, timedelta, timezone

PBKDF2_ITERATIONS = 240_000
SESSION_TTL_HOURS = 24 * 7
MIN_PASSWORD_LENGTH = 8


class AuthError(ValueError):
    """Falha de autenticação/autorização com mensagem segura."""


def hash_password(password: str, salt: bytes | None = None) -> str:
    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError("Senha muito curta.")
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def normalize_email(email: str) -> str:
    if not email or not isinstance(email, str):
        raise AuthError("E-mail inválido.")
    value = email.strip().lower()
    if "@" not in value or value.startswith("@") or value.endswith("@"):
        raise AuthError("E-mail inválido.")
    return value


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    if not token or not isinstance(token, str):
        raise AuthError("Token inválido.")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now + timedelta(hours=SESSION_TTL_HOURS)


def bearer_token(header_value: str | None) -> str:
    """Extrai token do header Authorization: Bearer <token>."""
    if not header_value:
        raise AuthError("Autenticação necessária.")
    parts = header_value.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthError("Autenticação necessária.")
    token = parts[1].strip()
    if not token:
        raise AuthError("Autenticação necessária.")
    return token


def assert_owner(resource_user_id, current_user_id):
    """Impede leitura/alteração de recurso de outro usuário."""
    if current_user_id is None:
        raise AuthError("Autenticação necessária.")
    if resource_user_id is None:
        # Recurso legado sem dono: tratado como não acessível em modo multiusuário
        raise AuthError("Recurso sem proprietário.")
    if int(resource_user_id) != int(current_user_id):
        raise AuthError("Acesso negado.")
    return True
