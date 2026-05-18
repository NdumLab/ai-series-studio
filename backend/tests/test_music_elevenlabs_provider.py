"""Unit tests for guarded ElevenLabs music/SFX provider integration."""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_episode_studio_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server  # noqa: E402
from providers import provider_status  # noqa: E402
from providers import executor as provider_executor  # noqa: E402
from providers.music_elevenlabs import (  # noqa: E402
    ElevenLabsMusicProvider,
    ElevenLabsMusicProviderError,
    _ElevenLabsMusicHttpClient,
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
            "duration": 8,
            "location": "Rooftop",
            "visual_prompt": "Wide establishing shot",
            "music_mood": "Tense",
        }])
        self.provider_settings = _FakeCollection([
            provider_settings or {
                "id": server.SETTINGS_DOC_ID,
                "mock_mode": True,
                **server.DEFAULT_PROVIDER_SETTINGS,
                "music": {"provider": "elevenlabs-music", "model": "music-v1"},
            }
        ])
        self.assets = _FakeCollection()
        self.credit_events = _FakeCollection()
        self.generations = _FakeCollection()
        self.provider_activity = _FakeCollection()


@pytest.fixture(autouse=True)
def clean_state(monkeypatch, tmp_path):
    for key in [
        "USE_REAL_MUSIC_PROVIDER",
        "MUSIC_REAL_PROVIDER",
        "MUSIC_REAL_MODEL",
        "SECRETS_BACKEND",
    ]:
        monkeypatch.delenv(key, raising=False)
    ElevenLabsMusicProvider.client_factory = None
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
    ElevenLabsMusicProvider.client_factory = None
    server.set_activity_recorder(None)


def test_elevenlabs_music_provider_posts_compose_payload(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def compose_music(self, *, prompt, model_id, duration_seconds):
            calls.append({
                "api_key": self.api_key,
                "prompt": prompt,
                "model_id": model_id,
                "duration_seconds": duration_seconds,
            })
            return b"music-bytes", "song-123"

    monkeypatch.setattr("providers.music_elevenlabs.get_provider_secret_value", lambda *_: '"el-key"')
    ElevenLabsMusicProvider.client_factory = FakeClient

    res = _run(ElevenLabsMusicProvider("elevenlabs-music", "music-v1").run(
        prompt="Tense strings",
        duration_seconds=8,
    ))

    assert res.status == "success"
    assert res.provider_job_id == "song-123"
    assert res.output["audio_bytes"] == b"music-bytes"
    assert res.output["audio_kind"] == "music"
    assert calls == [{
        "api_key": "el-key",
        "prompt": "Tense strings",
        "model_id": "music_v1",
        "duration_seconds": 8,
    }]


def test_elevenlabs_music_provider_supports_sfx_endpoint(monkeypatch):
    calls = []

    class FakeClient:
        def __init__(self, _api_key):
            pass

        def sound_effect(self, *, text, model_id, duration_seconds):
            calls.append({"text": text, "model_id": model_id, "duration_seconds": duration_seconds})
            return b"sfx-bytes", None

    monkeypatch.setattr("providers.music_elevenlabs.get_provider_secret_value", lambda *_: "el-key")
    ElevenLabsMusicProvider.client_factory = FakeClient

    res = _run(ElevenLabsMusicProvider("elevenlabs-music", "sound-effects").run(
        prompt="Metal door slam",
        duration_seconds=2,
        audio_kind="sfx",
    ))

    assert res.status == "success"
    assert res.output["audio_kind"] == "sfx"
    assert res.meta["endpoint"] == "sound-generation"
    assert calls == [{
        "text": "Metal door slam",
        "model_id": "eleven_text_to_sound_v2",
        "duration_seconds": 2,
    }]


def test_elevenlabs_music_provider_requires_prompt_before_request(monkeypatch):
    def fail_factory(_api_key):
        raise AssertionError("client should not be created without prompt")

    monkeypatch.setattr("providers.music_elevenlabs.get_provider_secret_value", lambda *_: "el-key")
    ElevenLabsMusicProvider.client_factory = fail_factory

    res = _run(ElevenLabsMusicProvider("elevenlabs-music", "music-v1").run(prompt=""))

    assert res.status == "failed"
    assert "prompt is empty" in res.meta["provider_error_message"].lower()


def test_elevenlabs_music_http_errors_are_sanitized():
    exc = ElevenLabsMusicProviderError(
        http_status=403,
        message='{"error":"bad","xi-api-key":"sk-secret-value"}',
        endpoint="music",
    )

    assert exc.http_status == 403
    assert "sk-secret-value" not in exc.safe_message
    assert "[redacted]" in exc.safe_message


def test_elevenlabs_music_http_client_uses_documented_endpoints():
    client = _ElevenLabsMusicHttpClient("el-key")

    assert client.base_url == "https://api.elevenlabs.io/v1"


def test_music_status_real_capable_for_elevenlabs(monkeypatch):
    monkeypatch.setenv("USE_REAL_MUSIC_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")

    snap = provider_status(
        modality="music",
        project=None,
        global_settings={"music": {"provider": "elevenlabs-music", "model": "music-v1"}},
    )

    assert snap["real_capable"] is True
    assert snap["would_use_real_provider"] is True
    assert "el-key" not in str(snap)
    assert "secret_value" not in str(snap).lower()


def test_generate_scene_music_real_stores_asset_and_deducts_after_success(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setenv("USE_REAL_MUSIC_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    monkeypatch.setattr("providers.music_elevenlabs.get_provider_secret_value", lambda *_: "el-key")
    server.set_activity_recorder(server._record_provider_activity)

    class FakeClient:
        def __init__(self, api_key):
            self.api_key = api_key

        def compose_music(self, *, prompt, model_id, duration_seconds):
            assert self.api_key == "el-key"
            assert "tense" in prompt.lower()
            assert model_id == "music_v1"
            assert duration_seconds == 8
            return b"music-audio", "song-123"

    ElevenLabsMusicProvider.client_factory = FakeClient

    out = _run(server.generate_scene_music("scene-1", user={"id": "user-1"}))

    assert out["mode"] == "real"
    assert out["cost"] == 2
    assert out["remaining_credits"] == 23
    assert out["music_audio_url"].startswith("http://testserver/assets/")
    assert fake_db.scenes.rows[0]["music_audio_url"] == out["music_audio_url"]
    assert fake_db.users.rows[0]["credits"] == 23
    assert fake_db.credit_events.rows[0]["credits_delta"] == -2
    asset = fake_db.assets.rows[0]
    assert asset["asset_type"] == "music_audio"
    assert asset["scene_id"] == "scene-1"
    assert asset["provider_job_id"] == "song-123"
    assert asset["size_bytes"] == len(b"music-audio")
    activity = fake_db.provider_activity.rows[0]
    assert activity["modality"] == "music"
    assert activity["status"] == "success"
    assert "prompt" not in activity


def test_generate_scene_music_blocked_does_not_deduct_or_store(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setenv("USE_REAL_MUSIC_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: False)

    with pytest.raises(server.HTTPException) as exc:
        _run(server.generate_scene_music("scene-1", user={"id": "user-1"}))

    assert exc.value.status_code == 503
    assert fake_db.users.rows[0]["credits"] == 25
    assert fake_db.assets.rows == []
    assert fake_db.credit_events.rows == []
