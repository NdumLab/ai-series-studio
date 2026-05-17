"""Unit tests for disabled-by-default video provider guard foundation."""
import asyncio
import urllib.error
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
from providers.video_luma import LumaVideoProvider, _LumaHttpClient  # noqa: E402


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
                if "$gte" in expected:
                    if row.get(key, 0) < expected["$gte"]:
                        return False
                    continue
                if "$in" in expected:
                    if row.get(key) not in expected["$in"]:
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
    def __init__(self, *, segments=None, user=None, scene=None, provider_settings=None):
        self.users = _FakeCollection([
            user or {
                "id": "user-1",
                "credits": 250,
                "credits_reserved": 0,
                "credits_used": 0,
            }
        ])
        self.projects = _FakeCollection([
            {"id": "project-1", "user_id": "user-1", "title": "Project 1"},
        ])
        self.scenes = _FakeCollection([
            scene or {"id": "scene-1", "project_id": "project-1", "visual_prompt": "Wide shot"},
        ])
        self.segments = _FakeCollection(segments or [])
        self.provider_settings = _FakeCollection([
            provider_settings or {
                "id": server.SETTINGS_DOC_ID,
                "mock_mode": True,
                **server.DEFAULT_PROVIDER_SETTINGS,
                "video": {"provider": "luma", "model": "ray-2"},
            }
        ])
        self.credit_events = _FakeCollection()
        self.generations = _FakeCollection()
        self.assets = _FakeCollection()
        self.provider_activity = _FakeCollection()


class _FakeHTTPResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body

    def close(self):
        pass


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    for key in [
        "USE_REAL_VIDEO_PROVIDER",
        "VIDEO_REAL_PROVIDER",
        "VIDEO_REAL_MODEL",
        "VIDEO_SEGMENT_SECONDS",
        "VIDEO_MAX_SEGMENTS_PER_SCENE",
        "VIDEO_MAX_PROJECT_SECONDS",
        "SECRETS_BACKEND",
    ]:
        monkeypatch.delenv(key, raising=False)
    server.set_activity_recorder(None)
    LumaVideoProvider.client_factory = None
    monkeypatch.setattr(server.random, "random", lambda: 1.0)
    monkeypatch.setattr(server.random, "choice", lambda values: values[0])
    yield
    server.set_activity_recorder(None)
    LumaVideoProvider.client_factory = None


GLOBAL_LUMA = {"video": {"provider": "luma", "model": "ray-2"}}
GLOBAL_RUNWAY = {"video": {"provider": "runway", "model": "gen-4.5"}}


def test_real_video_blocked_when_flag_false(monkeypatch):
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)

    res = _run(execute_provider(
        modality="video",
        project=None,
        global_settings=GLOBAL_LUMA,
        estimated_credits=12,
        prompt="wide shot",
    ))

    assert res.mode == "mock"
    assert res.status == "success"
    assert res.provider_name == "luma"


def test_real_video_blocked_when_key_missing(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: False)

    res = _run(execute_provider(
        modality="video",
        project=None,
        global_settings=GLOBAL_LUMA,
        estimated_credits=12,
        prompt="wide shot",
    ))

    assert res.mode == "mock"
    assert res.status == "blocked"
    assert res.meta["key_present"] is False


def test_real_video_blocked_when_provider_is_not_luma(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)

    res = _run(execute_provider(
        modality="video",
        project=None,
        global_settings=GLOBAL_RUNWAY,
        estimated_credits=12,
        prompt="wide shot",
    ))

    assert res.mode == "mock"
    assert res.status == "blocked"
    snap = provider_status(modality="video", project=None, global_settings=GLOBAL_RUNWAY)
    assert snap["real_capable"] is False
    assert snap["would_use_real_provider"] is False


def test_no_real_network_calls_occur_when_video_guard_blocks(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "false")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)

    def fail_factory(_api_key):
        raise AssertionError("Luma client should not be created")

    LumaVideoProvider.client_factory = fail_factory

    res = _run(execute_provider(
        modality="video",
        project=None,
        global_settings=GLOBAL_LUMA,
        estimated_credits=12,
        prompt="wide shot",
    ))

    assert res.mode == "mock"


