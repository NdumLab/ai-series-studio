"""Unit tests for guarded OpenAI image provider execution."""
import asyncio
import base64
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_episode_studio_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from providers import ProviderResult, execute_provider, provider_status, set_activity_recorder  # noqa: E402
from providers import executor as provider_executor  # noqa: E402
from providers.image_openai import OpenAIImageProvider  # noqa: E402
from storage_service import storage_config  # noqa: E402
import server  # noqa: E402


GLOBAL_OPENAI_IMAGE = {
    "image": {"provider": "openai-image", "model": "gpt-image-1"},
}
GLOBAL_FAL_IMAGE = {
    "image": {"provider": "fal", "model": "flux-pro"},
}


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for key in [
        "USE_REAL_IMAGE_PROVIDER",
        "SECRETS_BACKEND",
        "SSM_PROVIDER_KEY_PREFIX",
        "AWS_REGION",
    ]:
        monkeypatch.delenv(key, raising=False)
    set_activity_recorder(None)
    OpenAIImageProvider.client_factory = None
    yield
    set_activity_recorder(None)
    OpenAIImageProvider.client_factory = None


def test_real_image_blocked_when_flag_false(monkeypatch):
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)

    res = _run(execute_provider(
        modality="image",
        project=None,
        global_settings=GLOBAL_OPENAI_IMAGE,
        estimated_credits=2,
        prompt="cinematic scene",
    ))

    assert res.mode == "mock"
    assert res.status == "success"
    assert res.provider_name == "openai-image"


def test_real_image_blocked_when_key_missing(monkeypatch):
    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: False)

    res = _run(execute_provider(
        modality="image",
        project=None,
        global_settings=GLOBAL_OPENAI_IMAGE,
        estimated_credits=2,
        prompt="cinematic scene",
    ))

    assert res.mode == "mock"
    assert res.status == "blocked"
    assert res.meta["key_present"] is False


def test_real_image_blocked_if_effective_provider_is_not_openai(monkeypatch):
    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)

    res = _run(execute_provider(
        modality="image",
        project=None,
        global_settings=GLOBAL_FAL_IMAGE,
        estimated_credits=2,
        prompt="cinematic scene",
    ))

    assert res.mode == "mock"
    assert res.status == "blocked"
    snap = provider_status(modality="image", project=None, global_settings=GLOBAL_FAL_IMAGE)
    assert snap["real_capable"] is False
    assert snap["would_use_real_provider"] is False


def test_successful_openai_image_response_returns_bytes(monkeypatch):
    image_bytes = b"fake-png-bytes"
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    class _FakeImages:
        @staticmethod
        def generate(**kwargs):
            assert kwargs["model"] == "gpt-image-1"
            assert kwargs["prompt"] == "cinematic scene"
            return SimpleNamespace(
                id="img-job-1",
                data=[SimpleNamespace(b64_json=image_b64)],
            )

    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr("providers.image_openai.get_provider_secret_value", lambda *_: "unit-secret")
    OpenAIImageProvider.client_factory = lambda api_key: SimpleNamespace(images=_FakeImages)

    captured = []
    set_activity_recorder(lambda row: _capture(captured, row))
    res = _run(execute_provider(
        modality="image",
        project=None,
        global_settings=GLOBAL_OPENAI_IMAGE,
        estimated_credits=2,
        prompt="cinematic scene",
        image_kind="scene",
    ))

    assert res.mode == "real"
    assert res.status == "success"
    assert res.provider_job_id == "img-job-1"
    assert res.output["image_bytes"] == image_bytes
    assert captured[-1]["mode"] == "real"
    assert captured[-1]["status"] == "success"
    assert "unit-secret" not in str(captured)


async def _capture(rows, row):
    rows.append(row)


