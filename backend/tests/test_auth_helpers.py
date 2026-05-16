"""Unit tests for local MVP auth helpers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from auth_utils import (  # noqa: E402
    bearer_token,
    create_access_token,
    decode_access_token,
    hash_password,
    public_user,
    verify_password,
)


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


def test_jwt_access_token_round_trip():
    token = create_access_token("user-123", "test-secret", expires_in_seconds=60)
    payload = decode_access_token(token, "test-secret")

    assert payload["sub"] == "user-123"
    assert payload["exp"] > payload["iat"]


def test_jwt_rejects_wrong_secret():
    token = create_access_token("user-123", "test-secret", expires_in_seconds=60)

    try:
        decode_access_token(token, "wrong-secret")
    except ValueError as exc:
        assert "signature" in str(exc).lower()
    else:
        raise AssertionError("Expected wrong secret to be rejected")
