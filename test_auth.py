import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from midas_core.application.auth import (
    current_user_from_header,
    delete_my_data,
    export_my_data,
    login_user,
    logout_user,
    register_user,
)
from midas_core.domain.auth import (
    AuthError,
    assert_owner,
    bearer_token,
    generate_session_token,
    hash_password,
    hash_session_token,
    normalize_email,
    verify_password,
)


class PasswordTests(unittest.TestCase):
    def test_hash_and_verify_round_trip(self):
        stored = hash_password("senha-forte-123")
        self.assertTrue(verify_password("senha-forte-123", stored))
        self.assertFalse(verify_password("senha-errada", stored))

    def test_hash_is_salted_and_not_plaintext(self):
        a = hash_password("senha-forte-123")
        b = hash_password("senha-forte-123")
        self.assertNotEqual(a, b)
        self.assertNotIn("senha-forte-123", a)

    def test_rejects_short_password(self):
        with self.assertRaises(AuthError):
            hash_password("123")

    def test_normalize_email(self):
        self.assertEqual(normalize_email("  User@Example.COM "), "user@example.com")
        with self.assertRaises(AuthError):
            normalize_email("invalido")


class SessionTokenTests(unittest.TestCase):
    def test_bearer_token(self):
        token = generate_session_token()
        self.assertEqual(bearer_token("Bearer " + token), token)
        with self.assertRaises(AuthError):
            bearer_token(None)
        with self.assertRaises(AuthError):
            bearer_token("Basic abc")

    def test_hash_session_token_stable(self):
        token = generate_session_token()
        self.assertEqual(hash_session_token(token), hash_session_token(token))
        self.assertNotEqual(hash_session_token(token), token)


class OwnerTests(unittest.TestCase):
    def test_owner_can_access(self):
        self.assertTrue(assert_owner(1, 1))

    def test_other_user_denied(self):
        with self.assertRaisesRegex(AuthError, "Acesso negado"):
            assert_owner(2, 1)

    def test_missing_user_denied(self):
        with self.assertRaises(AuthError):
            assert_owner(1, None)

    def test_legacy_resource_without_owner_denied(self):
        with self.assertRaises(AuthError):
            assert_owner(None, 1)


class FakeRepository:
    def __init__(self):
        self.users = {}
        self.sessions = {}
        self._next = 1

    def create_user(self, email, password_hash):
        if any(u["email"] == email for u in self.users.values()):
            raise ValueError("E-mail já cadastrado.")
        user = {"id": self._next, "email": email, "password_hash": password_hash, "created_at": None}
        self.users[user["id"]] = user
        self._next += 1
        return user

    def get_user_by_email(self, email):
        for user in self.users.values():
            if user["email"] == email:
                return user
        return None

    def get_user(self, user_id):
        user = self.users.get(user_id)
        return {"id": user["id"], "email": user["email"], "created_at": None} if user else None

    def create_session(self, token_hash, user_id, expires_at):
        self.sessions[token_hash] = {"user_id": user_id, "expires_at": expires_at}

    def get_session_user(self, token_hash):
        session = self.sessions.get(token_hash)
        if not session:
            return None
        user = self.users[session["user_id"]]
        return {"id": user["id"], "email": user["email"], "expires_at": session["expires_at"]}

    def delete_session(self, token_hash):
        return self.sessions.pop(token_hash, None) is not None

    def export_user_data(self, user_id):
        user = self.users[user_id]
        return {"user": user, "portfolios": [], "operations": [], "jobs": []}

    def delete_user_data(self, user_id):
        return self.users.pop(user_id, None) is not None


class AuthFlowTests(unittest.TestCase):
    def test_register_login_and_me(self):
        repository = FakeRepository()
        register_user("a@b.com", "senha-forte-123", repository=repository)
        result = login_user("a@b.com", "senha-forte-123", repository=repository)
        self.assertIn("token", result)
        self.assertNotIn("password", result)
        me = current_user_from_header("Bearer " + result["token"], repository=repository)
        self.assertEqual(me["email"], "a@b.com")

    def test_login_rejects_wrong_password(self):
        repository = FakeRepository()
        register_user("a@b.com", "senha-forte-123", repository=repository)
        with self.assertRaises(AuthError):
            login_user("a@b.com", "outra-senha-123", repository=repository)

    def test_logout_invalidates_session(self):
        repository = FakeRepository()
        register_user("a@b.com", "senha-forte-123", repository=repository)
        token = login_user("a@b.com", "senha-forte-123", repository=repository)["token"]
        logout_user(token, repository=repository)
        with self.assertRaises(AuthError):
            current_user_from_header("Bearer " + token, repository=repository)

    def test_duplicate_email_rejected(self):
        repository = FakeRepository()
        register_user("a@b.com", "senha-forte-123", repository=repository)
        with self.assertRaisesRegex(ValueError, "cadastrado"):
            register_user("a@b.com", "senha-forte-123", repository=repository)

    def test_export_and_delete(self):
        repository = FakeRepository()
        register_user("a@b.com", "senha-forte-123", repository=repository)
        user_id = 1
        export = export_my_data(user_id, repository=repository)
        self.assertEqual(export["user"]["email"], "a@b.com")
        self.assertNotIn("password_hash", export["user"])
        delete_my_data(user_id, repository=repository)
        with self.assertRaises(AuthError):
            delete_my_data(user_id, repository=repository)


if __name__ == "__main__":
    unittest.main()