def test_luma_status_does_not_expose_secret_value(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")

    snap = provider_status(modality="video", project=None, global_settings=GLOBAL_LUMA)

    assert snap["selected_provider"] == "luma"
    assert snap["real_capable"] is True
    assert snap["would_use_real_provider"] is True
    assert "luma-secret" not in str(snap)
    assert "secret_value" not in str(snap).lower()


def test_video_guard_config_reads_safe_env_defaults(monkeypatch):
    monkeypatch.setenv("VIDEO_SEGMENT_SECONDS", "7")
    monkeypatch.setenv("VIDEO_MAX_SEGMENTS_PER_SCENE", "4")
    monkeypatch.setenv("VIDEO_MAX_PROJECT_SECONDS", "42")

    assert server.video_guard_config() == {
        "segment_seconds": 7,
        "max_segments_per_scene": 4,
        "max_project_seconds": 42,
    }


def test_segment_creation_respects_video_segment_seconds(monkeypatch):
    monkeypatch.setenv("VIDEO_SEGMENT_SECONDS", "7")
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)

    out = _run(server._create_scene_segment(
        "scene-1",
        expand_mode="initial",
        continuity_prompt=None,
        user={"id": "user-1"},
    ))

    assert out["duration"] == 7
    assert out["start_second"] == 0
    assert out["cost"] == server.COSTS["video_segment"]
    assert fake_db.users.rows[0]["credits"] == 250 - server.COSTS["video_segment"]
    assert fake_db.segments.rows[-1]["duration"] == 7


def test_scene_max_segment_guard_blocks_extra_expansion(monkeypatch):
    monkeypatch.setenv("VIDEO_MAX_SEGMENTS_PER_SCENE", "3")
    fake_db = _FakeDB(segments=[
        {"id": "seg-1", "scene_id": "scene-1", "project_id": "project-1", "duration": 5},
        {"id": "seg-2", "scene_id": "scene-1", "project_id": "project-1", "duration": 5},
        {"id": "seg-3", "scene_id": "scene-1", "project_id": "project-1", "duration": 5},
    ])
    monkeypatch.setattr(server, "db", fake_db)

    with pytest.raises(server.HTTPException) as exc:
        _run(server._create_scene_segment(
            "scene-1",
            expand_mode="expand",
            continuity_prompt=None,
            user={"id": "user-1"},
        ))

    assert exc.value.status_code == 400
    assert exc.value.detail == server.VIDEO_LIMIT_MESSAGE
    assert fake_db.users.rows[0]["credits"] == 250


def test_project_max_seconds_guard_blocks_extra_generation(monkeypatch):
    monkeypatch.setenv("VIDEO_SEGMENT_SECONDS", "5")
    monkeypatch.setenv("VIDEO_MAX_PROJECT_SECONDS", "10")
    fake_db = _FakeDB(segments=[
        {"id": "seg-1", "scene_id": "scene-1", "project_id": "project-1", "duration": 5},
        {"id": "seg-2", "scene_id": "other-scene", "project_id": "project-1", "duration": 5},
    ])
    monkeypatch.setattr(server, "db", fake_db)

    with pytest.raises(server.HTTPException) as exc:
        _run(server._create_scene_segment(
            "scene-1",
            expand_mode="expand",
            continuity_prompt=None,
            user={"id": "user-1"},
        ))

    assert exc.value.status_code == 400
    assert exc.value.detail == server.VIDEO_LIMIT_MESSAGE
    assert fake_db.users.rows[0]["credits"] == 250


def test_insufficient_credits_blocks_before_video_provider_call(monkeypatch):
    fake_db = _FakeDB(user={
        "id": "user-1",
        "credits": 1,
        "credits_reserved": 0,
        "credits_used": 0,
    })
    monkeypatch.setattr(server, "db", fake_db)

    async def fail_execute_provider(**kwargs):
        raise AssertionError("provider should not run without credits")

    monkeypatch.setattr(server, "execute_provider", fail_execute_provider)

    with pytest.raises(server.HTTPException) as exc:
        _run(server._create_scene_segment(
            "scene-1",
            expand_mode="initial",
            continuity_prompt=None,
            user={"id": "user-1"},
        ))

    assert exc.value.status_code == 402
    assert fake_db.segments.rows == []


