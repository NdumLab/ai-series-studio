"""Mock provider implementations.

These are thin wrappers — the actual mock generation logic lives in
`server.py` (mock_rewrite_story, MOCK_SCENE_IMAGES, MOCK_VIDEO_URLS, ...).
We don't move it here because the existing endpoints have specific
fail-rate / chaining behavior that the spec requires kept identical.

Instead, these classes give the executor / dry-run endpoint a uniform
interface that *describes* what a mock call would produce. Real generation
endpoints continue to call the existing server helpers directly today — and
will switch to `execute_provider(...)` in Phase 2B.
"""
from __future__ import annotations
from typing import Any

from .base import (
    BaseProvider,
    MockProviderMixin,
    ProviderResult,
    STATUS_SUCCESS,
)


class _MockBase(MockProviderMixin, BaseProvider):
    """Shared mock builder. Subclasses set `modality`, `_action`, `_credits`."""

    _action: str = "mock call"
    _credits: int = 0

    async def run(self, **kwargs: Any) -> ProviderResult:
        return ProviderResult(
            modality=self.modality,
            provider_name=self.provider_name,
            model_name=self.model_name,
            mode="mock",
            status=STATUS_SUCCESS,
            estimated_credits=self._credits,
            provider_job_id=None,
            output={},
            message=f"Mock {self._action} simulated — no real network call.",
        )


class MockLLMProvider(_MockBase):
    modality = "llm"
    _action = "LLM rewrite"


class MockImageProvider(_MockBase):
    modality = "image"
    _action = "image generation"


class MockVideoProvider(_MockBase):
    modality = "video"
    _action = "video segment generation"


class MockVoiceProvider(_MockBase):
    modality = "voice"
    _action = "voice synthesis"


class MockMusicProvider(_MockBase):
    modality = "music"
    _action = "music generation"


class MockExportProvider(_MockBase):
    modality = "export"
    _action = "final stitch / export"


MOCK_PROVIDER_BY_MODALITY = {
    "llm": MockLLMProvider,
    "image": MockImageProvider,
    "video": MockVideoProvider,
    "voice": MockVoiceProvider,
    "music": MockMusicProvider,
    "export": MockExportProvider,
}
