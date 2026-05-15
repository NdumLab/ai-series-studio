"""Server-side API key storage stub.

Phase 2A foundation: keys are NOT stored or read from anywhere user-controllable
today. This module exists so the executor's guard logic has a stable seam to
ask "is there a key for this provider yet?".

Today: always returns False. The executor uses this to block real providers
from running even if a flag is mistakenly flipped on.

Phase 2B will replace `key_present()` with a real lookup against a secure
secrets backend (still NOT stored in MongoDB or .env).
"""
from __future__ import annotations
from typing import Optional


def key_present(provider_name: Optional[str]) -> bool:
    """Return True if a server-side API key is configured for this provider.

    Phase 2A: always returns False. No keys are stored anywhere.
    """
    return False


def key_status(provider_name: Optional[str]) -> str:
    """Human-readable key status for diagnostics endpoints."""
    return "not_configured"
