"""Side-effect-free helpers for MVP local auth."""
import base64
import hashlib
import hmac
import json
import secrets
import time
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


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(raw: str) -> bytes:
    padding = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + padding).encode("ascii"))


def create_access_token(
    user_id: str,
    secret: str,
    expires_in_seconds: int = 86400,
    algorithm: str = "HS256",
) -> str:
    if algorithm != "HS256":
        raise ValueError("Only HS256 JWTs are supported")
    now = int(time.time())
    header = {"alg": algorithm, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + int(expires_in_seconds),
    }
    signing_input = ".".join([
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ])
    sig = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def decode_access_token(token: str, secret: str, algorithm: str = "HS256") -> dict:
    if algorithm != "HS256":
        raise ValueError("Only HS256 JWTs are supported")
    try:
        header_b64, payload_b64, sig_b64 = token.split(".", 2)
    except ValueError as exc:
        raise ValueError("Invalid token") from exc

    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(secret.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    try:
        actual = _b64url_decode(sig_b64)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid token signature") from exc
    if not hmac.compare_digest(actual, expected):
        raise ValueError("Invalid token signature")

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except Exception as exc:  # noqa: BLE001
        raise ValueError("Invalid token payload") from exc
    if header.get("alg") != algorithm:
        raise ValueError("Unsupported token algorithm")
    if int(payload.get("exp") or 0) < int(time.time()):
        raise ValueError("Token expired")
    if not payload.get("sub"):
        raise ValueError("Token subject missing")
    return payload
