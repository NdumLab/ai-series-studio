"""Security-focused tests for MVP auth dependency behavior."""
import asyncio
import os
import sys

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_episode_studio_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server  # noqa: E402

# Importing the FastAPI app registers a Mongo-backed provider activity recorder.
# These unit tests do not need it, and provider-layer unit tests in the same
# process must remain storage-free.
server.set_activity_recorder(None)


class _FakeUsers:
    def __init__(self):
        self.rows = {
            "user-demo": {
                "id": "user-demo",
                "email": "demo@episode.studio",
                "name": "Demo",
                "role": "creator",
                "credits": 250,
                "credits_reserved": 0,
                "credits_used": 0,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            "admin-1": {
                "id": "admin-1",
                "email": "admin@example.com",
                "name": "Admin",
                "role": "admin",
                "credits": 250,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
        }

    async def find_one(self, query, projection=None):
        if "id" in query:
            return self.rows.get(query["id"])
        if "email" in query:
            return next((u for u in self.rows.values() if u.get("email") == query["email"]), None)
        return None

    async def insert_one(self, doc):
        self.rows[doc["id"]] = doc

    async def update_one(self, query, update):
        row = await self.find_one(query)
        if row:
            row.update(update.get("$set", {}))


class _FakeDB:
    def __init__(self):
        self.users = _FakeUsers()


def _run(coro):
    return asyncio.run(coro)


def test_missing_token_rejected_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(server, "db", _FakeDB())
    monkeypatch.setattr(server, "AUTH_ENABLED", True)
    monkeypatch.setattr(server, "AUTH_DEMO_MODE", False)

    with pytest.raises(server.HTTPException) as exc:
        _run(server.current_user(None))

    assert exc.value.status_code == 401
    assert "Authentication required" in exc.value.detail


def test_invalid_token_rejected(monkeypatch):
    monkeypatch.setattr(server, "db", _FakeDB())
    monkeypatch.setattr(server, "AUTH_ENABLED", True)
    monkeypatch.setattr(server, "AUTH_DEMO_MODE", False)

    with pytest.raises(server.HTTPException) as exc:
        _run(server.current_user("Bearer not-a-jwt"))

    assert exc.value.status_code == 401
    assert "Invalid or expired session" in exc.value.detail


def test_demo_user_allowed_when_auth_disabled(monkeypatch):
    monkeypatch.setattr(server, "db", _FakeDB())
    monkeypatch.setattr(server, "AUTH_ENABLED", False)
    monkeypatch.setattr(server, "AUTH_DEMO_MODE", True)

    user = _run(server.current_user(None))

    assert user["id"] == "user-demo"


def test_non_admin_rejected_when_auth_enabled(monkeypatch):
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "AUTH_ENABLED", True)
    monkeypatch.setattr(server, "AUTH_DEMO_MODE", False)
    monkeypatch.setattr(server, "JWT_SECRET_KEY", "test-secret")

    token = server.create_access_token("user-demo", "test-secret")

    with pytest.raises(server.HTTPException) as exc:
        _run(server.current_admin_user(f"Bearer {token}"))

    assert exc.value.status_code == 403


def test_admin_allowed_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(server, "db", _FakeDB())
    monkeypatch.setattr(server, "AUTH_ENABLED", True)
    monkeypatch.setattr(server, "AUTH_DEMO_MODE", False)
    monkeypatch.setattr(server, "JWT_SECRET_KEY", "test-secret")

    token = server.create_access_token("admin-1", "test-secret")
    user = _run(server.current_admin_user(f"Bearer {token}"))

    assert user["id"] == "admin-1"
