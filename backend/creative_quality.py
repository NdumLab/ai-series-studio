"""Creative Quality Engine — mock-only.

Deterministic, lightweight quality scoring + prompt enhancement helpers.

Nothing in this module talks to any external API. Phase 2B will replace these
deterministic mocks with real LLM-driven analysis behind feature flags.

The scoring is intentionally rule-based + reproducible so the UI and tests
behave predictably without ever needing the network.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------
QUALITY_KEYS = (
    "hook_strength",
    "conflict_strength",
    "emotional_tension",
    "visual_potential",
    "cliffhanger_strength",
    "dialogue_strength",
    "overall_story_score",
)

IMPROVE_KINDS = (
    "suspenseful",
    "emotional",
    "romantic",
    "darker",
    "cliffhanger",
    "realistic-dialogue",
    "cinematic",
)

ENHANCE_KINDS = (
    "image-prompt",
    "video-prompt",
    "scene-drama",
    "dialogue",
)


# ---------------------------------------------------------------------------
# Story quality scoring
# ---------------------------------------------------------------------------
_HOOK_KEYWORDS = ("never", "always", "suddenly", "what if", "before", "secret", "hidden")
_CONFLICT_KEYWORDS = ("but", "however", "against", "fight", "betray", "danger", "threat", "rival", "lose")
_EMOTION_KEYWORDS = ("love", "heart", "tear", "afraid", "joy", "pain", "ache", "longing", "hope", "grief")
_CLIFFHANGER_KEYWORDS = ("?", "…", "...", "cliff", "revealed", "to be", "next time", "tomorrow", "moment later")
_VISUAL_KEYWORDS = ("light", "shadow", "neon", "rain", "sunset", "smoke", "skyline", "door", "window", "mirror")
_DIALOGUE_QUOTES = ('"', '"', '"', "'", "'", "'")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _keyword_score(text: str, keywords) -> int:
    lower = (text or "").lower()
    hits = sum(lower.count(k) for k in keywords)
    return min(100, 35 + hits * 7)


def _dialogue_score(text: str) -> int:
    if not text:
        return 30
    quoted = sum(text.count(q) for q in _DIALOGUE_QUOTES)
    if quoted == 0:
        return 35
    # rough pairing — every 2 quotes = one line of dialogue
    lines = max(1, quoted // 2)
    return min(100, 45 + lines * 4)


def _clip(n: int, lo=20, hi=98) -> int:
    return max(lo, min(hi, int(n)))


def compute_quality_scores(idea: str, rewritten: str) -> Dict[str, int]:
    """Return deterministic mock quality scores for a story.

    Same inputs → same outputs. Phase 2B will replace this with an LLM call.
    """
    text = (rewritten or "").strip() or (idea or "").strip()
    wc = _word_count(text)
    # base from length so larger stories tend to score higher early on
    base = 40 + min(40, wc // 8)

    hook = _clip(base + _keyword_score(text, _HOOK_KEYWORDS) // 4)
    conflict = _clip(base + _keyword_score(text, _CONFLICT_KEYWORDS) // 4)
    emotion = _clip(base + _keyword_score(text, _EMOTION_KEYWORDS) // 4)
    visual = _clip(base + _keyword_score(text, _VISUAL_KEYWORDS) // 4)
    cliff = _clip(base + _keyword_score(text, _CLIFFHANGER_KEYWORDS) // 4)
    dialogue = _clip(_dialogue_score(text))

    overall = _clip(round((hook + conflict + emotion + visual + cliff + dialogue) / 6))
    return {
        "hook_strength": hook,
        "conflict_strength": conflict,
        "emotional_tension": emotion,
        "visual_potential": visual,
        "cliffhanger_strength": cliff,
        "dialogue_strength": dialogue,
        "overall_story_score": overall,
    }


# ---------------------------------------------------------------------------
# Improve story
# ---------------------------------------------------------------------------
_IMPROVE_PATCHES = {
    "suspenseful": {
        "note": "Tightened pacing, added foreshadowing beats and an unanswered question.",
        "snippet": "A faint, unfamiliar shadow moved across the wall. {first} The silence stretched a beat too long.",
    },
    "emotional": {
        "note": "Surfaced inner stakes and gave the protagonist a small, vulnerable confession.",
        "snippet": "{first} Their hands trembled, betraying something they hadn't said in years.",
    },
    "romantic": {
        "note": "Added tension and a meaningful, almost-touching moment.",
        "snippet": "{first} Their eyes met for a second too long — neither of them looked away.",
    },
    "darker": {
        "note": "Sharpened the threat and removed an easy out.",
        "snippet": "{first} What had felt like a way out turned out to be exactly the wrong door.",
    },
    "cliffhanger": {
        "note": "Pushed the final beat into an unresolved reveal.",
        "snippet": "{first} The screen cut to black on a single word: \"Run.\"",
    },
    "realistic-dialogue": {
        "note": "Rewrote dialogue with contractions, interruptions and natural rhythm.",
        "snippet": "{first} \"Wait — you're saying you already knew?\" \"I'm saying… I didn't want to.\"",
    },
    "cinematic": {
        "note": "Added a wide-to-close camera move and a memorable visual anchor.",
        "snippet": "{first} The camera pulled wide across rain-slick streets, then snapped in on a single neon sign flickering above the door.",
    },
}


def apply_improvement(rewritten: str, kind: str) -> Tuple[str, str]:
    """Apply a mock improvement and return (new_story, improvement_note)."""
    if kind not in IMPROVE_KINDS:
        raise ValueError(f"Unknown improvement kind: {kind}")
    patch = _IMPROVE_PATCHES[kind]
    base = (rewritten or "").strip()
    paragraphs = [p for p in base.split("\n\n") if p.strip()]
    first = paragraphs[0] if paragraphs else ""
    inserted = patch["snippet"].format(first=first).strip()
    if paragraphs:
        paragraphs[0] = inserted
    else:
        paragraphs = [inserted]
    new_story = "\n\n".join(paragraphs)
    return new_story, patch["note"]


# ---------------------------------------------------------------------------
# Scene tension & enhancements
# ---------------------------------------------------------------------------
_EMOTIONAL_GOALS = [
    "Establish stakes and hint at the larger conflict.",
    "Force the protagonist to reveal a hidden fear.",
    "Push two opposing desires into open conflict.",
    "Give the audience a brief, dangerous hope.",
    "Land the emotional cost of an earlier decision.",
    "Tilt the alliance — someone is no longer who they seemed.",
]
_CONFLICT_POINTS = [
    "Protagonist's instinct clashes with the plan.",
    "An ally hesitates at the worst possible moment.",
    "The objective shifts mid-scene.",
    "A new piece of information changes the cost.",
    "A small betrayal sets a bigger one in motion.",
    "Time runs out before resolution is possible.",
]
_TURNING_POINTS = [
    "A small truth is finally said out loud.",
    "An object/photo/letter is found and reframes the past.",
    "A door closes behind them — there's no walking back.",
    "Someone breaks character — the audience sees the real them.",
    "A bystander steps in and changes the math.",
    "The plan succeeds — and immediately costs something else.",
]
_CLIFFHANGERS = [
    "A name is whispered just as the scene cuts to black.",
    "A phone rings unanswered on an empty desk.",
    "A door opens — and the camera doesn't follow.",
    "A character looks directly at us for the first time.",
    "The lights cut, and a single voice continues in the dark.",
    "A silent beat, then the title card.",
]


def _stable_index(seed: str, size: int) -> int:
    """Pick a deterministic index from a string seed (so re-runs are stable)."""
    h = hashlib.sha256((seed or "").encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % max(1, size)


def compute_scene_tension(scene: Dict, index: int = 0) -> Dict:
    """Deterministic mock fields for a single scene."""
    seed = (scene.get("id") or "") + "|" + (scene.get("title") or "") + f"|{index}"
    rng = random.Random(seed)
    base = 35 + rng.randint(0, 50)
    # Bump tension when the scene's prompt/dialogue hints at conflict
    text = " ".join(
        str(scene.get(k) or "") for k in ("title", "visual_prompt", "dialogue")
    ).lower()
    if any(k in text for k in _CONFLICT_KEYWORDS):
        base = min(100, base + 10)
    if any(k in text for k in _CLIFFHANGER_KEYWORDS):
        base = min(100, base + 5)
    tension = max(15, min(99, base))
    cliff_value = min(99, tension + rng.randint(-10, 10))
    return {
        "tension_level": tension,
        "emotional_goal": _EMOTIONAL_GOALS[_stable_index(seed + "g", len(_EMOTIONAL_GOALS))],
        "conflict_point": _CONFLICT_POINTS[_stable_index(seed + "c", len(_CONFLICT_POINTS))],
        "reveal_or_turning_point": _TURNING_POINTS[_stable_index(seed + "t", len(_TURNING_POINTS))],
        "cliffhanger_value": cliff_value,
    }


# ---------------------------------------------------------------------------
# Prompt enhancement
# ---------------------------------------------------------------------------
IMAGE_PROMPT_TRAITS = ("realism", "lighting", "character consistency", "camera framing")
VIDEO_PROMPT_TRAITS = ("motion", "continuity", "emotion", "camera movement")

_IMAGE_TAIL = (
    "Photoreal cinematic still, soft volumetric lighting, shallow depth of field, "
    "anamorphic lens framing, consistent character anatomy and wardrobe across shots."
)
_VIDEO_TAIL = (
    "Smooth camera dolly, naturalistic motion easing, consistent lighting and "
    "character placement frame-to-frame, emotional micro-expressions, 24fps cinematic feel."
)


def enhance_image_prompt(raw: str, scene: Dict) -> str:
    base = (raw or scene.get("visual_prompt") or "").strip()
    cam = (scene.get("camera_direction") or "Medium shot").strip()
    loc = (scene.get("location") or "").strip()
    parts = [base or scene.get("title", "")]
    if loc:
        parts.append(f"Location: {loc}.")
    parts.append(f"Camera: {cam}.")
    parts.append(_IMAGE_TAIL)
    return " ".join(p for p in parts if p)


def enhance_video_prompt(raw: str, scene: Dict) -> str:
    base = (raw or scene.get("visual_prompt") or "").strip()
    cam = (scene.get("camera_direction") or "Medium shot").strip()
    mood = (scene.get("music_mood") or "Cinematic").strip()
    parts = [base or scene.get("title", "")]
    parts.append(f"Camera: {cam}.")
    parts.append(f"Tone: {mood}.")
    parts.append(_VIDEO_TAIL)
    return " ".join(p for p in parts if p)


def improve_scene_drama(scene: Dict) -> Dict:
    """Return updates for a scene to push more drama (mock)."""
    tension = scene.get("tension_level") or 50
    return {
        "tension_level": min(99, int(tension) + 12),
        "dialogue": _heighten_dialogue(scene.get("dialogue") or "", flavor="drama"),
        "reveal_or_turning_point": _TURNING_POINTS[
            _stable_index((scene.get("id") or "") + "drama", len(_TURNING_POINTS))
        ],
    }


def improve_scene_dialogue(scene: Dict) -> Dict:
    return {
        "dialogue": _heighten_dialogue(scene.get("dialogue") or "", flavor="realistic"),
    }


def _heighten_dialogue(existing: str, flavor: str) -> str:
    if flavor == "realistic":
        prefix = '"Hey — wait. You\'re sure about this?" "I\'m not. But I\'m doing it anyway."'
    else:
        prefix = '"You don\'t get to walk away from this." "Watch me."'
    if existing.strip():
        return f"{prefix}\n{existing.strip()}"
    return prefix


IMAGE_ENHANCEMENT_HINT = (
    "This image prompt is enhanced for: realism, lighting, character consistency, "
    "camera framing."
)
VIDEO_ENHANCEMENT_HINT = (
    "This video prompt is enhanced for: motion, continuity, emotion, camera movement."
)


__all__ = [
    "QUALITY_KEYS",
    "IMPROVE_KINDS",
    "ENHANCE_KINDS",
    "compute_quality_scores",
    "apply_improvement",
    "compute_scene_tension",
    "enhance_image_prompt",
    "enhance_video_prompt",
    "improve_scene_drama",
    "improve_scene_dialogue",
    "IMAGE_PROMPT_TRAITS",
    "VIDEO_PROMPT_TRAITS",
    "IMAGE_ENHANCEMENT_HINT",
    "VIDEO_ENHANCEMENT_HINT",
]