def test_segment_cap_blocks_before_video_provider_call(monkeypatch):
    monkeypatch.setenv("VIDEO_MAX_SEGMENTS_PER_SCENE", "1")
    fake_db = _FakeDB(segments=[
        {"id": "seg-1", "scene_id": "scene-1", "project_id": "project-1", "duration": 5},
    ])
    monkeypatch.setattr(server, "db", fake_db)

    async def fail_execute_provider(**kwargs):
        raise AssertionError("provider should not run after duration cap")

    monkeypatch.setattr(server, "execute_provider", fail_execute_provider)

    with pytest.raises(server.HTTPException) as exc:
        _run(server._create_scene_segment(
            "scene-1",
            expand_mode="expand",
            continuity_prompt=None,
            user={"id": "user-1"},
        ))

    assert exc.value.status_code == 400
    assert fake_db.users.rows[0]["credits"] == 250


def test_mock_video_generation_still_works_inside_limits(monkeypatch):
    fake_db = _FakeDB(segments=[
        {
            "id": "seg-1",
            "scene_id": "scene-1",
            "project_id": "project-1",
            "order": 0,
            "duration": 5,
            "start_second": 0,
        },
    ])
    monkeypatch.setattr(server, "db", fake_db)

    out = _run(server._create_scene_segment(
        "scene-1",
        expand_mode="expand",
        continuity_prompt="continue",
        user={"id": "user-1"},
    ))

    assert out["duration"] == 5
    assert out["start_second"] == 5
    assert out["parent_segment_id"] == "seg-1"
    assert out["video_url"].startswith("http")
    assert fake_db.generations.rows[-1]["type"] == "video_segment"


def test_successful_mocked_luma_video_saves_asset_and_updates_segment(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")
    cfg = server.storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
        "ASSET_PUBLIC_BASE_URL": "https://assets.example.com/assets",
    })
    monkeypatch.setattr(server, "ASSET_STORAGE_CONFIG", cfg)
    fake_db = _FakeDB(scene={
        "id": "scene-1",
        "project_id": "project-1",
        "visual_prompt": "Wide shot",
        "enhanced_video_prompt": "Cinematic motion",
        "image_url": "https://assets.example.com/assets/scene.png",
    })
    monkeypatch.setattr(server, "db", fake_db)

    class _FakeLumaClient:
        def create_generation(self, **kwargs):
            assert kwargs["image_url"] == "https://assets.example.com/assets/scene.png"
            assert kwargs["duration_seconds"] == 5
            return {"id": "luma-job-1", "state": "queued"}

        def get_generation(self, provider_job_id):
            assert provider_job_id == "luma-job-1"
            return {"id": provider_job_id, "state": "completed", "assets": {"video": "https://luma.example/video.mp4"}}

        def download_asset(self, video_url):
            assert video_url == "https://luma.example/video.mp4"
            return b"real-video-bytes"

    LumaVideoProvider.client_factory = lambda _api_key: _FakeLumaClient()

    out = _run(server._create_scene_segment(
        "scene-1",
        expand_mode="initial",
        continuity_prompt=None,
        user={"id": "user-1"},
    ))

    assert out["video_url"].startswith("https://assets.example.com/assets/")
    assert out["provider_name"] == "luma"
    assert out["provider_job_id"] == "luma-job-1"
    assert out["generation_mode"] == "real"
    assert fake_db.segments.rows[-1]["video_url"] == out["video_url"]
    assert fake_db.assets.rows[0]["asset_type"] == "video_segment"
    assert fake_db.assets.rows[0]["provider_name"] == "luma"
    assert fake_db.assets.rows[0]["provider_job_id"] == "luma-job-1"
    assert fake_db.assets.rows[0]["mime_type"] == "video/mp4"
    assert fake_db.assets.rows[0]["size_bytes"] == len(b"real-video-bytes")
    assert (tmp_path / fake_db.assets.rows[0]["storage_key"]).exists()
    assert fake_db.users.rows[0]["credits"] == 250 - server.COSTS["video_segment"]


