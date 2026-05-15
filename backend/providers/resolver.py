"""Provider resolution.

Resolution priority (highest wins):
  1. Character override            (voice modality only — character.voice_provider)
  2. Project override              (when project.provider_override_enabled = True)
  3. Global default                (provider_settings doc)
  4. Hard fallback                 (modality-specific mock default)

`resolve_provider()` is modality-agnostic. `resolve_voice_for_character()` is
a convenience wrapper for the voice modality that also folds in the character
override layer.

This module is pure-logic. It accepts already-loaded dicts (project, character,
global settings) so it stays trivially testable.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import Modality, MODALITIES

# Map modality → (provider_field, model_field) on a Project document.
# `export` uses `export_mode` instead of `export_model` to match the existing schema.
_PROJECT_FIELDS = {
    "llm": ("llm_provider", "llm_model"),
    "image": ("image_provider", "image_model"),
    "video": ("video_provider", "video_model"),
    "voice": ("voice_provider", "voice_model"),
    "music": ("music_provider", "music_model"),
    "export": ("export_provider", "export_mode"),
}

# Hard fallback if neither the project nor global settings have anything (e.g.
# someone wipes provider_settings). These are mock identifiers.
_HARD_FALLBACK = {
    "llm":    {"provider": "mock-llm",    "model": "mock-rewrite"},
    "image":  {"provider": "mock-image",  "model": "mock-still"},
    "video":  {"provider": "mock-video",  "model": "mock-clip-5s"},
    "voice":  {"provider": "mock-voice",  "model": "mock-narrator"},
    "music":  {"provider": "mock-music",  "model": "mock-mood"},
    "export": {"provider": "mock-export", "model": "mock-stitch"},
}


def _global_view(global_settings: Dict[str, Any], modality: Modality) -> Dict[str, str]:
    cfg = (global_settings or {}).get(modality) or {}
    return {
        "provider": (cfg.get("provider") or "").strip(),
        "model": (cfg.get("model") or "").strip(),
    }


def _project_view(project: Dict[str, Any], modality: Modality) -> Dict[str, str]:
    prov_field, model_field = _PROJECT_FIELDS[modality]
    return {
        "provider": (project.get(prov_field) or "").strip(),
        "model": (project.get(model_field) or "").strip(),
    }


def resolve_provider(
    *,
    modality: Modality,
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Resolve effective provider+model for a project at the given modality.

    Returns a dict shaped:
        {
          "modality": ...,
          "provider": "...",
          "model": "...",
          "source": "project" | "global" | "global-fallback" | "hard-fallback",
        }
    """
    if modality not in MODALITIES:
        raise ValueError(f"Unknown modality: {modality}")

    override_on = bool((project or {}).get("provider_override_enabled"))
    proj_view = _project_view(project or {}, modality)
    glob_view = _global_view(global_settings or {}, modality)

    if override_on and proj_view["provider"]:
        return {
            "modality": modality,
            "provider": proj_view["provider"],
            "model": proj_view["model"],
            "source": "project",
        }
    if override_on and not proj_view["provider"] and glob_view["provider"]:
        # override is on but the project hasn't picked one — fall back to global
        return {
            "modality": modality,
            "provider": glob_view["provider"],
            "model": glob_view["model"],
            "source": "global-fallback",
        }
    if glob_view["provider"]:
        return {
            "modality": modality,
            "provider": glob_view["provider"],
            "model": glob_view["model"],
            "source": "global",
        }
    fb = _HARD_FALLBACK[modality]
    return {
        "modality": modality,
        "provider": fb["provider"],
        "model": fb["model"],
        "source": "hard-fallback",
    }


def resolve_voice_for_character(
    *,
    character: Optional[Dict[str, Any]],
    project: Optional[Dict[str, Any]],
    global_settings: Dict[str, Any],
) -> Dict[str, Any]:
    """Voice resolution with character override layer on top.

    Returns the same shape as `resolve_provider()` but the source can also be
    `"character"` when the character has its own voice_provider.
    """
    cv_provider = ((character or {}).get("voice_provider") or "").strip()
    cv_model = ((character or {}).get("voice_model") or "").strip()
    if cv_provider:
        return {
            "modality": "voice",
            "provider": cv_provider,
            "model": cv_model,
            "source": "character",
        }
    return resolve_provider(
        modality="voice",
        project=project,
        global_settings=global_settings,
    )
