"""Caso de uso de usuários: registro, login, sessão, export e exclusão.

Tokens brutos só aparecem na resposta de login; o banco guarda hash.
"""
from __future__ import annotations

from midas_core.domain.auth import (
    AuthError,
    assert_owner,
    bearer_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_email,
    session_expiry,
    verify_password,
)


def register_user(email, password, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    email = normalize_email(email)
    password_hash = hash_password(password)
    user = repository.create_user(email, password_hash)
    return {"user": {"id": user["id"], "email": user["email"]}}


def login_user(email, password, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    email = normalize_email(email)
    user = repository.get_user_by_email(email)
    if user is None or not verify_password(password or "", user["password_hash"]):
        raise AuthError("Credenciais inválidas.")
    token = generate_session_token()
    token_hash = hash_session_token(token)
    repository.create_session(token_hash, user["id"], session_expiry())
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"]},
        "expires_in_hours": 24 * 7,
    }


def logout_user(token, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    repository.delete_session(hash_session_token(token))
    return {"message": "Sessão encerrada."}


def current_user_from_header(authorization_header, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    token = bearer_token(authorization_header)
    row = repository.get_session_user(hash_session_token(token))
    if row is None:
        raise AuthError("Sessão inválida ou expirada.")
    return {"id": row["id"], "email": row["email"]}


def export_my_data(user_id, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    data = repository.export_user_data(user_id)
    return {
        "user": {"id": data["user"]["id"], "email": data["user"]["email"]},
        "portfolios": data["portfolios"],
        "operations": data["operations"],
        "jobs": data["jobs"],
    }


def delete_my_data(user_id, repository=None):
    from midas_core.infrastructure.repositories import PostgresRepository
    repository = repository or PostgresRepository()
    if not repository.delete_user_data(user_id):
        raise AuthError("Usuário não encontrado.")
    return {"message": "Dados e conta removidos."}


__all__ = [
    "AuthError",
    "assert_owner",
    "current_user_from_header",
    "delete_my_data",
    "export_my_data",
    "login_user",
    "logout_user",
    "register_user",
]