def test_real_luma_expand_uses_previous_generation_id(monkeypatch, tmp_path):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")
    cfg = server.storage_config({
        "ASSET_STORAGE_BACKEND": "local",
        "ASSET_LOCAL_DIR": str(tmp_path),
        "ASSET_PUBLIC_BASE_URL": "https://assets.example.com/assets",
    })
    monkeypatch.setattr(server, "ASSET_STORAGE_CONFIG", cfg)
    previous = {
        "id": "seg-1",
        "scene_id": "scene-1",
        "project_id": "project-1",
        "order": 0,
        "start_second": 0,
        "duration": 5,
        "provider_job_id": "luma-job-previous",
        "video_url": "https://assets.example.com/assets/previous.mp4",
    }
    fake_db = _FakeDB(
        segments=[previous],
        scene={
            "id": "scene-1",
            "project_id": "project-1",
            "visual_prompt": "Wide shot",
            "enhanced_video_prompt": "Continue the lighthouse shot",
            "image_url": None,
        },
    )
    monkeypatch.setattr(server, "db", fake_db)

    class _FakeLumaClient:
        def create_generation(self, **kwargs):
            assert kwargs["expand_mode"] == "expand"
            assert kwargs["parent_provider_job_id"] == "luma-job-previous"
            assert kwargs["parent_video_url"] == "https://assets.example.com/assets/previous.mp4"
            assert kwargs["image_url"] is None
            return {"id": "luma-job-expanded", "state": "queued"}

        def get_generation(self, provider_job_id):
            assert provider_job_id == "luma-job-expanded"
            return {
                "id": provider_job_id,
                "state": "completed",
                "assets": {"video": "https://luma.example/expanded.mp4"},
            }

        def download_asset(self, video_url):
            assert video_url == "https://luma.example/expanded.mp4"
            return b"expanded-video-bytes"

    LumaVideoProvider.client_factory = lambda _api_key: _FakeLumaClient()

    out = _run(server._create_scene_segment(
        "scene-1",
        expand_mode="expand",
        continuity_prompt="Continue the lighthouse shot",
        user={"id": "user-1"},
    ))

    assert out["parent_segment_id"] == "seg-1"
    assert out["start_second"] == 5
    assert out["expand_mode"] == "expand"
    assert out["provider_job_id"] == "luma-job-expanded"
    assert out["generation_mode"] == "real"
    assert fake_db.segments.rows[-1]["parent_segment_id"] == "seg-1"
    assert fake_db.assets.rows[0]["provider_job_id"] == "luma-job-expanded"


