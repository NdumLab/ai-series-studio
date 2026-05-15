"""Provider execution guard.

`execute_provider(...)` is the single entry point that resolves the configured
provider, checks the feature flag + key, and then dispatches to either the
real provider (Phase 2B+) or the corresponding mock.

Phase 2A guarantee: **No real network calls are ever made.** Even if a
`USE_REAL_*_PROVIDER` flag is flipped to true, the executor refuses because
no API key is configured (see `keys.key_present`). The result is always a
clean `ProviderResult` with `mode="mock"` and a transparent `message`.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .base import (
    ProviderResult,
    Modality,
    MODALITIES,
    STATUS_SUCCESS,
    STATUS_BLOCKED,
    STATUS_SKIPPED,
)
from .keys import key_present, key_status
from .mocks import MOCK_PROVIDER_BY_MODALITY
from .resolver import resolve_provider, resolve_voice_for_character

_FLAG_ENV_KEYS = {
    "llm":    "USE_REAL_LLM_PROVIDER",
    "image":  "USE_REAL_IMAGE_PROVIDER",
    "video":  "USE_REAL_VIDEO_PROVIDER",
    "voice":  "USE_REAL_VOICE_PROVIDER",
    "music":  "USE_REAL_MUSIC_PROVIDER",
    "export": "USE_REAL_EXPORT_PROVIDER",
}


def _flag_enabled(modality: Modality) -> bool:
    env_key = _FLAG_ENV_KEYS[modality]
    return os.environ.get(env_key, "false").strip().lower() == "true"


def _resolve(
    *,
    modality: Modality,
    project: Optional[Dict[str, Any]],
    character: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
) -> Dict[str, Any]:
    if modality == "voice":
        return resolve_voice_for_character(
            character=character, project=project, global_settings=global_settings
        )
    return resolve_provider(
        modality=modality, project=project, global_settings=global_settings
    )


def provider_status(
    *,
    modality: Modality,
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
    character: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Diagnostic snapshot — what *would* happen if execute_provider() ran right now."""
    if modality not in MODALITIES:
        raise ValueError(f"Unknown modality: {modality}")
    resolved = _resolve(
        modality=modality,
        project=project,
        character=character,
        global_settings=global_settings,
    )
    flag_on = _flag_enabled(modality)
    has_key = key_present(resolved["provider"])
    will_run_real = flag_on and has_key
    return {
        "modality": modality,
        "provider": resolved["provider"],
        "model": resolved["model"],
        "source": resolved["source"],
        "feature_flag_enabled": flag_on,
        "key_status": key_status(resolved["provider"]),
        "key_present": has_key,
        "would_use_real_provider": will_run_real,
        "mode": "real" if will_run_real else "mock",
    }


async def execute_provider(
    *,
    modality: Modality,
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
    character: Optional[Dict[str, Any]] = None,
    estimated_credits: int = 0,
    **call_kwargs: Any,
) -> ProviderResult:
    """Resolve + run a provider call.

    Phase 2A: real providers are NEVER executed. If the flag is on but the key
    is missing, the executor still runs the mock and tags the result as
    `status=blocked` so the caller can surface a clear message.
    """
    if modality not in MODALITIES:
        raise ValueError(f"Unknown modality: {modality}")

    resolved = _resolve(
        modality=modality,
        project=project,
        character=character,
        global_settings=global_settings,
    )
    flag_on = _flag_enabled(modality)
    has_key = key_present(resolved["provider"])
    meta = {
        "resolved_source": resolved["source"],
        "feature_flag_enabled": flag_on,
        "key_present": has_key,
        "key_status": key_status(resolved["provider"]),
    }

    # Real path is blocked in Phase 2A regardless of flag, because no key store
    # exists yet. We still run the mock so callers get a usable response.
    if flag_on and not has_key:
        mock_cls = MOCK_PROVIDER_BY_MODALITY[modality]
        mock = mock_cls(
            provider_name=resolved["provider"], model_name=resolved["model"]
        )
        res = await mock.run(**call_kwargs)
        res.estimated_credits = estimated_credits or res.estimated_credits
        res.status = STATUS_BLOCKED
        res.mode = "mock"
        res.message = (
            "Real provider blocked — feature flag is on but no API key is "
            "configured server-side. Mock provider ran instead."
        )
        res.meta = meta
        return res

    # Standard mock path (flag off OR no real provider implemented yet).
    mock_cls = MOCK_PROVIDER_BY_MODALITY[modality]
    mock = mock_cls(
        provider_name=resolved["provider"], model_name=resolved["model"]
    )
    res = await mock.run(**call_kwargs)
    res.estimated_credits = estimated_credits or res.estimated_credits
    res.status = STATUS_SUCCESS
    res.mode = "mock"
    res.message = "Mock mode active — real provider call skipped."
    res.meta = meta
    return res


async def run_modality_test(
    *,
    modality: Modality,
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Dry-run for the unified `POST /api/providers/test` endpoint.

    Nothing is actually executed (status = "skipped"). The response shape is
    the same shape Phase 2B will use when it really runs a provider ping.
    """
    if modality not in MODALITIES:
        raise ValueError(f"Unknown modality: {modality}")

    snap = provider_status(
        modality=modality, project=project, global_settings=global_settings
    )
    return {
        "ok": True,
        "mode": "mock",
        "status": STATUS_SKIPPED,
        "modality": modality,
        "provider": snap["provider"],
        "model": snap["model"],
        "source": snap["source"],
        "feature_flag_enabled": snap["feature_flag_enabled"],
        "key_status": snap["key_status"],
        "key_present": snap["key_present"],
        "message": "Mock mode active — no real provider call was made.",
    }
