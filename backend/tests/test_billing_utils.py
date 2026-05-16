"""Unit tests for guarded Stripe test-mode billing configuration."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from billing_utils import stripe_test_config  # noqa: E402


def test_stripe_disabled_by_default():
    cfg = stripe_test_config({})

    assert cfg["enabled"] is False
    assert cfg["mode"] == "disabled"
    assert cfg["live_payments_enabled"] is False


def test_stripe_requires_test_mode_key_and_price():
    cfg = stripe_test_config({
        "STRIPE_TEST_MODE": "true",
        "STRIPE_SECRET_KEY": "sk_live_not_allowed",
        "STRIPE_CREDIT_PRICE_ID": "price_123",
    })

    assert cfg["enabled"] is False
    assert cfg["secret_key_is_test"] is False
    assert cfg["live_payments_enabled"] is False


def test_stripe_test_mode_configured():
    cfg = stripe_test_config({
        "STRIPE_TEST_MODE": "true",
        "STRIPE_SECRET_KEY": "sk_test_123",
        "STRIPE_CREDIT_PRICE_ID": "price_123",
        "STRIPE_WEBHOOK_SECRET": "whsec_123",
    })

    assert cfg["enabled"] is True
    assert cfg["mode"] == "test"
    assert cfg["secret_key_configured"] is True
    assert cfg["price_id_configured"] is True
    assert cfg["webhook_secret_configured"] is True
    assert cfg["live_payments_enabled"] is False
