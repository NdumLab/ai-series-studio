"""Side-effect-free helpers for guarded Stripe test-mode billing."""
import os


def stripe_test_config(env: dict | None = None) -> dict:
    source = env if env is not None else os.environ
    test_mode = (source.get("STRIPE_TEST_MODE") or "false").strip().lower() == "true"
    secret_key = (source.get("STRIPE_SECRET_KEY") or "").strip()
    price_id = (source.get("STRIPE_CREDIT_PRICE_ID") or "").strip()
    webhook_secret = (source.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    key_is_test = secret_key.startswith("sk_test_")
    enabled = bool(test_mode and secret_key and key_is_test and price_id)
    return {
        "provider": "stripe",
        "mode": "test" if test_mode else "disabled",
        "enabled": enabled,
        "test_mode": test_mode,
        "secret_key_configured": bool(secret_key),
        "secret_key_is_test": key_is_test,
        "price_id_configured": bool(price_id),
        "webhook_secret_configured": bool(webhook_secret),
        "live_payments_enabled": False,
        "message": (
            "Stripe test metering is configured."
            if enabled
            else "Stripe test metering is disabled until test-mode env vars are configured."
        ),
    }
