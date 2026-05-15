"""Real LLM provider — Phase 2B, LLM modality only.

Uses the Emergent universal LLM key (`emergentintegrations.llm.chat.LlmChat`)
for short, text-only completions. Falls back to the deterministic mock on any
error so the workflow never breaks for the user.

This module is the ONLY place where real network calls leave the application.
Image / Video / Voice / Music / Export remain mock-only — guarded by their
own feature flags + `keys.key_present()` returning False for them.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from typing import Optional

from .base import BaseProvider, ProviderResult, STATUS_SUCCESS, STATUS_FAILED

log = logging.getLogger("episode-studio.llm")

# Heuristic timeout for short creative completions (story rewrite, prompt
# enhancements). Longer than the typical mock-mode latency but short enough
# that the UI still feels responsive if the upstream provider is degraded.
DEFAULT_TIMEOUT_S = 25.0


def _emergent_key() -> Optional[str]:
    key = (os.environ.get("EMERGENT_LLM_KEY") or "").strip()
    return key or None


def real_llm_available() -> bool:
    """True only when the universal key is set AND the integrations library is
    importable. Read by `keys.key_present` for the LLM modality."""
    if not _emergent_key():
        return False
    try:
        # Lazy import — never fail module load if the library isn't there.
        from emergentintegrations.llm.chat import LlmChat  # noqa: F401
        return True
    except Exception:  # pragma: no cover - defensive
        return False


class RealLLMProvider(BaseProvider):
    """Real LLM provider used for short, text-only creative work.

    Inputs are short user prompts assembled by the caller (story rewrite,
    improvement, prompt enhancement). Outputs are plain strings.
    """

    modality = "llm"
    is_mock = False
    requires_api_key = True

    def __init__(self, provider_name: str, model_name: str) -> None:
        super().__init__(provider_name=provider_name, model_name=model_name)

    async def run(
        self,
        *,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 600,  # noqa: ARG002 — accepted for future use
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> ProviderResult:
        """Run a single chat-style completion. Returns a ProviderResult.

        On any exception or timeout, returns `status=failed` with `error` set
        and an empty `output["text"]`. Callers are expected to fall back to
        the mock.
        """
        started = time.perf_counter()
        job_id = str(uuid.uuid4())
        try:
            from emergentintegrations.llm.chat import LlmChat, UserMessage

            api_key = _emergent_key()
            if not api_key:
                raise RuntimeError("EMERGENT_LLM_KEY not configured")

            session_id = f"episode-studio-{job_id}"
            chat = LlmChat(
                api_key=api_key,
                session_id=session_id,
                system_message=system or "You are a senior episode writer for a 1–3 minute AI story video. Reply with only the requested text — no preamble.",
            ).with_model(self.provider_name, self.model_name)

            text = await asyncio.wait_for(
                chat.send_message(UserMessage(text=prompt)),
                timeout=timeout,
            )
            duration_ms = int((time.perf_counter() - started) * 1000)
            return ProviderResult(
                modality="llm",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_SUCCESS,
                estimated_credits=0,
                provider_job_id=job_id,
                output={"text": (text or "").strip()},
                error=None,
                message=f"Real LLM call succeeded in {duration_ms}ms.",
                meta={"duration_ms": duration_ms},
            )
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            err = type(exc).__name__ + ": " + str(exc)
            log.warning("Real LLM call failed in %dms — %s", duration_ms, err)
            return ProviderResult(
                modality="llm",
                provider_name=self.provider_name,
                model_name=self.model_name,
                mode="real",
                status=STATUS_FAILED,
                estimated_credits=0,
                provider_job_id=job_id,
                output={"text": ""},
                error=err[:500],  # cap defensively
                message="Real LLM call failed — falling back to mock.",
                meta={"duration_ms": duration_ms},
            )


__all__ = ["RealLLMProvider", "real_llm_available", "DEFAULT_TIMEOUT_S"]