def test_failed_openai_provider_does_not_fallback_or_hide_failure(monkeypatch):
    class _FakeImages:
        @staticmethod
        def generate(**kwargs):
            raise RuntimeError("network should be mocked")

    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr("providers.image_openai.get_provider_secret_value", lambda *_: "unit-secret")
    OpenAIImageProvider.client_factory = lambda api_key: SimpleNamespace(images=_FakeImages)

    captured = []
    set_activity_recorder(lambda row: _capture(captured, row))
    res = _run(execute_provider(
        modality="image",
        project=None,
        global_settings=GLOBAL_OPENAI_IMAGE,
        estimated_credits=2,
        prompt="cinematic scene",
    ))

    assert res.mode == "real"
    assert res.status == "failed"
    assert res.error == "RuntimeError"
    assert captured[-1]["status"] == "failed"


def test_provider_status_does_not_expose_secret_when_real_ready(monkeypatch):
    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")

    snap = provider_status(modality="image", project=None, global_settings=GLOBAL_OPENAI_IMAGE)

    assert snap["mode"] == "real"
    assert snap["real_capable"] is True
    assert snap["would_use_real_provider"] is True
    assert "unit-secret" not in str(snap)


class _InsertCollection:
    def __init__(self, rows=None):
        self.rows = [dict(row) for row in (rows or [])]

    def _matches(self, row, query):
        for key, expected in query.items():
            if isinstance(expected, dict) and "$in" in expected:
                if row.get(key) not in expected["$in"]:
                    return False
                continue
            if row.get(key) != expected:
                return False
        return True

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return SimpleNamespace(inserted_id=doc.get("id"))

    async def count_documents(self, query):
        return len([row for row in self.rows if self._matches(row, query)])


class _FindOneCollection(_InsertCollection):
    async def find_one(self, query, projection=None):
        return next((row for row in self.rows if self._matches(row, query)), None)


class _FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def sort(self, key, direction):
        self.rows = sorted(self.rows, key=lambda row: row.get(key, ""))
        return self

    async def to_list(self, limit):
        return [row.copy() for row in self.rows[:limit]]


class _MutableCollection(_FindOneCollection):
    def find(self, query, projection=None):
        return _FakeCursor([row for row in self.rows if self._matches(row, query)])

    async def update_one(self, query, update, upsert=False):
        row = next((row for row in self.rows if self._matches(row, query)), None)
        if row is None:
            if upsert:
                row = {k: v for k, v in query.items() if not isinstance(v, dict)}
                self.rows.append(row)
            else:
                return SimpleNamespace(matched_count=0, modified_count=0)
        for key, value in (update.get("$set") or {}).items():
            row[key] = value
        for key, value in (update.get("$inc") or {}).items():
            row[key] = row.get(key, 0) + value
        return SimpleNamespace(matched_count=1, modified_count=1)

    def _matches(self, row, query):
        for key, value in query.items():
            if key == "$and":
                if not all(self._matches(row, part) for part in value):
                    return False
                continue
            if key == "$or":
                if not any(self._matches(row, part) for part in value):
                    return False
                continue
            current = row.get(key)
            if isinstance(value, dict):
                if "$gte" in value and not (current is not None and current >= value["$gte"]):
                    return False
                if "$exists" in value and ((key in row) != value["$exists"]):
                    return False
                if "$in" in value and current not in value["$in"]:
                    return False
            elif current != value:
                return False
        return True


def _fake_server_db(*, project, user, scenes=None, characters=None):
    settings = {
        "id": server.SETTINGS_DOC_ID,
        "mock_mode": True,
        **server.DEFAULT_PROVIDER_SETTINGS,
        "image": {"provider": "openai-image", "model": "gpt-image-1"},
    }
    return SimpleNamespace(
        provider_settings=_MutableCollection([settings]),
        projects=_MutableCollection([project]),
        users=_MutableCollection([user]),
        scenes=_MutableCollection(scenes or []),
        characters=_MutableCollection(characters or []),
        segments=_MutableCollection([]),
        assets=_MutableCollection([]),
        generations=_MutableCollection([]),
        credit_events=_MutableCollection([]),
        provider_activity=_MutableCollection([]),
    )


