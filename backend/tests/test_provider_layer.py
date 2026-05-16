"""Unit tests for the Phase 2A provider service layer (resolver + executor)."""
import asyncio
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from providers import (  # noqa: E402
    MODALITIES,
    execute_provider,
    provider_status,
    resolve_provider,
    resolve_voice_for_character,
    run_modality_test,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


GLOBAL = {
    "llm":    {"provider": "openai",      "model": "gpt-5.2"},
    "image":  {"provider": "fal",         "model": "flux-pro"},
    "video":  {"provider": "sora-2",      "model": "sora-2"},
    "voice":  {"provider": "elevenlabs",  "model": "eleven-v3"},
    "music":  {"provider": "suno",        "model": "v4"},
    "export": {"provider": "ffmpeg-local","model": "ffmpeg-6"},
}


# ---------- Resolver ----------
def test_resolver_global_fallback_when_no_override():
    proj = {"provider_override_enabled": False, "llm_provider": "ignored", "llm_model": "x"}
    r = resolve_provider(modality="llm", project=proj, global_settings=GLOBAL)
    assert r == {
        "modality": "llm",
        "provider": "openai",
        "model": "gpt-5.2",
        "source": "global",
    }


def test_resolver_project_override_beats_global():
    proj = {
        "provider_override_enabled": True,
        "image_provider": "gemini-nano-banana",
        "image_model": "nano-banana",
    }
    r = resolve_provider(modality="image", project=proj, global_settings=GLOBAL)
    assert r["provider"] == "gemini-nano-banana"
    assert r["model"] == "nano-banana"
    assert r["source"] == "project"


def test_resolver_global_fallback_when_override_on_but_project_empty():
    """override=on but the project hasn't picked a value for this modality."""
    proj = {"provider_override_enabled": True, "music_provider": "", "music_model": ""}
    r = resolve_provider(modality="music", project=proj, global_settings=GLOBAL)
    assert r["provider"] == "suno"
    assert r["source"] == "global-fallback"


def test_resolver_hard_fallback_when_nothing_configured():
    """No project, no global → hard-coded mock identifiers per modality."""
    for m in MODALITIES:
        r = resolve_provider(modality=m, project=None, global_settings={})
        assert r["source"] == "hard-fallback"
        assert r["provider"].startswith("mock-")


def test_resolver_rejects_unknown_modality():
    with pytest.raises(ValueError):
        resolve_provider(modality="not-a-modality", project=None, global_settings=GLOBAL)


# ---------- Voice resolver with character override ----------
def test_voice_resolver_character_override_beats_project_and_global():
    char = {"voice_provider": "openai-tts", "voice_model": "tts-1-hd"}
    proj = {
        "provider_override_enabled": True,
        "voice_provider": "elevenlabs",
        "voice_model": "eleven-v3",
    }
    r = resolve_voice_for_character(character=char, project=proj, global_settings=GLOBAL)
    assert r["source"] == "character"
    assert r["provider"] == "openai-tts"
    assert r["model"] == "tts-1-hd"


def test_voice_resolver_falls_through_to_project_when_no_character_override():
    char = {"voice_provider": "", "voice_model": ""}
    proj = {
        "provider_override_enabled": True,
        "voice_provider": "google-tts",
        "voice_model": "studio",
    }
    r = resolve_voice_for_character(character=char, project=proj, global_settings=GLOBAL)
    assert r["source"] == "project"
    assert r["provider"] == "google-tts"


def test_voice_resolver_falls_through_to_global_when_neither():
    r = resolve_voice_for_character(character=None, project=None, global_settings=GLOBAL)
    assert r["source"] == "global"
    assert r["provider"] == "elevenlabs"


# ---------- Executor: flag + key gating ----------
@pytest.fixture
def clean_env(monkeypatch):
    for k in [
        "USE_REAL_LLM_PROVIDER", "USE_REAL_IMAGE_PROVIDER", "USE_REAL_VIDEO_PROVIDER",
        "USE_REAL_VOICE_PROVIDER", "USE_REAL_MUSIC_PROVIDER", "USE_REAL_EXPORT_PROVIDER",
        "SECRETS_BACKEND", "SSM_PROVIDER_KEY_PREFIX", "AWS_REGION",
    ]:
        monkeypatch.delenv(k, raising=False)
    yield


def test_executor_runs_mock_when_flag_off(clean_env):
    res = _run(execute_provider(
        modality="image", project=None, global_settings=GLOBAL, estimated_credits=2,
    ))
    assert res.mode == "mock"
    assert res.status == "success"
    assert res.estimated_credits == 2
    assert res.provider_name == "fal"
    assert res.meta["feature_flag_enabled"] is False
    assert res.meta["key_present"] is False
    assert "Mock mode active" in res.message


def test_executor_blocks_when_flag_on_but_no_key(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    res = _run(execute_provider(
        modality="video", project=None, global_settings=GLOBAL, estimated_credits=12,
    ))
    # No real network call was made — the mock ran instead and status flips to blocked.
    assert res.mode == "mock"
    assert res.status == "blocked"
    assert res.meta["feature_flag_enabled"] is True
    assert res.meta["key_present"] is False
    assert "no API key" in res.message.lower() or "blocked" in res.message.lower()


def test_executor_estimated_credits_is_respected(clean_env):
    res = _run(execute_provider(
        modality="voice", project=None, global_settings=GLOBAL, estimated_credits=7,
    ))
    assert res.estimated_credits == 7


def test_executor_uses_resolved_voice_for_voice_modality(clean_env):
    char = {"voice_provider": "openai-tts", "voice_model": "tts-1"}
    res = _run(execute_provider(
        modality="voice", project=None, character=char, global_settings=GLOBAL,
    ))
    assert res.provider_name == "openai-tts"
    assert res.model_name == "tts-1"
    assert res.meta["resolved_source"] == "character"


def test_run_modality_test_returns_mock_response(clean_env):
    out = _run(run_modality_test(
        modality="llm", project=None, global_settings=GLOBAL,
    ))
    assert out["ok"] is True
    assert out["mode"] == "mock"
    assert out["status"] == "skipped"
    assert "no real provider call" in out["message"].lower()


# ---------- Status snapshot ----------
def test_provider_status_snapshot(clean_env):
    snap = provider_status(modality="export", project=None, global_settings=GLOBAL)
    assert snap["mode"] == "mock"
    assert snap["would_use_real_provider"] is False
    assert snap["key_status"] == "not_configured"
    assert snap["secrets_backend"] == "disabled"
    assert snap["selected_provider"] == "ffmpeg-local"
    assert snap["selected_model"] == "ffmpeg-6"
    assert snap["status"] == "mock"


def test_provider_status_image_blocked_when_flag_on_and_key_missing(monkeypatch):
    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setenv("SECRETS_BACKEND", "disabled")

    snap = provider_status(modality="image", project=None, global_settings=GLOBAL)

    assert snap["feature_flag_enabled"] is True
    assert snap["key_present"] is False
    assert snap["key_status"] == "not_configured"
    assert snap["secrets_backend"] == "disabled"
    assert snap["would_use_real_provider"] is False
    assert snap["status"] == "blocked"


def test_provider_status_rejects_unknown_modality():
    with pytest.raises(ValueError):
        provider_status(modality="bogus", project=None, global_settings=GLOBAL)
