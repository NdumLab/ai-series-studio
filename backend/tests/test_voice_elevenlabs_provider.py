"""Unit tests for guarded ElevenLabs voice provider integration."""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_episode_studio_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server  # noqa: E402
from providers import execute_provider, provider_status  # noqa: E402
from providers import executor as provider_executor  # noqa: E402
from providers.voice_elevenlabs import (  # noqa: E402
    ElevenLabsProviderError,
    ElevenLabsVoiceProvider,
    _ElevenLabsHttpClient,
)
from storage_service import storage_config  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


class _UpdateResult:
    def __init__(self, matched_count=0):
        self.matched_count = matched_count


class _Cursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def sort(self, key, direction):
        reverse = direction < 0
        self.rows.sort(key=lambda row: row.get(key, 0), reverse=reverse)
        return self

    async def to_list(self, length):
        return list(self.rows[:length])


class _FakeCollection:
    def __init__(self, rows=None):
        self.rows = [dict(row) for row in (rows or [])]

    def _matches(self, row, query):
        for key, expected in query.items():
            if key == "$and":
                if not all(self._matches(row, part) for part in expected):
                    return False
                continue
            if key == "$or":
                if not any(self._matches(row, part) for part in expected):
                    return False
                continue
            if isinstance(expected, dict):
                if "$exists" in expected:
                    exists = key in row
                    if exists is not bool(expected["$exists"]):
                        return False
                    continue
                if "$gte" in expected and row.get(key, 0) < expected["$gte"]:
                    return False
                if "$in" in expected and row.get(key) not in expected["$in"]:
                    return False
                continue
            if row.get(key) != expected:
                return False
        return True

    async def find_one(self, query, projection=None):
        return next((row for row in self.rows if self._matches(row, query)), None)

    def find(self, query, projection=None):
        return _Cursor(row for row in self.rows if self._matches(row, query))

    async def count_documents(self, query):
        return len([row for row in self.rows if self._matches(row, query)])

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return SimpleNamespace(inserted_id=doc.get("id"))

    async def update_one(self, query, update, upsert=False):
        row = await self.find_one(query)
        if row is None:
            return _UpdateResult()
        if "$set" in update:
            row.update(update["$set"])
        if "$inc" in update:
            for key, value in update["$inc"].items():
                row[key] = int(row.get(key) or 0) + int(value)
        return _UpdateResult(matched_count=1)


class _FakeDB:
    def __init__(self, *, provider_settings=None):
        self.users = _FakeCollection([{
            "id": "user-1",
            "credits": 25,
            "credits_reserved": 0,
            "credits_used": 0,
        }])
        self.projects = _FakeCollection([{
            "id": "project-1",
            "user_id": "user-1",
            "title": "Project 1",
        }])
        self.scenes = _FakeCollection([{
            "id": "scene-1",
            "project_id": "project-1",
            "title": "Opening",
            "dialogue": "A single line of narration.",
            "visual_prompt": "Wide establishing shot",
            "voice": "Narrator-Warm",
        }])
        self.provider_settings = _FakeCollection([
            provider_settings or {
                "id": server.SETTINGS_DOC_ID,
                "mock_mode": True,
                **server.DEFAULT_PROVIDER_SETTINGS,
                "voice": {"provider": "elevenlabs", "model": "eleven-v3"},
            }
        ])
        self.assets = _FakeCollection()
        self.credit_events = _FakeCollection()
        self.generations = _FakeCollection()
        self.provider_activity = _FakeCollection()


@pytest.fixture(autouse=True)
def clean_state(monkeypatch, tmp_path):
    for key in [
        "USE_REAL_VOICE_PROVIDER",
        "ELEVENLABS_DEFAULT_VOICE_ID",
        "SECRETS_BACKEND",
    ]:
        monkeypatch.delenv(key, raising=False)
    ElevenLabsVoiceProvider.client_factory = None
    server.set_activity_recorder(None)
    monkeypatch.setattr(
        server,
        "ASSET_STORAGE_CONFIG",
        storage_config(
            {
                "ASSET_STORAGE_BACKEND": "local",
                "ASSET_LOCAL_DIR": str(tmp_path / "assets"),
                "ASSET_PUBLIC_BASE_URL": "http://testserver/assets",
            },
            root_dir=tmp_path,
        ),
    )
    yield
    ElevenLabsVoiceProvider.client_factory = None
    server.set_activity_recorder(None)


