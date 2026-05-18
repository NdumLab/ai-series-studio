"""Real ElevenLabs music and sound-effects provider.

The provider is backend-only and only reachable through the executor when the
real music feature flag, selected provider, and server-side secret guards pass.
Unit tests inject a fake client; production uses urllib lazily.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Optional

from secrets_resolver import get_provider_secret_value

from .base import BaseProvider, ProviderResult, STATUS_FAILED, STATUS_SUCCESS


ELEVENLABS_MUSIC_PROVIDER_IDS = {"elevenlabs-music"}
DEFAULT_ELEVENLABS_MUSIC_MODEL = "music_v1"
DEFAULT_ELEVENLABS_SOUND_MODEL = "eleven_text_to_sound_v2"
ELEVENLABS_MUSIC_MODEL_ALIASES = {
    "music-v1": DEFAULT_ELEVENLABS_MUSIC_MODEL,
    "music_v1": DEFAULT_ELEVENLABS_MUSIC_MODEL,
    "sound-effects": DEFAULT_ELEVENLABS_SOUND_MODEL,
    "eleven-text-to-sound-v2": DEFAULT_ELEVENLABS_SOUND_MODEL,
}
SUPPORTED_ELEVENLABS_MUSIC_MODELS = {
    DEFAULT_ELEVENLABS_MUSIC_MODEL,
    DEFAULT_ELEVENLABS_SOUND_MODEL,
}
ELEVENLABS_MUSIC_ENDPOINT = "music"
ELEVENLABS_SOUND_ENDPOINT = "sound-generation"


class ElevenLabsMusicProvider(BaseProvider):
    modality = "music"
    requires_api_key = True
    client_factory: Optional[Callable[[str], Any]] = None

    def __init__(self, provider_name: str, model_name: str) -> None:
        super().__init__(provider_name, _normalize_elevenlabs_music_model(model_name))

    def _client(self, api_key: str) -> Any:
        factory = type(self).client_factory
        if factory is not None:
            return factory(api_key)
        return _ElevenLabsMusicHttpClient(api_key)

    async def run(
        self,
        *,
        prompt: str,
        duration_seconds: Optional[float] = None,
        audio_kind: str = "music",
        **_: Any,
    ) -> ProviderResult:
        started = time.perf_counter()
        api_key = _normalize_api_key(get_provider_secret_value("music", self.provider_name))
        if not api_key:
            return self._failed(started, "ElevenLabs music provider secret is not configured.")
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            return self._failed(started, "Music prompt is empty.", endpoint=ELEVENLABS_MUSIC_ENDPOINT)
        if self.model_name not in SUPPORTED_ELEVENLABS_MUSIC_MODELS:
            return self._failed(
                started,
                f"Unsupported ElevenLabs music model: {self.model_name}",
                endpoint=ELEVENLABS_MUSIC_ENDPOINT,
            )
        clean_kind = "sfx" if (audio_kind or "").strip().lower() in {"sfx", "sound", "sound_effect"} else "music"
        try:
            client = self._client(api_key)
            if clean_kind == "sfx":
                audio_bytes, provider_job_id = client.sound_effect(
                    text=clean_prompt,
                    model_id=DEFAULT_ELEVENLABS_SOUND_MODEL,
                    duration_seconds=duration_seconds,
                )
                endpoint = ELEVENLABS_SOUND_ENDPOINT
            else:
                audio_bytes, provider_job_id = client.compose_music(
                    prompt=clean_prompt,
                    model_id=self.model_name or DEFAULT_ELEVENLABS_MUSIC_MODEL,
                    duration_seconds=duration_seconds,
                )
                endpoint = ELEVENLABS_MUSIC_ENDPOINT
            if not isinstance(audio_bytes, (bytes, bytearray)) or not audio_bytes:
                raise ValueError("ElevenLabs music generation returned no bytes")
            return ProviderResult(
                modality="music",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_SUCCESS,
                provider_job_id=provider_job_id,
                output={
                    "audio_bytes": bytes(audio_bytes),
                    "mime_type": "audio/mpeg",
                    "audio_kind": clean_kind,
                },
                message="Real ElevenLabs music generated.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "endpoint": endpoint,
                    "input_mode": clean_kind,
                    "prompt_chars": len(clean_prompt),
                },
            )
        except ElevenLabsMusicProviderError as exc:
            error_type = "provider_auth_failed" if exc.http_status in {401, 403} else "provider_http_error"
            return ProviderResult(
                modality="music",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error=exc.__class__.__name__,
                message="Real ElevenLabs music generation failed.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "endpoint": exc.endpoint or ELEVENLABS_MUSIC_ENDPOINT,
                    "provider_http_status": exc.http_status,
                    "provider_error_message": exc.safe_message,
                    "error_type": error_type,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                modality="music",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error=exc.__class__.__name__,
                message="Real ElevenLabs music generation failed.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "endpoint": ELEVENLABS_MUSIC_ENDPOINT,
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
            modality="music",
            provider_name=self.provider_name,
            model_name=self.model_name,
            mode="real",
            status=STATUS_FAILED,
            error=error,
            message="Real ElevenLabs music provider failed before request.",
            meta={
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "endpoint": endpoint,
                "provider_error_message": _sanitize_message(error),
            },
        )


class _ElevenLabsMusicHttpClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = _normalize_api_key(api_key)
        self.base_url = "https://api.elevenlabs.io/v1"

    def compose_music(
        self,
        *,
        prompt: str,
        model_id: str,
        duration_seconds: Optional[float],
    ) -> tuple[bytes, Optional[str]]:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "model_id": model_id,
            "force_instrumental": True,
        }
        if duration_seconds is not None:
            payload["music_length_ms"] = int(max(3.0, float(duration_seconds)) * 1000)
        return self._post_audio(f"{self.base_url}/music", payload, ELEVENLABS_MUSIC_ENDPOINT)

    def sound_effect(
        self,
        *,
        text: str,
        model_id: str,
        duration_seconds: Optional[float],
    ) -> tuple[bytes, Optional[str]]:
        payload: dict[str, Any] = {
            "text": text,
            "model_id": model_id,
            "loop": False,
        }
        if duration_seconds is not None:
            payload["duration_seconds"] = max(0.5, min(30.0, float(duration_seconds)))
        return self._post_audio(
            f"{self.base_url}/sound-generation",
            payload,
            ELEVENLABS_SOUND_ENDPOINT,
        )

    def _post_audio(self, url: str, payload: dict[str, Any], endpoint: str) -> tuple[bytes, Optional[str]]:
        request = urllib.request.Request(
            url,
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
            with urllib.request.urlopen(request, timeout=180) as response:  # noqa: S310 - fixed provider URL
                return response.read(), response.headers.get("song-id")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ElevenLabsMusicProviderError(
                http_status=exc.code,
                message=body,
                endpoint=endpoint,
            ) from exc


class ElevenLabsMusicProviderError(RuntimeError):
    def __init__(self, *, http_status: int, message: str, endpoint: str) -> None:
        self.http_status = int(http_status)
        self.endpoint = endpoint
        self.safe_message = _sanitize_message(message)
        super().__init__(f"ElevenLabs HTTP {self.http_status}: {self.safe_message}")


def _normalize_elevenlabs_music_model(model_name: Optional[str]) -> str:
    raw = (model_name or DEFAULT_ELEVENLABS_MUSIC_MODEL).strip().lower() or DEFAULT_ELEVENLABS_MUSIC_MODEL
    return ELEVENLABS_MUSIC_MODEL_ALIASES.get(raw, raw)


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
