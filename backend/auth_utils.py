"""Side-effect-free helpers for MVP local auth."""
import hashlib
import hmac
import secrets
from typing import Optional


PASSWORD_HASH_ITERATIONS = 120_000


def public_user(user: dict) -> dict:
    return {k: v for k, v in (user or {}).items() if k not in {"password_hash", "password_salt"}}


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return salt, digest


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    _, actual = hash_password(password, salt)
    return hmac.compare_digest(actual, expected_hash or "")


def bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