def test_successful_real_image_asset_metadata_is_saved(monkeypatch, tmp_path):
    fake_assets = _InsertCollection()
    monkeypatch.setattr(server, "db", SimpleNamespace(assets=fake_assets))
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
    })
    monkeypatch.setattr(server, "ASSET_STORAGE_CONFIG", cfg)
    res = ProviderResult(
        modality="image",
        provider_name="openai-image",
        model_name="gpt-image-1",
        mode="real",
        output={"image_bytes": b"image-bytes", "mime_type": "image/png"},
        provider_job_id="img-job-1",
    )

    url = _run(server._store_generated_image_asset(
        user={"id": "user-1"},
        project_id="project-1",
        scene_id="scene-1",
        asset_type="scene_image",
        provider_result=res,
    ))

    assert url.startswith("/assets/user-1/project-1/scene_image/")
    assert fake_assets.rows[0]["provider_name"] == "openai-image"
    assert fake_assets.rows[0]["asset_type"] == "scene_image"
    assert fake_assets.rows[0]["size_bytes"] == len(b"image-bytes")
    assert (tmp_path / fake_assets.rows[0]["storage_key"]).exists()


def test_real_image_success_updates_scene_image_url(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
        "ASSET_PUBLIC_BASE_URL": "https://assets.example.com/assets",
    })
    monkeypatch.setattr(server, "ASSET_STORAGE_CONFIG", cfg)
    fake_db = _fake_server_db(
        project={"id": "project-1", "user_id": "user-1", "provider_override_enabled": False},
        user={"id": "user-1", "credits": 250, "credits_reserved": 0, "credits_used": 0},
        scenes=[{
            "id": "scene-1",
            "project_id": "project-1",
            "visual_prompt": "cinematic city",
            "status": "draft",
        }],
    )
    monkeypatch.setattr(server, "db", fake_db)

    async def fake_execute_provider(**kwargs):
        return ProviderResult(
            modality="image",
            provider_name="openai-image",
            model_name="gpt-image-1",
            mode="real",
            status="success",
            output={"image_bytes": b"real-scene-image", "mime_type": "image/png"},
            provider_job_id="scene-job-1",
        )

    monkeypatch.setattr(server, "execute_provider", fake_execute_provider)

    body = _run(server.generate_image("scene-1", user={"id": "user-1"}))

    scene = fake_db.scenes.rows[0]
    assert body["image_url"].startswith("https://assets.example.com/assets/")
    assert scene["image_url"] == body["image_url"]
    assert scene["status"] == "image_ready"
    assert fake_db.assets.rows[0]["provider_name"] == "openai-image"
    assert fake_db.assets.rows[0]["size_bytes"] == len(b"real-scene-image")


def test_real_character_image_success_updates_reference_image_url(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_REAL_IMAGE_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
        "ASSET_PUBLIC_BASE_URL": "https://assets.example.com/assets",
    })
    monkeypatch.setattr(server, "ASSET_STORAGE_CONFIG", cfg)
    fake_db = _fake_server_db(
        project={"id": "project-1", "user_id": "user-1", "provider_override_enabled": False},
        user={"id": "user-1", "credits": 250, "credits_reserved": 0, "credits_used": 0},
        characters=[{
            "id": "char-1",
            "project_id": "project-1",
            "name": "Ari",
            "description": "pilot",
            "voice_style": "calm",
        }],
    )
    monkeypatch.setattr(server, "db", fake_db)

    async def fake_execute_provider(**kwargs):
        return ProviderResult(
            modality="image",
            provider_name="openai-image",
            model_name="gpt-image-1",
            mode="real",
            status="success",
            output={"image_bytes": b"real-character-image", "mime_type": "image/png"},
            provider_job_id="char-job-1",
        )

    monkeypatch.setattr(server, "execute_provider", fake_execute_provider)

    body = _run(server.generate_character_image("char-1", user={"id": "user-1"}))

    character = fake_db.characters.rows[0]
    assert body["reference_image_url"].startswith("https://assets.example.com/assets/")
    assert character["reference_image_url"] == body["reference_image_url"]
    assert fake_db.assets.rows[0]["asset_type"] == "character_image"
    assert fake_db.assets.rows[0]["character_id"] == "char-1"


