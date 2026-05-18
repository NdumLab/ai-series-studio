"""Phase 2B real-LLM provider tests.

Verifies:
 - Real LLM is blocked when USE_REAL_LLM_PROVIDER=false (mock runs).
 - Real LLM is blocked when the key/runtime is unavailable.
 - When real LLM raises, the executor falls back to the mock and records the
   failure in provider_activity.
 - Image/Video/Voice/Music/Export modalities block without server-side keys,
   even when their feature flag is on.
"""
import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import providers as providers_pkg  # noqa: E402
from providers import (  # noqa: E402
    execute_llm,
    execute_provider,
    provider_status,
    set_activity_recorder,
)


def _run(coro):
    return asyncio.run(coro)


GLOBAL = {
    "llm":    {"provider": "openai",   "model": "gpt-5.2"},
    "image":  {"provider": "fal",      "model": "flux-pro"},
    "video":  {"provider": "sora-2",   "model": "sora-2"},
    "voice":  {"provider": "elevenlabs", "model": "eleven-v3"},
    "music":  {"provider": "suno",     "model": "v4"},
    "export": {"provider": "ffmpeg-local", "model": "ffmpeg-6"},
}


@pytest.fixture
def clean_env(monkeypatch):
    for k in [
        "USE_REAL_LLM_PROVIDER", "USE_REAL_IMAGE_PROVIDER", "USE_REAL_VIDEO_PROVIDER",
        "USE_REAL_VOICE_PROVIDER", "USE_REAL_MUSIC_PROVIDER", "USE_REAL_EXPORT_PROVIDER",
    ]:
        monkeypatch.delenv(k, raising=False)
    yield


@pytest.fixture
def captured_activity(monkeypatch):
    """Replace the recorder with an in-memory list."""
    rows = []

    async def _rec(r):
        rows.append(dict(r))

    # Save and restore the original recorder.
    from providers import executor as _exe
    original = _exe._recorder
    set_activity_recorder(_rec)
    try:
        yield rows
    finally:
        set_activity_recorder(original)


# ---------- Real-LLM gating ----------
def test_real_llm_blocked_when_flag_off(clean_env, captured_activity):
    res = _run(execute_llm(
        prompt="anything", project=None, global_settings=GLOBAL,
    ))
    # Flag off → real path never tried → mock ran cleanly → status=success.
    assert res.mode == "mock"
    assert res.status == "success"
    assert res.meta["feature_flag_enabled"] is False
    assert captured_activity, "Expected one activity row"
    assert captured_activity[-1]["mode"] == "mock"


def test_real_llm_blocked_when_key_missing(clean_env, monkeypatch, captured_activity):
    # Force flag on AND remove the key — should still run mock, never real.
    monkeypatch.setenv("USE_REAL_LLM_PROVIDER", "true")
    monkeypatch.delenv("EMERGENT_LLM_KEY", raising=False)
    # Re-import side: keys.key_present_for_modality reads the env at call time,
    # so this should now return False even though the flag is on.
    res = _run(execute_llm(
        prompt="anything", project=None, global_settings=GLOBAL,
    ))
    assert res.mode == "mock"
    assert res.status == "blocked"
    assert captured_activity[-1]["key_present"] is False


def test_real_llm_fallback_when_real_raises(clean_env, monkeypatch, captured_activity):
    """If real LLM is enabled but the provider call raises, the executor must
    record the failure and fall back to the mock so the user is never blocked."""
    monkeypatch.setenv("USE_REAL_LLM_PROVIDER", "true")
    # Force a broken key so RealLLMProvider.run() raises during send_message().
    monkeypatch.setenv("EMERGENT_LLM_KEY", "definitely-not-a-real-key")
    monkeypatch.setattr(
        providers_pkg.executor,
        "key_present_for_modality",
        lambda modality, provider: modality == "llm",
    )

    # Patch RealLLMProvider to raise — but only if it's actually reached
    # (when key_present_for_modality returns True). Since our broken key still
    # imports `emergentintegrations`, real_llm_available() should return True
    # and the executor will call into it. Force send_message to raise.
    from providers import llm_real as llm_real_mod

    class _BrokenRealLLM(llm_real_mod.RealLLMProvider):
        async def run(self, **kwargs):
            from providers.base import ProviderResult, STATUS_FAILED
            return ProviderResult(
                modality="llm",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                output={"text": ""},
                error="simulated real-LLM failure",
                message="Real LLM call failed — falling back to mock.",
                meta={"duration_ms": 7},
            )

    monkeypatch.setattr(llm_real_mod, "RealLLMProvider", _BrokenRealLLM)

    res = _run(execute_llm(
        prompt="anything", project=None, global_settings=GLOBAL,
    ))
    # The caller gets the mock fallback — user workflow not broken.
    assert res.mode == "mock"
    assert res.status == "fallback"
    # Both rows landed in provider_activity: the failed real one + the mock fallback.
    statuses = [r["status"] for r in captured_activity if r["modality"] == "llm"]
    assert "failed" in statuses
    assert "fallback" in statuses


# ---------- Non-LLM modalities remain guarded when no server-side key exists ----------
@pytest.mark.parametrize("modality,flag_env", [
    ("image",  "USE_REAL_IMAGE_PROVIDER"),
    ("video",  "USE_REAL_VIDEO_PROVIDER"),
    ("voice",  "USE_REAL_VOICE_PROVIDER"),
    ("music",  "USE_REAL_MUSIC_PROVIDER"),
])
def test_non_llm_modalities_block_without_key_even_with_flag_on(modality, flag_env, monkeypatch, captured_activity):
    monkeypatch.setenv(flag_env, "true")
    res = _run(execute_provider(
        modality=modality, project=None, global_settings=GLOBAL, estimated_credits=1,
    ))
    assert res.mode == "mock"
    # No real call occurs — even with flag on, key_present is False.
    assert res.meta["key_present"] is False
    assert res.status == "blocked"
    # Provider status snapshot agrees.
    snap = provider_status(modality=modality, project=None, global_settings=GLOBAL)
    assert snap["mode"] == "mock"
    assert snap["real_capable"] is (modality == "voice")
    assert snap["would_use_real_provider"] is False


def test_ffmpeg_export_does_not_require_provider_secret(monkeypatch):
    monkeypatch.setenv("USE_REAL_EXPORT_PROVIDER", "true")
    snap = provider_status(modality="export", project=None, global_settings=GLOBAL)
    assert snap["key_present"] is True
    assert snap["key_status"] == "not_required"
    assert snap["secret_ref"] is None


def test_provider_status_llm_is_real_capable():
    snap = provider_status(modality="llm", project=None, global_settings=GLOBAL)
    assert snap["real_capable"] is True
