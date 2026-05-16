"""Unit tests for local MVP auth helpers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth_utils import bearer_token, hash_password, public_user, verify_password  # noqa: E402


def test_password_hash_verify_round_trip():
    salt, digest = hash_password("correct horse battery staple")

    assert salt
    assert digest
    assert verify_password("correct horse battery staple", salt, digest)
    assert not verify_password("wrong password", salt, digest)


def test_public_user_strips_password_fields():
    user = {
        "id": "user-1",
        "email": "creator@example.com",
        "password_hash": "secret-hash",
        "password_salt": "secret-salt",
    }

    assert public_user(user) == {"id": "user-1", "email": "creator@example.com"}


def test_bearer_token_parsing():
    assert bearer_token("Bearer abc123") == "abc123"
    assert bearer_token("bearer abc123") == "abc123"
    assert bearer_token("Basic abc123") is None
    assert bearer_token(None) is None
