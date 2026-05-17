"""Unit tests for backend-only provider secret resolution."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from secrets_resolver import (  # noqa: E402
    get_provider_secret,
    get_provider_secret_value,
    key_present_for_provider,
    provider_secret_ref,
    secrets_backend,
)


def test_disabled_backend_returns_not_configured():
    env = {"SECRETS_BACKEND": "disabled"}
    res = get_provider_secret("image", "openai-image", env)

    assert res.configured is False
    assert res.backend == "disabled"
    assert res.status == "not_configured"
    assert res.secret_ref == "/ai-series-studio/providers/image/openai/api-key"
    assert get_provider_secret_value("image", "openai-image", env) is None


def test_missing_provider_key_returns_false():
    assert key_present_for_provider("image", "", {"SECRETS_BACKEND": "disabled"}) is False


def test_secret_ref_naming_convention():
    env = {"SSM_PROVIDER_KEY_PREFIX": "/ai-series-studio/providers"}

    assert provider_secret_ref("image", "openai-image", env) == "/ai-series-studio/providers/image/openai/api-key"
    assert provider_secret_ref("image", "gemini-nano-banana", env) == "/ai-series-studio/providers/image/gemini/api-key"
    assert provider_secret_ref("image", "fal", env) == "/ai-series-studio/providers/image/fal/api-key"
    assert provider_secret_ref("video", "luma", env) == "/ai-series-studio/providers/video/luma/api-key"
    assert provider_secret_ref("voice", "elevenlabs", env) == "/ai-series-studio/providers/voice/elevenlabs/api-key"


def test_ssm_backend_handles_missing_boto3_safely(monkeypatch):
    monkeypatch.setitem(sys.modules, "boto3", None)
    env = {
        "SECRETS_BACKEND": "ssm",
        "AWS_REGION": "us-east-1",
        "SSM_PROVIDER_KEY_PREFIX": "/ai-series-studio/providers",
    }

    res = get_provider_secret("image", "openai-image", env)

    assert res.configured is False
    assert res.backend == "ssm"
    assert res.status == "not_configured"
    assert res.error == "AWS SDK unavailable"


def test_ssm_backend_uses_boto3_without_exposing_secret(monkeypatch):
    class FakeSSM:
        def get_parameter(self, Name, WithDecryption):
            assert Name == "/ai-series-studio/providers/image/openai/api-key"
            assert WithDecryption is True
            return {"Parameter": {"Value": "configured-test-value"}}

    fake_boto3 = types.SimpleNamespace(client=lambda service, region_name=None: FakeSSM())
    fake_botocore = types.SimpleNamespace(
        exceptions=types.SimpleNamespace(BotoCoreError=Exception, ClientError=Exception)
    )
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setitem(sys.modules, "botocore", fake_botocore)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", fake_botocore.exceptions)
    env = {
        "SECRETS_BACKEND": "ssm",
        "AWS_REGION": "us-east-1",
        "SSM_PROVIDER_KEY_PREFIX": "/ai-series-studio/providers",
    }

    res = get_provider_secret("image", "openai-image", env)

    assert res.configured is True
    assert res.status == "configured"
    assert res.secret_ref == "/ai-series-studio/providers/image/openai/api-key"
    assert "configured-test-value" not in repr(res)
    assert get_provider_secret_value("image", "openai-image", env) == "configured-test-value"


def test_secrets_backend_default_is_disabled():
    assert secrets_backend({}) == "disabled"
