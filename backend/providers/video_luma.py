"""Real Luma video provider.

The provider is backend-only and is never instantiated unless the executor has
already verified the real-video feature flag, selected provider, and
server-side secret presence. Unit tests inject a fake client through
`client_factory`; production uses a small urllib-based client lazily so
importing this module cannot make network calls.
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


LUMA_VIDEO_PROVIDER_IDS = {"luma"}
DEFAULT_LUMA_MODEL = "ray-2"
LEGACY_LUMA_MODEL_ALIASES = {"ray": DEFAULT_LUMA_MODEL}
SUPPORTED_LUMA_MODELS = {DEFAULT_LUMA_MODEL, "ray-flash-2"}
DEFAULT_LUMA_TIMEOUT_SECONDS = 180
DEFAULT_LUMA_POLL_INTERVAL_SECONDS = 3
LUMA_CREATE_VIDEO_ENDPOINT = "create_video"


class LumaVideoProvider(BaseProvider):
    modality = "video"
    requires_api_key = True
    client_factory: Optional[Callable[[str], Any]] = None

    def __init__(self, provider_name: str, model_name: str) -> None:
        super().__init__(provider_name, _normalize_luma_model(model_name))

    def _client(self, api_key: str) -> Any:
        factory = type(self).client_factory
        if factory is not None:
            return factory(api_key)
        return _LumaHttpClient(api_key)

    async def run(
        self,
        *,
        prompt: str,
        image_url: Optional[str] = None,
        duration_seconds: int = 5,
        expand_mode: str = "initial",
        parent_provider_job_id: Optional[str] = None,
        parent_video_url: Optional[str] = None,
        timeout_seconds: int = DEFAULT_LUMA_TIMEOUT_SECONDS,
        poll_interval_seconds: int = DEFAULT_LUMA_POLL_INTERVAL_SECONDS,
        **_: Any,
    ) -> ProviderResult:
        started = time.perf_counter()
        api_key = _normalize_api_key(get_provider_secret_value("video", self.provider_name))
        if not api_key:
            return self._failed(started, "Luma video provider secret is not configured.")
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            return self._failed(started, "Video prompt is empty.")
        input_mode = "image-to-video" if (image_url or "").strip() else "text-to-video"
        if self.model_name not in SUPPORTED_LUMA_MODELS:
            return self._failed(
                started,
                f"Unsupported Luma video model: {self.model_name}",
                endpoint=LUMA_CREATE_VIDEO_ENDPOINT,
                input_mode=input_mode,
            )
        provider_job_id = None
        try:
            client = self._client(api_key)
            created = client.create_generation(
                model=self.model_name or DEFAULT_LUMA_MODEL,
                prompt=clean_prompt,
                image_url=(image_url or "").strip() or None,
                duration_seconds=max(1, int(duration_seconds or 5)),
                expand_mode=expand_mode,
                parent_provider_job_id=parent_provider_job_id,
                parent_video_url=parent_video_url,
            )
            provider_job_id = _field(created, "id") or _field(created, "generation_id")
            if not provider_job_id:
                raise ValueError("Luma response did not include generation id")
            final = self._poll_until_complete(
                client=client,
                provider_job_id=provider_job_id,
                timeout_seconds=max(1, int(timeout_seconds or DEFAULT_LUMA_TIMEOUT_SECONDS)),
                poll_interval_seconds=max(0, int(poll_interval_seconds or DEFAULT_LUMA_POLL_INTERVAL_SECONDS)),
            )
            video_url = _extract_video_url(final)
            if not video_url:
                raise ValueError("Luma completed generation did not include a video URL")
            video_bytes = client.download_asset(video_url)
            if not isinstance(video_bytes, (bytes, bytearray)) or not video_bytes:
                raise ValueError("Luma video download returned no bytes")
            return ProviderResult(
                modality="video",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_SUCCESS,
                provider_job_id=provider_job_id,
                output={
                    "video_bytes": bytes(video_bytes),
                    "mime_type": "video/mp4",
                    "duration": max(1, int(duration_seconds or 5)),
                },
                message="Real Luma video generated.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "provider_status": _field(final, "state") or _field(final, "status") or "completed",
                    "input_mode": input_mode,
                    "image_to_video": input_mode == "image-to-video",
                    "expand_mode": expand_mode,
                    "endpoint": LUMA_CREATE_VIDEO_ENDPOINT,
                },
            )
        except TimeoutError as exc:
            return ProviderResult(
                modality="video",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status="timeout",
                provider_job_id=provider_job_id,
                error=exc.__class__.__name__,
                message="Real Luma video generation timed out.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "expand_mode": expand_mode,
                    "endpoint": LUMA_CREATE_VIDEO_ENDPOINT,
                    "input_mode": input_mode,
                    "provider_job_id": provider_job_id,
                    "provider_error_message": _sanitize_message(str(exc)),
                },
            )
        except LumaProviderError as exc:
            error_type = "provider_auth_failed" if exc.http_status in {401, 403} else "provider_http_error"
            return ProviderResult(
                modality="video",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                provider_job_id=provider_job_id,
                error=exc.__class__.__name__,
                message="Real Luma video generation failed.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "expand_mode": expand_mode,
                    "endpoint": exc.endpoint or LUMA_CREATE_VIDEO_ENDPOINT,
                    "input_mode": input_mode,
                    "provider_http_status": exc.http_status,
                    "provider_error_message": exc.safe_message,
                    "error_type": error_type,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                modality="video",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                provider_job_id=provider_job_id,
                error=exc.__class__.__name__,
                message="Real Luma video generation failed.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "expand_mode": expand_mode,
                    "endpoint": LUMA_CREATE_VIDEO_ENDPOINT,
                    "input_mode": input_mode,
                    "provider_error_message": _sanitize_message(str(exc)),
                },
            )

    def _failed(
        self,
        started: float,
        error: str,
        *,
        endpoint: Optional[str] = None,
        input_mode: Optional[str] = None,
    ) -> ProviderResult:
        return ProviderResult(
            modality="video",
            provider_name=self.provider_name,
            model_name=self.model_name,
            mode="real",
            status=STATUS_FAILED,
            error=error,
            message="Real Luma video provider failed before request.",
            meta={
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "endpoint": endpoint,
                "input_mode": input_mode,
                "provider_error_message": _sanitize_message(error),
            },
        )

    def _poll_until_complete(
        self,
        *,
        client: Any,
        provider_job_id: str,
        timeout_seconds: int,
        poll_interval_seconds: int,
    ) -> Any:
        deadline = time.monotonic() + timeout_seconds
        while True:
            result = client.get_generation(provider_job_id)
            status = (_field(result, "state") or _field(result, "status") or "").lower()
            if status in {"completed", "complete", "succeeded", "success", "done"}:
                return result
            if status in {"failed", "failure", "error", "cancelled", "canceled"}:
                raise RuntimeError(f"Luma generation ended with status {status}")
            if time.monotonic() >= deadline:
                raise TimeoutError("Luma generation polling timed out")
            time.sleep(poll_interval_seconds)


class _LumaHttpClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = _normalize_api_key(api_key)
        self.base_url = "https://api.lumalabs.ai/dream-machine/v1/generations"

    def create_generation(
        self,
        *,
        model: str,
        prompt: str,
        image_url: Optional[str],
        duration_seconds: int,
        expand_mode: str,
        parent_provider_job_id: Optional[str],
        parent_video_url: Optional[str],
    ) -> dict:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "duration": f"{duration_seconds}s",
        }
        if image_url:
            payload["keyframes"] = {"frame0": {"type": "image", "url": image_url}}
        if parent_provider_job_id:
            payload["extend_generation_id"] = parent_provider_job_id
        elif parent_video_url and expand_mode == "expand":
            payload["source_video_url"] = parent_video_url
        return self._json_request("POST", self.base_url, payload, endpoint=LUMA_CREATE_VIDEO_ENDPOINT)

    def get_generation(self, provider_job_id: str) -> dict:
        return self._json_request("GET", f"{self.base_url}/{provider_job_id}", None, endpoint="get_generation")

    def download_asset(self, video_url: str) -> bytes:
        request = urllib.request.Request(video_url, headers={"User-Agent": "ai-series-studio/1.0"})
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310 - provider asset URL
            return response.read()

    def _json_request(self, method: str, url: str, payload: Optional[dict], *, endpoint: str) -> dict:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ai-series-studio/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - fixed provider URL
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LumaProviderError(
                http_status=exc.code,
                message=body,
                endpoint=endpoint,
            ) from exc
        return json.loads(body or "{}")


class LumaProviderError(RuntimeError):
    def __init__(self, *, http_status: int, message: str, endpoint: str) -> None:
        self.http_status = int(http_status)
        self.endpoint = endpoint
        self.safe_message = _sanitize_message(message)
        super().__init__(f"Luma HTTP {self.http_status}: {self.safe_message}")


def _normalize_luma_model(model_name: Optional[str]) -> str:
    raw = (model_name or DEFAULT_LUMA_MODEL).strip().lower() or DEFAULT_LUMA_MODEL
    return LEGACY_LUMA_MODEL_ALIASES.get(raw, raw)


def _normalize_api_key(api_key: Optional[str]) -> str:
    value = (api_key or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1].strip()
    return value


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_video_url(value: Any) -> Optional[str]:
    direct = _field(value, "video_url")
    if direct:
        return str(direct)
    assets = _field(value, "assets") or {}
    if isinstance(assets, dict):
        for key in ("video", "mp4", "url"):
            if assets.get(key):
                return str(assets[key])
    return None


def _sanitize_message(value: str, limit: int = 240) -> str:
    text = " ".join((value or "").replace("\x00", "").split())
    text = re.sub(r"Bearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [redacted]", text, flags=re.I)
    text = re.sub(r"(api[_-]?key[\"'=:\s]+)[A-Za-z0-9._~+/=-]+", r"\1[redacted]", text, flags=re.I)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-[redacted]", text)
    if len(text) > limit:
        return f"{text[:limit]}..."
    return text
