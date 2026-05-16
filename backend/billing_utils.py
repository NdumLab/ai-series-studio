"""Side-effect-free helpers for guarded Stripe test-mode billing."""
import os


def _positive_int(value: str | None, default: int) -> int:
    try:
        parsed = int(value or default)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def stripe_test_config(env: dict | None = None) -> dict:
    source = env if env is not None else os.environ
    test_mode = (source.get("STRIPE_TEST_MODE") or "false").strip().lower() == "true"
    secret_key = (source.get("STRIPE_SECRET_KEY") or "").strip()
    price_id = (source.get("STRIPE_CREDIT_PRICE_ID") or "").strip()
    webhook_secret = (source.get("STRIPE_WEBHOOK_SECRET") or "").strip()
    credits = _positive_int(source.get("STRIPE_CREDIT_PACK_CREDITS"), 500)
    success_url = (source.get("BILLING_SUCCESS_URL") or "http://localhost:3000/billing/success").strip()
    cancel_url = (source.get("BILLING_CANCEL_URL") or "http://localhost:3000/billing/cancel").strip()
    key_is_test = secret_key.startswith("sk_test_")
    missing_config = []
    if not test_mode:
        missing_config.append("STRIPE_TEST_MODE")
    if not secret_key:
        missing_config.append("STRIPE_SECRET_KEY")
    elif not key_is_test:
        missing_config.append("STRIPE_SECRET_KEY_TEST_MODE")
    if not price_id:
        missing_config.append("STRIPE_CREDIT_PRICE_ID")
    checkout_enabled = not missing_config
    return {
        "provider": "stripe",
        "mode": "test" if test_mode else "disabled",
        "enabled": checkout_enabled,
        "checkout_enabled": checkout_enabled,
        "stripe_test_mode": test_mode,
        "test_mode": test_mode,
        "secret_key_configured": bool(secret_key),
        "secret_key_is_test": key_is_test,
        "price_id_configured": bool(price_id),
        "configured_price_id_present": bool(price_id),
        "webhook_secret_configured": bool(webhook_secret),
        "webhook_configured": bool(webhook_secret),
        "missing_config": missing_config,
        "credit_pack_credits": credits,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "live_payments_enabled": False,
        "message": (
            "Stripe test checkout is configured."
            if checkout_enabled
            else "Stripe test checkout is not configured."
        ),
    }
