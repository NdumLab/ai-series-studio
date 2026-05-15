"""Server-side provider key/runtime status.

Phase 2B (LLM-only): the `llm` modality is considered key-configured when
the Emergent universal LLM key is set AND `emergentintegrations` is
importable. Every other modality remains permanently `not_configured` until
a proper secrets store exists.
"""
from __future__ import annotations
from typing import Optional


# Map of which modality each provider id belongs to. Used by `key_present()`
# to disallow non-LLM modalities even if `USE_REAL_*_PROVIDER` is flipped on.
_LLM_PROVIDER_IDS = {
    "openai", "anthropic", "gemini",
    # Internal mock identifiers can also map to the LLM modality.
    "mock-llm",
}


def key_present_for_modality(modality: Optional[str], provider_name: Optional[str]) -> bool:
    """Return True only when a key/runtime is configured for this modality.

    Phase 2B accepts ONLY the `llm` modality. All other modalities return
    False unconditionally until a proper secrets store exists.
    """
    if modality != "llm":
        return False
    # Lazy import to avoid pulling emergentintegrations at module load.
    try:
        from .llm_real import real_llm_available
        return real_llm_available()
    except Exception:  # pragma: no cover
        return False


def key_present(provider_name: Optional[str]) -> bool:
    """Legacy single-arg signature kept for the executor + status snapshot.

    Without a modality, we err on the safe side: only return True when the
    provider id is recognized as LLM AND the universal key is configured.
    """
    if not provider_name:
        return False
    if provider_name in _LLM_PROVIDER_IDS or provider_name.startswith("mock-"):
        return key_present_for_modality("llm", provider_name)
    return False


def key_status(provider_name: Optional[str]) -> str:
    return "configured" if key_present(provider_name) else "not_configured"
