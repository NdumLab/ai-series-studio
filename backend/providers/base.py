"""Provider base types.

Each modality has a `BaseProvider` interface. Mock implementations subclass
`MockProviderMixin` so the executor can tell them apart from real
implementations cleanly.

`ProviderResult` is the single shape every provider call returns — whether mock
or real, success or failure, blocked-by-flag or completed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

Modality = Literal["llm", "image", "video", "voice", "music", "export"]
MODALITIES: tuple[Modality, ...] = ("llm", "image", "video", "voice", "music", "export")


# Status field values
STATUS_SUCCESS = "success"
STATUS_BLOCKED = "blocked"   # real provider blocked by flag / missing key → mock ran (or nothing ran)
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"   # dry-run (e.g. `POST /providers/test`) — nothing executed


@dataclass
class ProviderResult:
    """Standard outcome of any provider call.

    Fields:
      modality:           which modality (llm / image / ...)
      provider_name:      the *configured* provider id (e.g. "openai", "fal")
      model_name:         the *configured* model id (e.g. "gpt-5.2", "flux-pro")
      mode:               "mock" or "real"
      status:             one of STATUS_*
      estimated_credits:  best-effort credit estimate for this call
      provider_job_id:    placeholder for future async provider jobs (None for mock)
      output:             provider payload (e.g. `{"image_url": "..."}`)
      error:              human-readable error message (None on success)
      message:            human-readable summary line for UI / logs
      meta:               anything extra (resolved source, flag value, key_present, ...)
    """
    modality: Modality
    provider_name: str
    model_name: str
    mode: Literal["mock", "real"] = "mock"
    status: str = STATUS_SUCCESS
    estimated_credits: int = 0
    provider_job_id: Optional[str] = None
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    message: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modality": self.modality,
            "provider_name": self.provider_name,
            "model_name": self.model_name,
            "mode": self.mode,
            "status": self.status,
            "estimated_credits": self.estimated_credits,
            "provider_job_id": self.provider_job_id,
            "output": self.output,
            "error": self.error,
            "message": self.message,
            "meta": self.meta,
        }


class BaseProvider:
    """Abstract base. Each modality has a concrete `BaseXxxProvider` class that
    declares the call signature. Mock + future real implementations subclass
    those modality bases.

    Today we don't subclass per-modality (mock implementations are flat) — but
    the seam exists so Phase 2B can introduce real ones without touching the
    executor.
    """

    modality: Modality = "llm"
    provider_name: str = ""
    model_name: str = ""
    is_mock: bool = False
    # When True, the executor will require a server-side API key before this
    # provider is allowed to run. Mocks set this to False.
    requires_api_key: bool = True

    def __init__(self, provider_name: str, model_name: str) -> None:
        self.provider_name = provider_name
        self.model_name = model_name

    async def run(self, **kwargs: Any) -> ProviderResult:  # pragma: no cover - abstract
        raise NotImplementedError


class MockProviderMixin:
    """Marker mixin so the executor / tests can detect mocks unambiguously."""
    is_mock = True
    requires_api_key = False
