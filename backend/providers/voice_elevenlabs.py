"""Real ElevenLabs voice provider.

The provider is backend-only and is only reachable through the executor when
the real voice feature flag, selected provider, and server-side secret guards
all pass. Unit tests inject a fake client; production uses urllib lazily.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from secrets_resolver import get_provider_secret_value

from .base import BaseProvider, ProviderResult, STATUS_FAILED, STATUS_SUCCESS


ELEVENLABS_VOICE_PROVIDER_IDS = {"elevenlabs"}
DEFAULT_ELEVENLABS_MODEL = "eleven_v3"
LEGACY_ELEVENLABS_MODEL_ALIASES = {
    "eleven-v3": DEFAULT_ELEVENLABS_MODEL,
    "eleven-turbo": "eleven_turbo_v2_5",
}
SUPPORTED_ELEVENLABS_MODELS = {
    DEFAULT_ELEVENLABS_MODEL,
    "eleven_turbo_v2_5",
    "eleven_multilingual_v2",
}
ELEVENLABS_TTS_ENDPOINT = "text_to_speech"


class ElevenLabsVoiceProvider(BaseProvider):
    modality = "voice"
    requires_api_key = True
    client_factory: Optional[Callable[[str], Any]] = None

    def __init__(self, provider_name: str, model_name: str) -> None:
        super().__init__(provider_name, _normalize_elevenlabs_model(model_name))

    def _client(self, api_key: str) -> Any:
        factory = type(self).client_factory
        if factory is not None:
            return factory(api_key)
        return _ElevenLabsHttpClient(api_key)

    async def run(
        self,
        *,
        text: str,
        voice_id: Optional[str] = None,
        **_: Any,
    ) -> ProviderResult:
        started = time.perf_counter()
        api_key = _normalize_api_key(get_provider_secret_value("voice", self.provider_name))
        if not api_key:
            return self._failed(started, "ElevenLabs voice provider secret is not configured.")
        clean_text = (text or "").strip()
        if not clean_text:
            return self._failed(started, "Voice text is empty.", endpoint=ELEVENLABS_TTS_ENDPOINT)
        clean_voice_id = (voice_id or "").strip()
        if not clean_voice_id:
            return self._failed(
                started,
                "ElevenLabs voice id is not configured.",
                endpoint=ELEVENLABS_TTS_ENDPOINT,
            )
        if self.model_name not in SUPPORTED_ELEVENLABS_MODELS:
            return self._failed(
                started,
                f"Unsupported ElevenLabs voice model: {self.model_name}",
                endpoint=ELEVENLABS_TTS_ENDPOINT,
            )
        try:
            client = self._client(api_key)
            audio_bytes = client.text_to_speech(
                voice_id=clean_voice_id,
                model_id=self.model_name or DEFAULT_ELEVENLABS_MODEL,
                text=clean_text,
            )
            if not isinstance(audio_bytes, (bytes, bytearray)) or not audio_bytes:
                raise ValueError("ElevenLabs voice synthesis returned no bytes")
            return ProviderResult(
                modality="voice",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_SUCCESS,
                provider_job_id=None,
                output={
                    "audio_bytes": bytes(audio_bytes),
                    "mime_type": "audio/mpeg",
                },
                message="Real ElevenLabs voice generated.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "endpoint": ELEVENLABS_TTS_ENDPOINT,
                    "voice_id": clean_voice_id,
                    "text_chars": len(clean_text),
                },
            )
        except ElevenLabsProviderError as exc:
            error_type = "provider_auth_failed" if exc.http_status in {401, 403} else "provider_http_error"
            return ProviderResult(
                modality="voice",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error=exc.__class__.__name__,
                message="Real ElevenLabs voice generation failed.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "endpoint": exc.endpoint or ELEVENLABS_TTS_ENDPOINT,
                    "provider_http_status": exc.http_status,
                    "provider_error_message": exc.safe_message,
                    "error_type": error_type,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                modality="voice",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error=exc.__class__.__name__,
                message="Real ElevenLabs voice generation failed.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "endpoint": ELEVENLABS_TTS_ENDPOINT,
                    "provider_error_message": _sanitize_message(str(exc)),
                },
            )

    def _failed(
        self,
        started: float,
        error: str,
        *,
        endpoint: Optional[str] = None,
    ) -> ProviderResult:
        return ProviderResult(
            modality="voice",
            provider_name=self.provider_name,
            model_name=self.model_name,
            mode="real",
            status=STATUS_FAILED,
            error=error,
            message="Real ElevenLabs voice provider failed before request.",
            meta={
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "endpoint": endpoint,
                "provider_error_message": _sanitize_message(error),
            },
        )


class _ElevenLabsHttpClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = _normalize_api_key(api_key)
        self.base_url = "https://api.elevenlabs.io/v1/text-to-speech"

    def text_to_speech(self, *, voice_id: str, model_id: str, text: str) -> bytes:
        safe_voice_id = urllib.parse.quote(voice_id, safe="")
        payload: dict[str, Any] = {
            "text": text,
            "model_id": model_id,
        }
        request = urllib.request.Request(
            f"{self.base_url}/{safe_voice_id}",
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
                "User-Agent": "ai-series-studio/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:  # noqa: S310 - fixed provider URL
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ElevenLabsProviderError(
                http_status=exc.code,
                message=body,
                endpoint=ELEVENLABS_TTS_ENDPOINT,
            ) from exc


class ElevenLabsProviderError(RuntimeError):
    def __init__(self, *, http_status: int, message: str, endpoint: str) -> None:
        self.http_status = int(http_status)
        self.endpoint = endpoint
        self.safe_message = _sanitize_message(message)
        super().__init__(f"ElevenLabs HTTP {self.http_status}: {self.safe_message}")


def _normalize_elevenlabs_model(model_name: Optional[str]) -> str:
    raw = (model_name or DEFAULT_ELEVENLABS_MODEL).strip().lower() or DEFAULT_ELEVENLABS_MODEL
    return LEGACY_ELEVENLABS_MODEL_ALIASES.get(raw, raw)


def _normalize_api_key(api_key: Optional[str]) -> str:
    value = (api_key or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def _sanitize_message(value: str, limit: int = 240) -> str:
    text = " ".join((value or "").replace("\x00", "").split())
    text = re.sub(r"(xi-api-key[\"'=:\s]+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", text, flags=re.I)
    text = re.sub(r"(api[_-]?key[\"'=:\s]+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", text, flags=re.I)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-[redacted]", text)
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text