def test_luma_http_client_uses_documented_video_endpoint_and_payload(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        assert request.full_url == "https://api.lumalabs.ai/dream-machine/v1/generations"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert "\n" not in request.headers["Authorization"]
        assert '"' not in request.headers["Authorization"]
        body = request.data.decode("utf-8")
        assert '"model": "ray-2"' in body
        assert '"duration": "5s"' in body
        assert '"keyframes"' not in body
        return _FakeHTTPResponse(b'{"id":"job-1","state":"queued"}')

    monkeypatch.setattr("providers.video_luma.urllib.request.urlopen", fake_urlopen)

    client = _LumaHttpClient('  \n"test-key"\n  ')
    out = client.create_generation(
        model="ray-2",
        prompt="Short safe prompt",
        image_url=None,
        duration_seconds=5,
        expand_mode="initial",
        parent_provider_job_id=None,
        parent_video_url=None,
    )

    assert out["id"] == "job-1"
    assert len(requests) == 1


def test_luma_http_client_image_to_video_payload(monkeypatch):
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://api.lumalabs.ai/dream-machine/v1/generations"
        payload = request.data.decode("utf-8")
        assert '"keyframes": {"frame0": {"type": "image", "url": "https://assets.example/scene.png"}}' in payload
        return _FakeHTTPResponse(b'{"id":"job-1"}')

    monkeypatch.setattr("providers.video_luma.urllib.request.urlopen", fake_urlopen)

    _LumaHttpClient("test-key").create_generation(
        model="ray-2",
        prompt="Short safe prompt",
        image_url="https://assets.example/scene.png",
        duration_seconds=5,
        expand_mode="initial",
        parent_provider_job_id=None,
        parent_video_url=None,
    )


def test_luma_provider_polls_completed_downloads_bytes_and_normalizes_legacy_model(monkeypatch):
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")

    class _FakeLumaClient:
        def __init__(self):
            self.polls = 0

        def create_generation(self, **kwargs):
            assert kwargs["model"] == "ray-2"
            return {"id": "job-1"}

        def get_generation(self, provider_job_id):
            self.polls += 1
            if self.polls == 1:
                return {"id": provider_job_id, "state": "running"}
            return {"id": provider_job_id, "state": "completed", "assets": {"video": "https://luma.example/out.mp4"}}

        def download_asset(self, video_url):
            assert video_url == "https://luma.example/out.mp4"
            return b"mp4"

    LumaVideoProvider.client_factory = lambda _api_key: _FakeLumaClient()

    res = _run(LumaVideoProvider("luma", "ray").run(
        prompt="Short safe prompt",
        duration_seconds=5,
        poll_interval_seconds=0,
    ))

    assert res.status == "success"
    assert res.model_name == "ray-2"
    assert res.provider_job_id == "job-1"
    assert res.output["video_bytes"] == b"mp4"
    assert res.meta["input_mode"] == "text-to-video"


def test_luma_http_4xx_failure_is_sanitized(monkeypatch):
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=_FakeHTTPResponse(b'{"error":"bad model","api_key":"sk-secret"}'),
        )

    monkeypatch.setattr("providers.video_luma.urllib.request.urlopen", fake_urlopen)
    LumaVideoProvider.client_factory = lambda api_key: _LumaHttpClient(api_key)

    res = _run(LumaVideoProvider("luma", "ray-2").run(prompt="Short safe prompt"))

    assert res.status == "failed"
    assert res.meta["provider_http_status"] == 400
    assert res.meta["error_type"] == "provider_http_error"
    assert res.meta["endpoint"] == "create_video"
    assert res.meta["input_mode"] == "text-to-video"
    assert "sk-secret" not in str(res.to_dict())


def test_luma_http_403_failure_has_auth_error_type_and_safe_body(monkeypatch):
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: ' \n"luma-secret"\n ')

    def fake_urlopen(request, timeout):
        assert request.headers["Authorization"] == "Bearer luma-secret"
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=_FakeHTTPResponse(b'{"detail":"Not authenticated","api_key":"luma-secret"}'),
        )

    monkeypatch.setattr("providers.video_luma.urllib.request.urlopen", fake_urlopen)
    LumaVideoProvider.client_factory = lambda api_key: _LumaHttpClient(api_key)

    res = _run(LumaVideoProvider("luma", "").run(prompt="Short safe prompt"))

    assert res.status == "failed"
    assert res.model_name == "ray-2"
    assert res.meta["provider_http_status"] == 403
    assert res.meta["error_type"] == "provider_auth_failed"
    assert res.meta["endpoint"] == "create_video"
    assert res.meta["input_mode"] == "text-to-video"
    assert "Not authenticated" in res.meta["provider_error_message"]
    assert "luma-secret" not in str(res.to_dict())


def test_luma_provider_5xx_failure_metadata_is_sanitized(monkeypatch):
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")

    class _FailingClient:
        def create_generation(self, **kwargs):
            from providers.video_luma import LumaProviderError

            raise LumaProviderError(
                http_status=503,
                endpoint="create_video",
                message='{"error":"temporary","Authorization":"Bearer secret-token"}',
            )

    LumaVideoProvider.client_factory = lambda _api_key: _FailingClient()

    res = _run(LumaVideoProvider("luma", "ray-2").run(prompt="Short safe prompt"))

    assert res.status == "failed"
    assert res.meta["provider_http_status"] == 503
    assert res.meta["endpoint"] == "create_video"
    assert "secret-token" not in str(res.to_dict())


def test_luma_timeout_has_safe_failure_metadata(monkeypatch):
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")

    class _NeverCompletes:
        def create_generation(self, **kwargs):
            return {"id": "job-timeout"}

        def get_generation(self, provider_job_id):
            return {"id": provider_job_id, "state": "running"}

    LumaVideoProvider.client_factory = lambda _api_key: _NeverCompletes()

    res = _run(LumaVideoProvider("luma", "ray-2").run(
        prompt="Short safe prompt",
        timeout_seconds=1,
        poll_interval_seconds=0,
    ))

    assert res.status == "timeout"
    assert res.provider_job_id == "job-timeout"
    assert res.meta["provider_job_id"] == "job-timeout"


