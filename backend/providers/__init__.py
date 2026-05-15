"""Provider service layer for AI Episode Studio.

Phase 2A foundation: defines provider interfaces, mock implementations, a
resolver (global → project → character) and an execution guard. All real
providers are blocked by feature flags + missing keys today — only mock
providers run.

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
    "resolve_provider",
    "resolve_voice_for_character",
    "execute_provider",
    "execute_llm",
    "run_modality_test",
    "provider_status",
    "set_activity_recorder",
]
