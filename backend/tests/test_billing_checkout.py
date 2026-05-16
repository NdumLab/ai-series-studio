"""Unit tests for Stripe test-mode checkout and webhook fulfillment."""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")
os.environ.setdefault("DB_NAME", "ai_episode_studio_test")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import server  # noqa: E402

server.set_activity_recorder(None)


class _UpdateResult:
    def __init__(self, matched_count=0, upserted_id=None):
        self.matched_count = matched_count
        self.upserted_id = upserted_id


class _FakeCollection:
    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def _matches(self, row, query):
        return all(row.get(k) == v for k, v in query.items())

    async def find_one(self, query, projection=None):
        return next((row for row in self.rows if self._matches(row, query)), None)

    async def insert_one(self, doc):
        self.rows.append(dict(doc))
        return SimpleNamespace(inserted_id=doc.get("id"))

    async def update_one(self, query, update, upsert=False):
        row = await self.find_one(query)
        if row is None:
            if not upsert:
                return _UpdateResult()
            row = dict(query)
            row.update(update.get("$setOnInsert", {}))
            self.rows.append(row)
            return _UpdateResult(upserted_id=row.get("id") or "upserted")
        if "$inc" in update:
            for key, value in update["$inc"].items():
                row[key] = int(row.get(key) or 0) + int(value)
        if "$set" in update:
            row.update(update["$set"])
        return _UpdateResult(matched_count=1)


class _FakeDB:
    def __init__(self):
        self.users = _FakeCollection([
            {
                "id": "user-1",
                "email": "user@example.com",
                "credits": 250,
                "credits_reserved": 0,
                "credits_used": 0,
            }
        ])
        self.billing_events = _FakeCollection()
        self.credit_events = _FakeCollection()


class _FakeStripeSession:
    created_payload = None

    @classmethod
    def create(cls, **kwargs):
        cls.created_payload = kwargs
        return SimpleNamespace(id="cs_test_123", url="https://checkout.stripe.test/session")


class _FakeWebhook:
    event = None
    should_fail = False

    @classmethod
    def construct_event(cls, payload, signature, secret):
        if cls.should_fail:
            raise ValueError("bad signature")
        return cls.event


class _FakeStripe:
    api_key = None
    checkout = SimpleNamespace(Session=_FakeStripeSession)
    Webhook = _FakeWebhook


def _run(coro):
    return asyncio.run(coro)


def _clear_stripe_env(monkeypatch):
    for key in [
        "STRIPE_TEST_MODE",
        "STRIPE_SECRET_KEY",
        "STRIPE_CREDIT_PRICE_ID",
        "STRIPE_WEBHOOK_SECRET",
        "STRIPE_CREDIT_PACK_CREDITS",
        "BILLING_SUCCESS_URL",
        "BILLING_CANCEL_URL",
    ]:
        monkeypatch.delenv(key, raising=False)


def _set_checkout_env(monkeypatch):
    monkeypatch.setenv("STRIPE_TEST_MODE", "true")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_unit")
    monkeypatch.setenv("STRIPE_CREDIT_PRICE_ID", "price_test_credits")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_unit")
    monkeypatch.setenv("STRIPE_CREDIT_PACK_CREDITS", "500")
    monkeypatch.setenv("BILLING_SUCCESS_URL", "http://localhost:3000/billing/success")
    monkeypatch.setenv("BILLING_CANCEL_URL", "http://localhost:3000/billing/cancel")


def test_checkout_blocked_when_test_mode_false(monkeypatch):
    _clear_stripe_env(monkeypatch)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_unit")
    monkeypatch.setenv("STRIPE_CREDIT_PRICE_ID", "price_test_credits")

    with pytest.raises(server.HTTPException) as exc:
        server._billing_checkout_config()

    assert exc.value.status_code == 400
    assert "STRIPE_TEST_MODE" in exc.value.detail["missing_config"]


def test_checkout_blocked_when_config_missing(monkeypatch):
    _clear_stripe_env(monkeypatch)
    monkeypatch.setenv("STRIPE_TEST_MODE", "true")

    with pytest.raises(server.HTTPException) as exc:
        server._billing_checkout_config()

    assert exc.value.status_code == 400
    assert "STRIPE_SECRET_KEY" in exc.value.detail["missing_config"]
    assert "STRIPE_CREDIT_PRICE_ID" in exc.value.detail["missing_config"]


def test_checkout_requires_auth_when_auth_enabled(monkeypatch):
    monkeypatch.setattr(server, "db", _FakeDB())
    monkeypatch.setattr(server, "AUTH_ENABLED", True)
    monkeypatch.setattr(server, "AUTH_DEMO_MODE", False)

    with pytest.raises(server.HTTPException) as exc:
        _run(server.current_user(None))

    assert exc.value.status_code == 401


def test_checkout_creates_session_with_test_metadata(monkeypatch):
    _set_checkout_env(monkeypatch)
    monkeypatch.setattr(server, "_load_stripe", lambda: _FakeStripe)
    _FakeStripeSession.created_payload = None

    result = _run(server.create_checkout_session({"id": "user-1"}))

    assert result["checkout_url"] == "https://checkout.stripe.test/session"
    assert result["session_id"] == "cs_test_123"
    payload = _FakeStripeSession.created_payload
    assert payload["mode"] == "payment"
    assert payload["line_items"] == [{"price": "price_test_credits", "quantity": 1}]
    assert payload["metadata"] == {
        "user_id": "user-1",
        "credits": "500",
        "environment": "test",
    }
    assert _FakeStripe.api_key == "sk_test_unit"


def test_webhook_rejects_invalid_signature(monkeypatch):
    _set_checkout_env(monkeypatch)
    monkeypatch.setattr(server, "_load_stripe", lambda: _FakeStripe)
    _FakeWebhook.should_fail = True

    with pytest.raises(server.HTTPException) as exc:
        _run(server._handle_stripe_webhook(b"{}", "bad"))

    assert exc.value.status_code == 400
    assert "signature" in exc.value.detail.lower()
    _FakeWebhook.should_fail = False


def test_webhook_credits_user_records_events_and_is_idempotent(monkeypatch):
    _set_checkout_env(monkeypatch)
    fake_db = _FakeDB()
    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "_load_stripe", lambda: _FakeStripe)
    _FakeWebhook.should_fail = False
    _FakeWebhook.event = {
        "id": "evt_test_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "client_reference_id": "user-1",
                "metadata": {
                    "user_id": "user-1",
                    "credits": "500",
                    "environment": "test",
                },
            }
        },
    }

    first = _run(server._handle_stripe_webhook(b"{}", "sig"))
    second = _run(server._handle_stripe_webhook(b"{}", "sig"))
    _FakeWebhook.event = {
        **_FakeWebhook.event,
        "id": "evt_test_2",
    }
    third = _run(server._handle_stripe_webhook(b"{}", "sig"))

    user = fake_db.users.rows[0]
    assert first["status"] == "processed"
    assert second["duplicate"] is True
    assert third["duplicate"] is True
    assert user["credits"] == 750
    assert len(fake_db.credit_events.rows) == 1
    assert fake_db.credit_events.rows[0]["credits_delta"] == 500
    assert fake_db.credit_events.rows[0]["operation"] == "stripe_checkout"
    processed = [e for e in fake_db.billing_events.rows if e.get("status") == "processed"]
    assert len(processed) == 1
