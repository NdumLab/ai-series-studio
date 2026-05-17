"""Unit tests for disabled-by-default video provider guard foundation."""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_episode_studio_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server  # noqa: E402


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
    def __init__(self, *, segments=None):
        self.users = _FakeCollection([
            {
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
            {"id": "scene-1", "project_id": "project-1", "visual_prompt": "Wide shot"},
        ])
        self.segments = _FakeCollection(segments or [])
        self.provider_settings = _FakeCollection([
            {
                "id": server.SETTINGS_DOC_ID,
                "mock_mode": True,
                **server.DEFAULT_PROVIDER_SETTINGS,
                "video": {"provider": "luma", "model": "ray"},
            }
        ])
        self.credit_events = _FakeCollection()
        self.generations = _FakeCollection()


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
    monkeypatch.setattr(server.random, "random", lambda: 1.0)
    monkeypatch.setattr(server.random, "choice", lambda values: values[0])
    yield
    server.set_activity_recorder(None)


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
