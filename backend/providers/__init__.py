"""Provider service layer for AI Episode Studio.

Defines provider interfaces, mock implementations, a resolver (global →
project → character) and execution guards. Real LLM, OpenAI image, and Luma
video providers are disabled by default and require feature flags plus
server-side runtime/secrets before they can run.

Public surface:
    from providers import (
        ProviderResult,
        BaseProvider,
        MODALITIES,
        resolve_provider,
        execute_provider,
        run_modality_test,
        provider_status,
    )
"""
from .base import (
    ProviderResult,
    BaseProvider,
    MockProviderMixin,
    MODALITIES,
    STATUS_SUCCESS,
)
from .resolver import resolve_provider, resolve_voice_for_character
from .executor import (
    execute_provider,
    execute_llm,
    run_modality_test,
    provider_status,
    set_activity_recorder,
)

__all__ = [
    "ProviderResult",
    "BaseProvider",
    "MockProviderMixin",
    "MODALITIES",
    "STATUS_SUCCESS",
    "resolve_provider",
    "resolve_voice_for_character",
    "execute_provider",
    "execute_llm",
    "run_modality_test",
    "provider_status",
    "set_activity_recorder",
]