def test_luma_unsupported_model_fails_before_client(monkeypatch):
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")

    def fail_factory(_api_key):
        raise AssertionError("client should not be created for unsupported model")

    LumaVideoProvider.client_factory = fail_factory

    res = _run(LumaVideoProvider("luma", "not-a-model").run(prompt="Short safe prompt"))

    assert res.status == "failed"
    assert "Unsupported Luma video model" in res.error


def test_failed_luma_provider_does_not_deduct_and_logs_activity(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: "luma-secret")
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)

    class _FailingLumaClient:
        def create_generation(self, **kwargs):
            raise RuntimeError("provider unavailable")

    LumaVideoProvider.client_factory = lambda _api_key: _FailingLumaClient()
    server.set_activity_recorder(server._record_provider_activity)

    with pytest.raises(server.HTTPException) as exc:
        _run(server._create_scene_segment(
            "scene-1",
            expand_mode="initial",
            continuity_prompt=None,
            user={"id": "user-1"},
        ))

    assert exc.value.status_code == 502
    assert fake_db.users.rows[0]["credits"] == 250
    assert fake_db.segments.rows == []
    assert fake_db.generations.rows[-1]["status"] == "failed"
    assert fake_db.provider_activity.rows[-1]["modality"] == "video"
    assert fake_db.provider_activity.rows[-1]["provider_name"] == "luma"
    assert fake_db.provider_activity.rows[-1]["status"] == "failed"
    assert fake_db.provider_activity.rows[-1]["input_mode"] == "text-to-video"
    assert fake_db.provider_activity.rows[-1]["provider_error_message"] == "provider unavailable"
    assert "luma-secret" not in str(fake_db.provider_activity.rows)


def test_luma_403_does_not_deduct_create_asset_or_expose_key(monkeypatch):
    monkeypatch.setenv("USE_REAL_VIDEO_PROVIDER", "true")
    monkeypatch.setattr(provider_executor, "key_present_for_modality", lambda *_: True)
    monkeypatch.setattr(provider_executor, "key_status_for_modality", lambda *_: "configured")
    monkeypatch.setattr("providers.video_luma.get_provider_secret_value", lambda *_: ' \n"luma-secret"\n ')
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)

    class _AuthFailingLumaClient:
        def create_generation(self, **kwargs):
            from providers.video_luma import LumaProviderError

            raise LumaProviderError(
                http_status=403,
                endpoint="create_video",
                message='{"detail":"Not authenticated","api_key":"luma-secret"}',
            )

    captured_keys = []

    def client_factory(api_key):
        captured_keys.append(api_key)
        return _AuthFailingLumaClient()

    LumaVideoProvider.client_factory = client_factory
    server.set_activity_recorder(server._record_provider_activity)

    with pytest.raises(server.HTTPException) as exc:
        _run(server._create_scene_segment(
            "scene-1",
            expand_mode="initial",
            continuity_prompt=None,
            user={"id": "user-1"},
        ))

    assert exc.value.status_code == 502
    assert captured_keys == ["luma-secret"]
    assert fake_db.users.rows[0]["credits"] == 250
    assert fake_db.users.rows[0]["credits_used"] == 0
    assert fake_db.segments.rows == []
    assert fake_db.assets.rows == []
    assert fake_db.credit_events.rows == []
    assert fake_db.generations.rows[-1]["status"] == "failed"
    activity = fake_db.provider_activity.rows[-1]
    assert activity["modality"] == "video"
    assert activity["provider_name"] == "luma"
    assert activity["mode"] == "real"
    assert activity["status"] == "failed"
    assert activity["provider_http_status"] == 403
    assert activity["error_type"] == "provider_auth_failed"
    assert activity["endpoint"] == "create_video"
    assert activity["input_mode"] == "text-to-video"
    assert "Not authenticated" in activity["provider_error_message"]
    assert "luma-secret" not in str(fake_db.provider_activity.rows)
