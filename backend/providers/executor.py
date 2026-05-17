"""Provider execution guard.

`execute_provider(...)` resolves the configured provider, checks feature flag
and server-side key state, and dispatches to a real provider only for connected
modalities. Today, LLM has its own `execute_llm(...)` path and image can run
OpenAI GPT Image only when all guards pass. Video, voice, music, and export
remain mock-only.
"""
from __future__ import annotations

import os
import time
from typing import Any, Awaitable, Callable, Dict, Optional

from .base import (
    ProviderResult,
    Modality,
    MODALITIES,
    STATUS_SUCCESS,
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_SKIPPED,
)
from .keys import (
    key_present_for_modality,
    key_status,
    key_status_for_modality,
    provider_secrets_backend,
    secret_ref_for_modality,
)
from .mocks import MOCK_PROVIDER_BY_MODALITY
from .resolver import resolve_provider, resolve_voice_for_character

# ---------------------------------------------------------------------------
# Activity recorder seam
# ---------------------------------------------------------------------------
# The provider package stays storage-agnostic. The host app registers a
# coroutine that persists safe metadata for each execute_provider() call.
# The recorder is *only* given the `ProviderResult` + safe scope ids — never
# raw prompts, outputs or API keys.

ActivityRecorder = Callable[[Dict[str, Any]], Awaitable[None]]
_recorder: Optional[ActivityRecorder] = None


def set_activity_recorder(fn: Optional[ActivityRecorder]) -> None:
    """Register a coroutine that persists provider activity metadata.

    Pass `None` to disable recording (used by unit tests)."""
    global _recorder
    _recorder = fn

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


def _real_capable(modality: Modality, provider_name: Optional[str]) -> bool:
    if modality == "llm":
        return True
    if modality == "image":
        try:
            from .image_openai import OPENAI_IMAGE_PROVIDER_IDS
        except Exception:  # pragma: no cover
            return False
        return (provider_name or "").strip().lower() in OPENAI_IMAGE_PROVIDER_IDS
    if modality == "video":
        return (provider_name or "").strip().lower() in {
            "luma",
            "runway",
            "openai-video",
            "sora",
            "fal-video",
        }
    return False


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
    has_key = key_present_for_modality(modality, resolved["provider"])
    real_capable = _real_capable(modality, resolved["provider"])
    will_run_real = flag_on and has_key and real_capable
    return {
        "modality": modality,
        "provider": resolved["provider"],
        "selected_provider": resolved["provider"],
        "model": resolved["model"],
        "selected_model": resolved["model"],
        "source": resolved["source"],
        "feature_flag_enabled": flag_on,
        "secrets_backend": provider_secrets_backend() if modality != "llm" else "llm-runtime",
        "secret_ref": secret_ref_for_modality(modality, resolved["provider"]),
        "key_status": key_status_for_modality(modality, resolved["provider"]),
        "key_present": has_key,
        "would_use_real_provider": will_run_real,
        "real_capable": real_capable,
        "mode": "real" if will_run_real else "mock",
        "status": "ready" if will_run_real else ("blocked" if flag_on else "mock"),
    }