def test_legacy_localhost_asset_urls_are_rewritten_for_browser(monkeypatch, tmp_path):
    cfg = storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
        "ASSET_PUBLIC_BASE_URL": "https://assets.example.com/assets",
    })
    monkeypatch.setattr(server, "ASSET_STORAGE_CONFIG", cfg)

    assert (
        server._browser_safe_asset_url("http://localhost:8000/assets/user/project/scene.png")
        == "https://assets.example.com/assets/user/project/scene.png"
    )
    assert (
        server._browser_safe_asset_url("http://127.0.0.1:8000/assets/user/project/char.png")
        == "https://assets.example.com/assets/user/project/char.png"
    )


def test_image_readiness_status_includes_activation_checklist(monkeypatch):
    monkeypatch.setenv("REAL_IMAGE_SINGLE_TEST_MODE", "true")
    fake_assets = _InsertCollection([
        {
            "user_id": "user-1",
            "asset_type": "scene_image",
            "provider_name": "openai-image",
        }
    ])
    fake_provider_settings = _FindOneCollection([
        {
            "id": server.SETTINGS_DOC_ID,
            "mock_mode": True,
            **server.DEFAULT_PROVIDER_SETTINGS,
            "image": {"provider": "openai-image", "model": "gpt-image-1"},
        }
    ])
    monkeypatch.setattr(
        server,
        "db",
        SimpleNamespace(assets=fake_assets, provider_settings=fake_provider_settings),
    )

    status = _run(server.providers_status_endpoint("image", user={
        "id": "user-1",
        "credits": 250,
        "credits_reserved": 0,
        "credits_used": 0,
    }))

    assert status["selected_provider"] == "openai-image"
    assert status["selected_model"] == "gpt-image-1"
    assert status["feature_flag_enabled"] is False
    assert status["key_present"] is False
    assert status["real_capable"] is True
    assert status["asset_storage_backend"] == server.ASSET_STORAGE_CONFIG.backend
    assert status["available_credits"] == 250
    assert status["provider_activity_logging"] == "enabled"
    assert status["single_image_test_mode"] is True
    assert status["single_image_test_limits"] == {"scene_image": 1, "character_image": 1}
    assert status["single_image_test_usage"]["scene_image"] == 1
    assert "unit-secret" not in str(status)


def test_real_image_single_test_guard_blocks_second_scene_image(monkeypatch):
    monkeypatch.setenv("REAL_IMAGE_SINGLE_TEST_MODE", "true")
    fake_assets = _InsertCollection([
        {
            "user_id": "user-1",
            "asset_type": "scene_image",
            "provider_name": "openai-image",
        }
    ])
    monkeypatch.setattr(server, "db", SimpleNamespace(assets=fake_assets))

    with pytest.raises(server.HTTPException) as exc:
        _run(server._assert_real_image_single_test_allowed(
            user={"id": "user-1"},
            asset_type="scene_image",
            status_snapshot={"would_use_real_provider": True},
        ))

    assert exc.value.status_code == 429
    assert exc.value.detail == server.REAL_IMAGE_SINGLE_TEST_MESSAGE


def test_real_image_single_test_guard_ignored_for_mock_mode(monkeypatch):
    monkeypatch.setenv("REAL_IMAGE_SINGLE_TEST_MODE", "true")
    fake_assets = _InsertCollection([
        {
            "user_id": "user-1",
            "asset_type": "scene_image",
            "provider_name": "openai-image",
        }
    ])
    monkeypatch.setattr(server, "db", SimpleNamespace(assets=fake_assets))

    _run(server._assert_real_image_single_test_allowed(
        user={"id": "user-1"},
        asset_type="scene_image",
        status_snapshot={"would_use_real_provider": False},
    ))
