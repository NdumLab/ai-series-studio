"""Backend-only provider secret resolution.

This module intentionally fails closed. It never logs or returns secret values
to frontend-facing code. The current production target is AWS SSM Parameter
Store SecureString; local/default mode is disabled.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional


_SAFE_SEGMENT = re.compile(r"[^a-zA-Z0-9_.-]+")


@dataclass(frozen=True)
class SecretResolution:
    configured: bool
    backend: str
    secret_ref: Optional[str] = None
    status: str = "not_configured"
    error: Optional[str] = None


def secrets_backend(env: Optional[dict] = None) -> str:
    source = env if env is not None else os.environ
    return (source.get("SECRETS_BACKEND") or "disabled").strip().lower() or "disabled"


def _provider_slug(provider_name: Optional[str]) -> str:
    raw = (provider_name or "").strip().lower()
    if not raw:
        return ""
    # Preserve common provider family names even when the configured provider id
    # is model-ish, e.g. "openai-image".
    for prefix in ("openai", "gemini", "fal", "luma", "elevenlabs"):
        if raw.startswith(prefix):
            return prefix
    return _SAFE_SEGMENT.sub("-", raw).strip("-")


def provider_secret_ref(
    modality: Optional[str],
    provider_name: Optional[str],
    env: Optional[dict] = None,
) -> Optional[str]:
    source = env if env is not None else os.environ
    modality_slug = _SAFE_SEGMENT.sub("-", (modality or "").strip().lower()).strip("-")
    provider_slug = _provider_slug(provider_name)
    if not modality_slug or not provider_slug:
        return None
    prefix = (source.get("SSM_PROVIDER_KEY_PREFIX") or "/ai-series-studio/providers").strip().rstrip("/")
    return f"{prefix}/{modality_slug}/{provider_slug}/api-key"


def get_provider_secret(
    modality: Optional[str],
    provider_name: Optional[str],
    env: Optional[dict] = None,
) -> SecretResolution:
    """Return safe secret resolution metadata.

    The actual secret value is never returned. Callers only learn whether a
    secret is configured and which reference was attempted.
    """
    source = env if env is not None else os.environ
    backend = secrets_backend(source)
    ref = provider_secret_ref(modality, provider_name, source)
    if backend == "disabled":
        return SecretResolution(False, backend, ref, "not_configured")
    if backend != "ssm":
        return SecretResolution(False, backend, ref, "not_configured", "Unsupported secrets backend")
    if not ref:
        return SecretResolution(False, backend, ref, "not_configured", "Missing provider secret reference")
    try:
        import boto3  # type: ignore
        from botocore.exceptions import BotoCoreError, ClientError  # type: ignore
    except Exception:
        return SecretResolution(False, backend, ref, "not_configured", "AWS SDK unavailable")
    try:
        client = boto3.client("ssm", region_name=(source.get("AWS_REGION") or "us-east-1").strip())
        response = client.get_parameter(Name=ref, WithDecryption=True)
        value = ((response or {}).get("Parameter") or {}).get("Value") or ""
        return SecretResolution(bool(str(value).strip()), backend, ref, "configured" if str(value).strip() else "not_configured")
    except (BotoCoreError, ClientError, Exception) as exc:  # noqa: BLE001
        return SecretResolution(False, backend, ref, "not_configured", exc.__class__.__name__)


def key_present_for_provider(
    modality: Optional[str],
    provider_name: Optional[str],
    env: Optional[dict] = None,
) -> bool:
    return get_provider_secret(modality, provider_name, env).configured