def test_elevenlabs_provider_posts_tts_payload_and_returns_audio(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def text_to_speech(self, *, voice_id, model_id, text):
            calls.append({
                "api_key": self.api_key,
                "voice_id": voice_id,
                "model_id": model_id,
                "text": text,
            })
            return b"mp3-bytes"

    monkeypatch.setattr("providers.voice_elevenlabs.get_provider_secret_value", lambda *_: '"el-key"')
    ElevenLabsVoiceProvider.client_factory = FakeClient

    res = _run(ElevenLabsVoiceProvider("elevenlabs", "eleven-v3").run(
        text="Hello",
        voice_id="voice-123",
    ))

    assert res.status == "success"
    assert res.output["audio_bytes"] == b"mp3-bytes"
    assert res.output["mime_type"] == "audio/mpeg"
    assert calls == [{
        "api_key": "el-key",
        "voice_id": "voice-123",
        "model_id": "eleven_v3",
        "text": "Hello",
    }]


def test_elevenlabs_provider_requires_voice_id_before_request(monkeypatch):
    def fail_factory(_api_key):
        raise AssertionError("client should not be created without voice_id")

    monkeypatch.setattr("providers.voice_elevenlabs.get_provider_secret_value", lambda *_: "el-key")
    ElevenLabsVoiceProvider.client_factory = fail_factory

    res = _run(ElevenLabsVoiceProvider("elevenlabs", "eleven-v3").run(text="Hello"))

    assert res.status == "failed"
    assert "voice id" in res.meta["provider_error_message"].lower()


def test_elevenlabs_http_errors_are_sanitized():
    exc = ElevenLabsProviderError(
        http_status=403,
        message='{"error":"bad","xi-api-key":"sk-secret-value"}',
        endpoint="text_to_speech",
    )

    assert exc.http_status == 403
    assert "sk-secret-value" not in exc.safe_message
    assert "[redacted]" in exc.safe_message


def test_elevenlabs_http_client_uses_documented_endpoint():
    client = _ElevenLabsHttpClient("el-key")

    assert client.base_url == "https://api.elevenlabs.io/v1/text-to-speech"


def test_voice_status_real_capable_for_elevenlabs(monkeypatch):
    monkeypatch.setenv("USE_REAL_VOICE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")

    snap = provider_status(
        modality="voice",
        project=None,
        global_settings={"voice": {"provider": "elevenlabs", "model": "eleven-v3"}},
    )

    assert snap["real_capable"] is True
    assert snap["would_use_real_provider"] is True
    assert "el-key" not in str(snap)
    assert "secret_value" not in str(snap).lower()


def test_generate_scene_voice_real_stores_asset_and_deducts_after_success(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setenv("USE_REAL_VOICE_PROVIDER", "true")
    monkeypatch.setenv("ELEVENLABS_DEFAULT_VOICE_ID", "voice-123")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    monkeypatch.setattr("providers.voice_elevenlabs.get_provider_secret_value", lambda *_: "el-key")
    server.set_activity_recorder(server._record_provider_activity)

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def text_to_speech(self, *, voice_id, model_id, text):
            assert self.api_key == "el-key"
            assert voice_id == "voice-123"
            assert model_id == "eleven_v3"
            assert text == "A single line of narration."
            return b"voice-audio"

    ElevenLabsVoiceProvider.client_factory = FakeClient

    out = _run(server.generate_scene_voice("scene-1", user={"id": "user-1"}))

    assert out["mode"] == "real"
    assert out["cost"] == 1
    assert out["remaining_credits"] == 24
    assert out["voice_audio_url"].startswith("http://testserver/assets/")
    assert fake_db.scenes.rows[0]["voice_audio_url"] == out["voice_audio_url"]
    assert fake_db.users.rows[0]["credits"] == 24
    assert fake_db.credit_events.rows[0]["credits_delta"] == -1
    asset = fake_db.assets.rows[0]
    assert asset["asset_type"] == "voice_audio"
    assert asset["scene_id"] == "scene-1"
    assert asset["mime_type"] == "audio/mpeg"
    assert asset["size_bytes"] == len(b"voice-audio")
    activity = fake_db.provider_activity.rows[0]
    assert activity["modality"] == "voice"
    assert activity["status"] == "success"
    assert "voice_id" not in activity
    assert "text" not in activity


def test_generate_scene_voice_blocked_does_not_deduct_or_store(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setenv("USE_REAL_VOICE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: False)

    with pytest.raises(server.HTTPException) as exc:
        _run(server.generate_scene_voice("scene-1", user={"id": "user-1"}))

    assert exc.value.status_code == 503
    assert fake_db.users.rows[0]["credits"] == 25
    assert fake_db.assets.rows == []
    assert fake_db.credit_events.rows == []
