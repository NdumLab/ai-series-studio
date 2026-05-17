"""Real OpenAI image provider.

The provider is backend-only and is never instantiated unless the executor has
already verified the real-image feature flag and server-side secret presence.
Unit tests inject a fake client through `client_factory`; production uses the
official OpenAI SDK lazily so importing this module cannot make network calls.
"""
from __future__ import annotations

import base64
import time
from typing import Any, Callable, Optional

from secrets_resolver import get_provider_secret_value

from .base import BaseProvider, ProviderResult, STATUS_FAILED, STATUS_SUCCESS


OPENAI_IMAGE_PROVIDER_IDS = {"openai", "openai-image"}
DEFAULT_OPENAI_IMAGE_MODEL = "gpt-image-1"


class OpenAIImageProvider(BaseProvider):
    modality = "image"
    requires_api_key = True
    client_factory: Optional[Callable[[str], Any]] = None

    def __init__(self, provider_name: str, model_name: str) -> None:
        super().__init__(provider_name, model_name or DEFAULT_OPENAI_IMAGE_MODEL)

    def _client(self, api_key: str) -> Any:
        factory = type(self).client_factory
        if factory is not None:
            return factory(api_key)
        from openai import OpenAI  # type: ignore

        return OpenAI(api_key=api_key, timeout=60)

    async def run(
        self,
        *,
        prompt: str,
        image_kind: str = "scene",
        size: str = "1024x1024",
        quality: str = "low",
        **_: Any,
    ) -> ProviderResult:
        started = time.perf_counter()
        api_key = get_provider_secret_value("image", self.provider_name)
        if not api_key:
            return ProviderResult(
                modality="image",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error="OpenAI image provider secret is not configured.",
                message="Real image provider failed before request.",
                meta={"duration_ms": int((time.perf_counter() - started) * 1000), "image_kind": image_kind},
            )
        clean_prompt = (prompt or "").strip()
        if not clean_prompt:
            return ProviderResult(
                modality="image",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error="Image prompt is empty.",
                message="Real image provider failed before request.",
                meta={"duration_ms": int((time.perf_counter() - started) * 1000), "image_kind": image_kind},
            )
        try:
            response = self._generate_sync(api_key, clean_prompt, size, quality)
            item = (getattr(response, "data", None) or [None])[0]
            if isinstance(item, dict):
                b64 = item.get("b64_json")
                item_id = item.get("id")
            else:
                b64 = getattr(item, "b64_json", None)
                item_id = getattr(item, "id", None)
            if not b64:
                raise ValueError("OpenAI image response did not include b64_json")
            image_bytes = base64.b64decode(b64)
            provider_job_id = (
                getattr(response, "id", None)
                or item_id
            )
            return ProviderResult(
                modality="image",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_SUCCESS,
                provider_job_id=provider_job_id,
                output={
                    "image_bytes": image_bytes,
                    "mime_type": "image/png",
                    "image_kind": image_kind,
                },
                message="Real OpenAI image generated.",
                meta={
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "image_kind": image_kind,
                    "size": size,
                    "quality": quality,
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                modality="image",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                error=exc.__class__.__name__,
                message="Real OpenAI image generation failed.",
                meta={"duration_ms": int((time.perf_counter() - started) * 1000), "image_kind": image_kind},
            )

    def _generate_sync(self, api_key: str, prompt: str, size: str, quality: str) -> Any:
        client = self._client(api_key)
        return client.images.generate(
            model=self.model_name or DEFAULT_OPENAI_IMAGE_MODEL,
            prompt=prompt,
            n=1,
            size=size,
            quality=quality,
        )