async def execute_provider(
    *,
    modality: Modality,
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
    character: Optional[Dict[str, Any]] = None,
    estimated_credits: int = 0,
    # Scope ids — recorded as safe metadata, never combined with prompts.
    project_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    segment_id: Optional[str] = None,
    **call_kwargs: Any,
) -> ProviderResult:
    """Resolve + run a provider call.

    Image can take a real OpenAI path when the flag, provider, and key guards
    pass. Video/voice/music/export remain mock-only.
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
    has_key = key_present_for_modality(modality, resolved["provider"])
    meta = {
        "resolved_source": resolved["source"],
        "feature_flag_enabled": flag_on,
        "key_present": has_key,
        "key_status": key_status_for_modality(modality, resolved["provider"]),
        "secrets_backend": provider_secrets_backend() if modality != "llm" else "llm-runtime",
    }

    if modality == "image" and flag_on and has_key and _real_capable("image", resolved["provider"]):
        try:
            from .image_openai import OpenAIImageProvider
            real = OpenAIImageProvider(
                provider_name=resolved["provider"],
                model_name=resolved["model"],
            )
            real_res = await real.run(**call_kwargs)
            real_res.estimated_credits = estimated_credits
            real_res.meta = {**meta, **real_res.meta}
            await _record(
                real_res,
                int(real_res.meta.get("duration_ms") or 0),
                project_id, scene_id, segment_id,
            )
            return real_res
        except Exception as exc:  # pragma: no cover - provider returns failures itself
            failed = ProviderResult(
                modality="image",
                provider_name=resolved["provider"],
                model_name=resolved["model"],
                mode="real",
                status=STATUS_FAILED,
                estimated_credits=estimated_credits,
                error=exc.__class__.__name__,
                message="Real image provider failed before request.",
                meta=meta,
            )
            await _record(failed, 0, project_id, scene_id, segment_id)
            return failed

    mock_cls = MOCK_PROVIDER_BY_MODALITY[modality]
    mock = mock_cls(provider_name=resolved["provider"], model_name=resolved["model"])
    started = time.perf_counter()
    res = await mock.run(**call_kwargs)
    duration_ms = int((time.perf_counter() - started) * 1000)
    res.estimated_credits = estimated_credits or res.estimated_credits
    res.mode = "mock"
    if flag_on and (not has_key or not _real_capable(modality, resolved["provider"])):
        res.status = STATUS_BLOCKED
        if not has_key:
            res.message = (
                "Real provider blocked — feature flag is on but no API key is "
                "configured server-side. Mock provider ran instead."
            )
        else:
            res.message = (
                "Real provider blocked — selected provider is not connected "
                "for real execution. Mock provider ran instead."
            )
    else:
        res.status = STATUS_SUCCESS
        res.message = "Mock mode active — real provider call skipped."
    res.meta = meta

    await _record(res, duration_ms, project_id, scene_id, segment_id)
    return res


async def execute_llm(
    *,
    prompt: str,
    system: Optional[str] = None,
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
    estimated_credits: int = 0,
    project_id: Optional[str] = None,
    scene_id: Optional[str] = None,
    segment_id: Optional[str] = None,
) -> ProviderResult:
    """Run an LLM call (real or mock) and return a ProviderResult.

    Behavior:
      - If `USE_REAL_LLM_PROVIDER=true` AND the Emergent key + integrations
        library are available → call the real LLM. On success, the result
        carries `mode="real"`, `output["text"]`, and a `provider_job_id`.
      - On real failure (timeout / exception / blank output): a single
        `status=failed` activity row is written, then the mock runs as a
        fallback and a second activity row is written. The caller gets the
        successful mock `ProviderResult` so the user workflow continues.
      - When the flag is off or the key is missing, only the mock runs.
    """
    resolved = _resolve(
        modality="llm",
        project=project,
        character=None,
        global_settings=global_settings,
    )
    flag_on = _flag_enabled("llm")
    has_key = key_present_for_modality("llm", resolved["provider"])
    meta_base = {
        "resolved_source": resolved["source"],
        "feature_flag_enabled": flag_on,
        "key_present": has_key,
        "key_status": key_status(resolved["provider"]),
    }

    # Real path
    if flag_on and has_key:
        try:
            from .llm_real import RealLLMProvider  # lazy import
        except Exception:
            RealLLMProvider = None  # type: ignore[assignment]
        if RealLLMProvider is not None:
            real = RealLLMProvider(
                provider_name=resolved["provider"],
                model_name=resolved["model"],
            )
            real_res = await real.run(prompt=prompt, system=system)
            real_res.estimated_credits = estimated_credits
            real_res.meta = {**meta_base, **real_res.meta}
            await _record(
                real_res,
                int(real_res.meta.get("duration_ms") or 0),
                project_id, scene_id, segment_id,
            )
            if real_res.status == STATUS_SUCCESS and (real_res.output.get("text") or "").strip():
                return real_res
            # Real failed → record the failure already happened above, now run mock.
            return await _mock_llm(
                resolved=resolved,
                meta_base=meta_base,
                estimated_credits=estimated_credits,
                fallback_reason=real_res.error or "real provider returned no text",
                project_id=project_id, scene_id=scene_id, segment_id=segment_id,
            )

    # Mock-only path (flag off OR key missing)
    return await _mock_llm(
        resolved=resolved,
        meta_base=meta_base,
        estimated_credits=estimated_credits,
        fallback_reason=None,
        blocked=flag_on and not has_key,
        project_id=project_id, scene_id=scene_id, segment_id=segment_id,
    )


async def _mock_llm(
    *,
    resolved: Dict[str, str],
    meta_base: Dict[str, Any],
    estimated_credits: int,
    fallback_reason: Optional[str],
    blocked: bool = False,
    project_id: Optional[str],
    scene_id: Optional[str],
    segment_id: Optional[str],
) -> ProviderResult:
    mock_cls = MOCK_PROVIDER_BY_MODALITY["llm"]
    mock = mock_cls(provider_name=resolved["provider"], model_name=resolved["model"])
    started = time.perf_counter()
    res = await mock.run()
    duration_ms = int((time.perf_counter() - started) * 1000)
    res.estimated_credits = estimated_credits
    res.mode = "mock"
    if fallback_reason:
        res.status = "fallback"
        res.message = f"Real LLM unavailable — fell back to mock ({fallback_reason})."
    elif blocked:
        res.status = STATUS_BLOCKED
        res.message = "Mock mode active — real LLM call skipped."
    else:
        res.status = STATUS_SUCCESS
        res.message = "Mock mode active — real LLM call skipped."
    res.meta = meta_base
    await _record(res, duration_ms, project_id, scene_id, segment_id)
    return res


async def _record(
    res: ProviderResult,
    duration_ms: int,
    project_id: Optional[str],
    scene_id: Optional[str],
    segment_id: Optional[str],
) -> None:
    if _recorder is None:
        return
    record = {
        "modality": res.modality,
        "provider_name": res.provider_name,
        "model_name": res.model_name,
        "source": (res.meta or {}).get("resolved_source", "global"),
        "mode": res.mode,
        "status": res.status,
        "estimated_credits": res.estimated_credits,
        "provider_job_id": res.provider_job_id,
        "message": res.message,
        "error": res.error,
        "duration_ms": duration_ms,
        "project_id": project_id,
        "scene_id": scene_id,
        "segment_id": segment_id,
        "feature_flag_enabled": (res.meta or {}).get("feature_flag_enabled", False),
        "key_present": (res.meta or {}).get("key_present", False),
    }
    try:
        await _recorder(record)
    except Exception:  # pragma: no cover
        pass


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
