"""AI Episode Studio - MVP backend (mock generation, no external APIs)."""
from fastapi import FastAPI, APIRouter, Depends, Header, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import asyncio
import logging
import random
import secrets
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone, timedelta


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="AI Episode Studio API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("episode-studio")

# Phase 2A provider service layer (mock-only foundation).
from providers import (  # noqa: E402  (kept after logger init)
    MODALITIES as PROVIDER_LAYER_MODALITIES,
    execute_provider,
    execute_llm,
    provider_status,
    resolve_provider,
    resolve_voice_for_character,
    run_modality_test,
    set_activity_recorder,
)
# Phase 2C creative quality engine (mock-only).
from creative_quality import (  # noqa: E402
    QUALITY_KEYS,
    IMPROVE_KINDS,
    ENHANCE_KINDS,
    compute_quality_scores,
    apply_improvement,
    compute_scene_tension,
    enhance_image_prompt,
    enhance_video_prompt,
    improve_scene_drama,
    improve_scene_dialogue,
    IMAGE_PROMPT_TRAITS,
    VIDEO_PROMPT_TRAITS,
    IMAGE_ENHANCEMENT_HINT,
    VIDEO_ENHANCEMENT_HINT,
)
from auth_utils import (  # noqa: E402
    bearer_token,
    hash_password,
    normalize_email,
    public_user,
    verify_password,
)


# Activity recorder — writes safe metadata to the `provider_activity` collection.
# Never includes prompts, raw outputs, or API keys.
_PROVIDER_ACTIVITY_SAFE_FIELDS = {
    "modality", "provider_name", "model_name", "source", "mode", "status",
    "estimated_credits", "provider_job_id", "message", "error", "duration_ms",
    "project_id", "scene_id", "segment_id", "feature_flag_enabled", "key_present",
}


async def _record_provider_activity(record: dict) -> None:
    # Strict allowlist — anything outside this set is dropped.
    safe = {k: v for k, v in record.items() if k in _PROVIDER_ACTIVITY_SAFE_FIELDS}
    safe["id"] = str(uuid.uuid4())
    safe["created_at"] = datetime.now(timezone.utc).isoformat()
    await db.provider_activity.insert_one(safe)


set_activity_recorder(_record_provider_activity)

# ---------------------------------------------------------------------------
# Constants & mock asset pools
# ---------------------------------------------------------------------------
DEFAULT_USER_ID = "user-demo"
DEFAULT_USER = {
    "id": DEFAULT_USER_ID,
    "name": "Demo Creator",
    "email": "demo@episode.studio",
    "role": "creator",
    "credits": 250,
    "created_at": datetime.now(timezone.utc).isoformat(),
}

# Local development remains demo-friendly: requests without a bearer token use
# the seeded demo user. Authenticated beta users receive isolated projects.
AUTH_DEMO_MODE = os.environ.get("AUTH_DEMO_MODE", "true").strip().lower() != "false"

MOCK_SCENE_IMAGES = [
    "https://static.prod-images.emergentagent.com/jobs/79e2f754-43ce-44a2-9d11-60523bb0d255/images/623d1bffe45150b2f2ede70157aed5fe723bbd8f51fa49c37a6ca79970a2b82c.png",
    "https://static.prod-images.emergentagent.com/jobs/79e2f754-43ce-44a2-9d11-60523bb0d255/images/8b466f1bd6dcd2d931e8035ea08abd83e6da41e8dfb8cb69e0fdc1ff86dad122.png",
    "https://images.unsplash.com/photo-1518709268805-4e9042af2176?w=1280&q=80",
    "https://images.unsplash.com/photo-1478479474757-39c8b633474a?w=1280&q=80",
    "https://images.unsplash.com/photo-1534447677768-be436bb09401?w=1280&q=80",
    "https://images.unsplash.com/photo-1502134249126-9f3755a50d78?w=1280&q=80",
]
MOCK_CHARACTER_IMAGE = (
    "https://static.prod-images.emergentagent.com/jobs/79e2f754-43ce-44a2-9d11-60523bb0d255/"
    "images/e7f594932d8af1231fb8f1fb8853952c8c60fea7ce40ad3450bb2fe15a086998.png"
)
MOCK_VIDEO_URLS = [
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
]

VOICE_OPTIONS = ["Narrator-Deep", "Narrator-Warm", "Hero-Bold", "Heroine-Calm", "Villain-Raspy", "Child-Bright"]
MUSIC_MOODS = ["Cinematic", "Tense", "Uplifting", "Mysterious", "Romantic", "Action", "Melancholic"]

COSTS = {
    "rewrite": 3,
    "split_scenes": 4,
    "image": 2,
    "video_segment": 12,
    "voice": 1,
    "music": 2,
    "export": 5,
}

# ---------------------------------------------------------------------------
# Provider catalog (display only — no real calls)
# ---------------------------------------------------------------------------
PROVIDER_CATALOG = {
    "llm": [
        {"id": "openai", "label": "OpenAI", "models": ["gpt-5.2", "gpt-4o", "gpt-4o-mini"]},
        {"id": "anthropic", "label": "Claude", "models": ["claude-sonnet-4.5", "claude-opus-4.5", "claude-haiku-4.5"]},
        {"id": "gemini", "label": "Gemini", "models": ["gemini-3-pro", "gemini-3-flash"]},
        {"id": "custom", "label": "Custom provider/model ID", "models": []},
    ],
    "image": [
        {"id": "fal", "label": "fal.ai", "models": ["flux-pro", "flux-dev", "ideogram-v2"]},
        {"id": "gemini-nano-banana", "label": "Gemini Nano Banana", "models": ["nano-banana"]},
        {"id": "openai-image", "label": "OpenAI gpt-image-1", "models": ["gpt-image-1"]},
        {"id": "custom", "label": "Custom image provider", "models": []},
    ],
    "video": [
        {"id": "sora-2", "label": "Sora 2", "models": ["sora-2"]},
        {"id": "runway", "label": "Runway Gen-4.5", "models": ["gen-4.5", "gen-4.5-turbo"]},
        {"id": "luma", "label": "Luma Ray / Dream Machine", "models": ["ray-2", "dream-machine-1.6"]},
        {"id": "custom", "label": "Custom video provider", "models": []},
    ],
    "voice": [
        {"id": "elevenlabs", "label": "ElevenLabs", "models": ["eleven-v3", "eleven-turbo"]},
        {"id": "openai-tts", "label": "OpenAI TTS", "models": ["tts-1-hd", "tts-1"]},
        {"id": "google-tts", "label": "Google Cloud TTS", "models": ["studio", "neural2"]},
        {"id": "custom", "label": "Custom voice provider", "models": []},
    ],
    "music": [
        {"id": "suno", "label": "Suno", "models": ["v4", "v3.5"]},
        {"id": "udio", "label": "Udio", "models": ["udio-130", "udio-32"]},
        {"id": "elevenlabs-music", "label": "ElevenLabs Music", "models": ["music-v1"]},
        {"id": "mubert", "label": "Mubert", "models": ["pro", "standard"]},
        {"id": "custom", "label": "Custom music provider", "models": []},
    ],
    "export": [
        {"id": "ffmpeg-local", "label": "FFmpeg local worker", "models": ["ffmpeg-6"]},
        {"id": "aws-mediaconvert", "label": "AWS MediaConvert", "models": ["default"]},
        {"id": "custom", "label": "Custom export worker", "models": []},
    ],
}

PROVIDER_MODALITIES = list(PROVIDER_CATALOG.keys())

# Per-modality "model field" name on a project. Spec uses `export_mode` instead of
# `export_model` for the export modality, so the mapping is explicit.
PROJECT_FIELD_MAP = {
    "llm":    {"provider": "llm_provider",    "model": "llm_model"},
    "image":  {"provider": "image_provider",  "model": "image_model"},
    "video":  {"provider": "video_provider",  "model": "video_model"},
    "voice":  {"provider": "voice_provider",  "model": "voice_model"},
    "music":  {"provider": "music_provider",  "model": "music_model"},
    "export": {"provider": "export_provider", "model": "export_mode"},
}

FEATURE_FLAG_KEYS = {
    "llm":    "USE_REAL_LLM_PROVIDER",
    "image":  "USE_REAL_IMAGE_PROVIDER",
    "video":  "USE_REAL_VIDEO_PROVIDER",
    "voice":  "USE_REAL_VOICE_PROVIDER",
    "music":  "USE_REAL_MUSIC_PROVIDER",
    "export": "USE_REAL_EXPORT_PROVIDER",
}


def feature_flags() -> dict:
    """Read USE_REAL_*_PROVIDER flags from env. Anything not 'true' is False."""
    out = {}
    for modality, env_key in FEATURE_FLAG_KEYS.items():
        out[modality] = os.environ.get(env_key, "false").strip().lower() == "true"
    out["any_real"] = any(out.values())
    return out


def _int_env(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, str(default)))
    except (TypeError, ValueError):
        return default


def studio_config() -> dict:
    """User-tunable thresholds. All read at request time so .env changes
    take effect without a restart."""
    return {
        "wallet_credits": _int_env("WALLET_CREDITS", 250),
        "high_cost_scene_threshold_percent": _int_env(
            "HIGH_COST_SCENE_THRESHOLD_PERCENT", 25
        ),
    }


def _wallet_state(pct: float) -> str:
    if pct > 100:
        return "insufficient"
    if pct >= 71:
        return "high"
    if pct >= 41:
        return "warning"
    return "normal"

DEFAULT_PROVIDER_SETTINGS = {
    "llm": {"provider": "openai", "model": "gpt-5.2", "custom_provider": "", "custom_model": ""},
    "image": {"provider": "fal", "model": "flux-pro", "custom_provider": "", "custom_model": ""},
    "video": {"provider": "sora-2", "model": "sora-2", "custom_provider": "", "custom_model": ""},
    "voice": {"provider": "elevenlabs", "model": "eleven-v3", "custom_provider": "", "custom_model": ""},
    "music": {"provider": "suno", "model": "v4", "custom_provider": "", "custom_model": ""},
    "export": {"provider": "ffmpeg-local", "model": "ffmpeg-6", "custom_provider": "", "custom_model": ""},
}
SETTINGS_DOC_ID = "global"

# ---------------------------------------------------------------------------
# Provider settings (selection only — no real calls, no API keys stored)
# ---------------------------------------------------------------------------
class ProviderModalitySetting(BaseModel):
    provider: str
    model: str = ""
    custom_provider: str = ""
    custom_model: str = ""


class ProviderSettingsUpdate(BaseModel):
    llm: Optional[ProviderModalitySetting] = None
    image: Optional[ProviderModalitySetting] = None
    video: Optional[ProviderModalitySetting] = None
    voice: Optional[ProviderModalitySetting] = None
    music: Optional[ProviderModalitySetting] = None
    export: Optional[ProviderModalitySetting] = None


class ProviderTestRequest(BaseModel):
    modality: Literal["llm", "image", "video", "voice", "music", "export"]


async def _load_provider_settings() -> dict:
    doc = await db.provider_settings.find_one({"id": SETTINGS_DOC_ID}, {"_id": 0})
    if not doc:
        doc = {
            "id": SETTINGS_DOC_ID,
            "mock_mode": True,
            "updated_at": now_iso(),
            **DEFAULT_PROVIDER_SETTINGS,
        }
        await db.provider_settings.insert_one(doc.copy())
    # Always force mock_mode True until real APIs are wired
    doc["mock_mode"] = True
    return doc


@api.get("/settings/providers/options")
async def provider_options():
    return {
        "modalities": PROVIDER_MODALITIES,
        "catalog": PROVIDER_CATALOG,
        "mock_mode": True,
    }


@api.get("/settings/providers")
async def get_provider_settings():
    return await _load_provider_settings()


@api.put("/settings/providers")
async def update_provider_settings(body: ProviderSettingsUpdate):
    update: dict = {"updated_at": now_iso()}
    body_dict = body.model_dump(exclude_none=True)
    for modality, val in body_dict.items():
        if modality not in PROVIDER_MODALITIES:
            continue
        valid_ids = {p["id"] for p in PROVIDER_CATALOG[modality]}
        if val.get("provider") not in valid_ids:
            raise HTTPException(400, f"Unknown {modality} provider: {val.get('provider')}")
        update[modality] = {
            "provider": val.get("provider"),
            "model": (val.get("model") or "").strip(),
            "custom_provider": (val.get("custom_provider") or "").strip(),
            "custom_model": (val.get("custom_model") or "").strip(),
        }
    await db.provider_settings.update_one(
        {"id": SETTINGS_DOC_ID},
        {"$set": update},
        upsert=True,
    )
    return await _load_provider_settings()


@api.post("/settings/providers/test")
async def test_provider_connection(body: ProviderTestRequest):
    settings = await _load_provider_settings()
    cfg = settings.get(body.modality, {})
    return {
        "modality": body.modality,
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "ok": True,
        "mock_mode": True,
        "message": "Mock mode active — real provider call skipped.",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


async def log_generation(gen_type: str, project_id: Optional[str], cost: int,
                         status: str = "success", error: Optional[str] = None,
                         user_id: str = DEFAULT_USER_ID) -> None:
    await db.generations.insert_one({
        "id": new_id(),
        "user_id": user_id,
        "project_id": project_id,
        "type": gen_type,
        "cost_credits": cost,
        "status": status,
        "error": error,
        "created_at": now_iso(),
    })


async def ensure_default_user() -> None:
    existing = await db.users.find_one({"id": DEFAULT_USER_ID}, {"_id": 0})
    if not existing:
        await db.users.insert_one(DEFAULT_USER.copy())


async def _create_session(user_id: str) -> dict:
    token = secrets.token_urlsafe(32)
    doc = {
        "id": new_id(),
        "token": token,
        "user_id": user_id,
        "created_at": now_iso(),
    }
    await db.user_sessions.insert_one(doc.copy())
    return doc


async def current_user(authorization: Optional[str] = Header(None)) -> dict:
    await ensure_default_user()
    token = bearer_token(authorization)
    if token:
        sess = await db.user_sessions.find_one({"token": token}, {"_id": 0})
        if not sess:
            raise HTTPException(401, "Invalid or expired session")
        user = await db.users.find_one({"id": sess["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(401, "Session user not found")
        return user
    if AUTH_DEMO_MODE:
        return await db.users.find_one({"id": DEFAULT_USER_ID}, {"_id": 0})
    raise HTTPException(401, "Authentication required")


def _project_owner_filter(project_id: str, user: dict, include_deleted: bool = False) -> dict:
    base = {"id": project_id, "user_id": user["id"]}
    return base if include_deleted else _active_project_filter(base)


async def _owned_project(project_id: str, user: dict, include_deleted: bool = False) -> dict:
    proj = await db.projects.find_one(
        _project_owner_filter(project_id, user, include_deleted), {"_id": 0}
    )
    if not proj:
        raise HTTPException(404, "Project not found")
    return proj


async def _owned_scene(scene_id: str, user: dict) -> dict:
    scene = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
    if not scene:
        raise HTTPException(404, "Scene not found")
    await _owned_project(scene["project_id"], user)
    return scene


async def _owned_character(character_id: str, user: dict) -> dict:
    char = await db.characters.find_one({"id": character_id}, {"_id": 0})
    if not char:
        raise HTTPException(404, "Character not found")
    await _owned_project(char["project_id"], user)
    return char


async def _owned_segment(segment_id: str, user: dict) -> dict:
    seg = await db.segments.find_one({"id": segment_id}, {"_id": 0})
    if not seg:
        raise HTTPException(404, "Segment not found")
    await _owned_project(seg["project_id"], user)
    return seg


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    title: str
    idea: str = ""


class AuthRegister(BaseModel):
    name: str
    email: str
    password: str


class AuthLogin(BaseModel):
    email: str
    password: str


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    idea: Optional[str] = None
    rewritten_story: Optional[str] = None
    status: Optional[str] = None


class CharacterCreate(BaseModel):
    name: str
    description: str = ""
    voice_style: str = "Narrator-Warm"
    voice_provider: str = ""
    voice_model: str = ""
    reference_image_url: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    voice_style: Optional[str] = None
    voice_provider: Optional[str] = None
    voice_model: Optional[str] = None
    reference_image_url: Optional[str] = None


class SceneCreate(BaseModel):
    title: str
    duration: int = 10
    location: str = ""
    characters: List[str] = []
    visual_prompt: str = ""
    dialogue: str = ""
    music_mood: str = "Cinematic"
    camera_direction: str = "Medium shot"
    voice: str = "Narrator-Warm"


class SceneUpdate(BaseModel):
    title: Optional[str] = None
    duration: Optional[int] = None
    location: Optional[str] = None
    characters: Optional[List[str]] = None
    visual_prompt: Optional[str] = None
    dialogue: Optional[str] = None
    music_mood: Optional[str] = None
    camera_direction: Optional[str] = None
    voice: Optional[str] = None
    image_url: Optional[str] = None
    status: Optional[str] = None


class CostEstimateRequest(BaseModel):
    operations: dict  # {"image": 4, "video_segment": 6, ...}


class SegmentStatus(BaseModel):
    status: Literal["approved", "rejected", "pending"]


class SegmentUpdate(BaseModel):
    continuity_prompt: Optional[str] = None
    expand_mode: Optional[Literal["initial", "expand"]] = None
    duration: Optional[int] = None
    status: Optional[Literal["approved", "rejected", "pending"]] = None


class ReorderScenesBody(BaseModel):
    scene_ids: List[str]


class ReorderSegmentsBody(BaseModel):
    segment_ids: List[str]


class ReorderCharactersBody(BaseModel):
    character_ids: List[str]


class SegmentCreate(BaseModel):
    continuity_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Mock generators
# ---------------------------------------------------------------------------
def mock_rewrite_story(idea: str) -> str:
    idea = (idea or "").strip() or "An untitled mystery"
    return (
        f"COLD OPEN — A sweeping aerial shot establishes the world. "
        f"We meet our protagonist as the inciting moment strikes.\n\n"
        f"ACT I — {idea}. The stakes are revealed through a tense exchange and a personal cost.\n\n"
        f"ACT II — Allies are tested, secrets surface, and a turning point forces a choice. "
        f"A motif (a sound, an object) recurs to anchor the emotional spine.\n\n"
        f"ACT III — In a kinetic climax, the protagonist confronts the antagonist. "
        f"A bittersweet resolution lands on a single, lingering frame.\n\n"
        f"TAG — A quiet beat that hints at what comes next."
    )


def mock_split_scenes(rewritten: str) -> List[dict]:
    presets = [
        ("Cold Open", "Establishing aerial → city skyline at dusk", "Skyline Rooftop", "Cinematic", "Crane down to medium"),
        ("Inciting Incident", "Protagonist receives the call that changes everything", "Apartment Kitchen", "Tense", "Handheld push-in"),
        ("Rising Conflict", "Allies argue over the path forward; lights flicker", "Underground Bunker", "Mysterious", "Wide two-shot, slow dolly"),
        ("Turning Point", "A secret is revealed in the rain", "Empty Street, Night", "Melancholic", "Low-angle close-up"),
        ("Climax", "Confrontation under flickering neon", "Abandoned Warehouse", "Action", "Tracking shot, rapid cuts"),
        ("Resolution", "A quiet exhale on a single lingering frame", "Hilltop at Dawn", "Uplifting", "Static wide, golden hour"),
    ]
    scenes = []
    for i, (title, prompt, location, mood, cam) in enumerate(presets):
        scenes.append({
            "title": title,
            "duration": 15,
            "location": location,
            "characters": [],
            "visual_prompt": prompt,
            "dialogue": "",
            "music_mood": mood,
            "camera_direction": cam,
            "voice": "Narrator-Warm",
            "image_url": None,
            "status": "draft",
            "order": i,
        })
    return scenes


# ---------------------------------------------------------------------------
# Routes — health & meta
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"service": "AI Episode Studio", "status": "ok"}


@api.get("/meta/options")
async def meta_options():
    return {
        "voices": VOICE_OPTIONS,
        "music_moods": MUSIC_MOODS,
        "costs": COSTS,
    }


@api.post("/auth/register")
async def auth_register(body: AuthRegister):
    email = normalize_email(body.email)
    name = body.name.strip()
    password = body.password or ""
    if not name:
        raise HTTPException(400, "Name is required")
    if "@" not in email:
        raise HTTPException(400, "Valid email is required")
    if len(password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(400, "Email is already registered")
    salt, digest = hash_password(password)
    user = {
        "id": new_id(),
        "name": name,
        "email": email,
        "role": "creator",
        "credits": 250,
        "password_salt": salt,
        "password_hash": digest,
        "created_at": now_iso(),
    }
    await db.users.insert_one(user.copy())
    session = await _create_session(user["id"])
    return {"token": session["token"], "user": public_user(user)}


@api.post("/auth/login")
async def auth_login(body: AuthLogin):
    email = normalize_email(body.email)
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not user.get("password_salt"):
        raise HTTPException(401, "Invalid email or password")
    if not verify_password(body.password or "", user["password_salt"], user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    session = await _create_session(user["id"])
    return {"token": session["token"], "user": public_user(user)}


@api.post("/auth/logout")
async def auth_logout(authorization: Optional[str] = Header(None)):
    token = bearer_token(authorization)
    if token:
        await db.user_sessions.delete_one({"token": token})
    return {"ok": True}


@api.get("/me")
async def me(user: dict = Depends(current_user)):
    return public_user(user)


@api.get("/feature-flags")
async def get_feature_flags():
    """Real-provider feature flags. All false until backend is wired to live providers."""
    return feature_flags()


# ---------------------------------------------------------------------------
# Phase 2A unified provider endpoints (foundation only — no real calls)
# ---------------------------------------------------------------------------
class UnifiedProviderTestRequest(BaseModel):
    modality: Literal["llm", "image", "video", "voice", "music", "export"]
    project_id: Optional[str] = None


@api.post("/providers/test")
async def providers_test(body: UnifiedProviderTestRequest, user: dict = Depends(current_user)):
    """Dry-run for any modality. No real network call is ever made.

    Returns the resolved provider, feature flag state, and key status so the
    UI can clearly explain why a real call would (or would not) execute.
    """
    project = None
    if body.project_id:
        project = await _owned_project(body.project_id, user)
    global_settings = await _load_provider_settings()
    return await run_modality_test(
        modality=body.modality,
        project=project,
        global_settings=global_settings,
    )


@api.get("/providers/{modality}/status")
async def providers_status_endpoint(
    modality: str,
    project_id: Optional[str] = None,
    user: dict = Depends(current_user),
):
    """Snapshot of resolved provider, feature flag and key for one modality."""
    if modality not in PROVIDER_LAYER_MODALITIES:
        raise HTTPException(400, f"Unknown modality: {modality}")
    project = None
    if project_id:
        project = await _owned_project(project_id, user)
    global_settings = await _load_provider_settings()
    return provider_status(
        modality=modality,  # type: ignore[arg-type]
        project=project,
        global_settings=global_settings,
    )


@api.get("/config")
async def get_studio_config():
    """Tunable thresholds (wallet credits, high-cost-scene threshold)."""
    return {**studio_config(), "mock_mode": True}


# ---------------------------------------------------------------------------
# Project provider override (per-project, mock-only)
# ---------------------------------------------------------------------------
class ProjectProvidersUpdate(BaseModel):
    provider_override_enabled: Optional[bool] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    image_provider: Optional[str] = None
    image_model: Optional[str] = None
    video_provider: Optional[str] = None
    video_model: Optional[str] = None
    voice_provider: Optional[str] = None
    voice_model: Optional[str] = None
    music_provider: Optional[str] = None
    music_model: Optional[str] = None
    export_provider: Optional[str] = None
    export_mode: Optional[str] = None


def _project_modality_view(project: dict, modality: str, source_label: str) -> dict:
    fmap = PROJECT_FIELD_MAP[modality]
    return {
        "provider": project.get(fmap["provider"], "") or "",
        "model": project.get(fmap["model"], "") or "",
        "source": source_label,
    }


def _global_modality_view(global_settings: dict, modality: str) -> dict:
    cfg = global_settings.get(modality, {}) or {}
    return {
        "provider": cfg.get("provider", "") or "",
        "model": cfg.get("model", "") or "",
        "custom_provider": cfg.get("custom_provider", "") or "",
        "custom_model": cfg.get("custom_model", "") or "",
        "source": "global",
    }


async def _build_effective_providers(project: dict) -> dict:
    """Returns the effective config that *would* be used for each modality.
    When override is off → values come from global. When on → from the project."""
    global_settings = await _load_provider_settings()
    override_on = bool(project.get("provider_override_enabled"))
    effective: dict = {}
    for modality in PROVIDER_MODALITIES:
        if override_on:
            view = _project_modality_view(project, modality, "project")
            # Fall back to global value if the project didn't choose one yet.
            if not view["provider"]:
                view = _global_modality_view(global_settings, modality)
                view["source"] = "global-fallback"
        else:
            view = _global_modality_view(global_settings, modality)
        effective[modality] = view
    return effective


@api.get("/projects/{project_id}/providers")
async def get_project_providers(project_id: str, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user)
    effective = await _build_effective_providers(proj)
    project_view = {
        modality: _project_modality_view(proj, modality, "project")
        for modality in PROVIDER_MODALITIES
    }
    return {
        "project_id": project_id,
        "provider_override_enabled": bool(proj.get("provider_override_enabled")),
        "feature_flags": feature_flags(),
        "mock_mode": True,
        "project": project_view,
        "effective": effective,
    }


@api.put("/projects/{project_id}/providers")
async def update_project_providers(
    project_id: str,
    body: ProjectProvidersUpdate,
    user: dict = Depends(current_user),
):
    proj = await _owned_project(project_id, user)
    payload = body.model_dump(exclude_none=True)

    # Validate any provided provider id against the catalog (empty string clears it)
    for modality, fmap in PROJECT_FIELD_MAP.items():
        prov_field = fmap["provider"]
        if prov_field in payload and payload[prov_field]:
            valid = {p["id"] for p in PROVIDER_CATALOG[modality]}
            if payload[prov_field] not in valid:
                raise HTTPException(400, f"Unknown {modality} provider: {payload[prov_field]}")

    payload["updated_at"] = now_iso()
    await db.projects.update_one({"id": project_id}, {"$set": payload})
    return await get_project_providers(project_id, user)  # noqa: E501  (reuse the merged view)


@api.post("/projects/{project_id}/providers/test")
async def test_project_provider(
    project_id: str,
    body: ProviderTestRequest,
    user: dict = Depends(current_user),
):
    proj = await _owned_project(project_id, user)
    effective = await _build_effective_providers(proj)
    cfg = effective.get(body.modality, {})
    flags = feature_flags()
    return {
        "project_id": project_id,
        "modality": body.modality,
        "provider": cfg.get("provider"),
        "model": cfg.get("model"),
        "source": cfg.get("source"),
        "ok": True,
        "mock_mode": True,
        "real_provider_enabled": flags.get(body.modality, False),
        "message": "Mock mode active — no real provider call was made.",
    }


@api.get("/projects/{project_id}/voice-resolution")
async def project_voice_resolution(project_id: str, user: dict = Depends(current_user)):
    """Resolve effective voice per character with priority:
    character override → project override → global default."""
    proj = await _owned_project(project_id, user)
    effective = await _build_effective_providers(proj)
    project_voice = {
        "provider": effective["voice"]["provider"],
        "model": effective["voice"]["model"],
        "source": effective["voice"]["source"],  # "global" | "global-fallback" | "project"
    }
    chars = await _ordered_characters(project_id)
    out_chars = []
    for c in chars:
        cv_provider = (c.get("voice_provider") or "").strip()
        cv_model = (c.get("voice_model") or "").strip()
        if cv_provider:
            voice = {
                "provider": cv_provider,
                "model": cv_model,
                "source": "character",
            }
        else:
            voice = {**project_voice}
            # When falling through from a character, label it as project- or global-derived
            voice["source"] = (
                "project"
                if project_voice["source"] == "project"
                else "global"
            )
        out_chars.append({
            "id": c["id"],
            "name": c.get("name"),
            "voice_style": c.get("voice_style"),
            "voice": voice,
        })
    return {
        "project_id": project_id,
        "mock_mode": True,
        "global_voice": _global_modality_view(await _load_provider_settings(), "voice"),
        "project_voice": project_voice,
        "characters": out_chars,
    }


@api.get("/projects/{project_id}/scene-costs")
async def project_scene_costs(
    project_id: str,
    wallet_credits: Optional[int] = None,
    high_cost_pct: Optional[int] = None,
    user: dict = Depends(current_user),
):
    """Per-scene credit estimate using the mock COSTS map.

    Optional query params (`wallet_credits`, `high_cost_pct`) let dev tools and
    tests override the env-configured defaults without mutating server state.

    Formula: image + (video_segment * max(1, len(segments))) + voice
    Missing keys degrade gracefully (treated as 0) and the response flags
    `estimate_unavailable=True` for that scene if any unit cost is missing.
    """
    proj = await _owned_project(project_id, user)

    image_cost = COSTS.get("image")
    seg_cost = COSTS.get("video_segment")
    voice_cost = COSTS.get("voice")
    cfg = studio_config()
    if wallet_credits is None:
        wallet_credits = cfg["wallet_credits"]
    if high_cost_pct is None:
        high_cost_pct = cfg["high_cost_scene_threshold_percent"]
    high_threshold = high_cost_pct

    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0}).sort("order", 1).to_list(500)
    out = []
    grand_total = 0
    for sc in scenes:
        seg_count = await db.segments.count_documents({"scene_id": sc["id"]})
        planned_segments = max(1, seg_count)
        missing = []
        if image_cost is None:
            missing.append("image")
        if seg_cost is None:
            missing.append("video_segment")
        if voice_cost is None:
            missing.append("voice")
        breakdown = {
            "image": (image_cost or 0),
            "video": (seg_cost or 0) * planned_segments,
            "voice": (voice_cost or 0),
        }
        total = breakdown["image"] + breakdown["video"] + breakdown["voice"]
        grand_total += total
        out.append({
            "scene_id": sc["id"],
            "title": sc.get("title"),
            "segments_count": seg_count,
            "planned_segments": planned_segments,
            "breakdown": breakdown,
            "total_credits": total,
            "estimate_unavailable": bool(missing),
            "missing_costs": missing,
        })

    # Wallet share + high-cost flagging — second pass so we know grand_total
    for row in out:
        share = (row["total_credits"] / grand_total * 100.0) if grand_total else 0.0
        row["share_pct"] = round(share, 1)
        row["high_cost"] = bool(grand_total) and share >= high_threshold

    wallet_pct_raw = (grand_total / wallet_credits * 100.0) if wallet_credits else 0.0
    wallet_pct = round(wallet_pct_raw, 1)
    return {
        "project_id": project_id,
        "mock_mode": True,
        "unit_costs": {"image": image_cost, "video_segment": seg_cost, "voice": voice_cost},
        "grand_total_credits": grand_total,
        "wallet_credits": wallet_credits,
        "wallet_pct": wallet_pct,
        "wallet_state": _wallet_state(wallet_pct_raw),
        "high_cost_scene_threshold_percent": high_threshold,
        "scenes": out,
    }




# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
@api.post("/projects")
async def create_project(body: ProjectCreate, user: dict = Depends(current_user)):
    doc = {
        "id": new_id(),
        "user_id": user["id"],
        "title": body.title,
        "idea": body.idea,
        "rewritten_story": "",
        "status": "draft",
        # Per-project provider override (off by default → uses global settings)
        "provider_override_enabled": False,
        "llm_provider": "",
        "llm_model": "",
        "image_provider": "",
        "image_model": "",
        "video_provider": "",
        "video_model": "",
        "voice_provider": "",
        "voice_model": "",
        "music_provider": "",
        "music_model": "",
        "export_provider": "",
        "export_mode": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.projects.insert_one(doc.copy())
    return doc


async def _project_cost_summary(project_id: str, cfg: dict) -> dict:
    image_cost = COSTS.get("image")
    seg_cost = COSTS.get("video_segment")
    voice_cost = COSTS.get("voice")
    wallet_credits = cfg["wallet_credits"]
    missing = image_cost is None or seg_cost is None or voice_cost is None

    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0, "id": 1}).to_list(500)
    total = 0
    for sc in scenes:
        seg_count = await db.segments.count_documents({"scene_id": sc["id"]})
        planned = max(1, seg_count)
        total += (image_cost or 0) + (seg_cost or 0) * planned + (voice_cost or 0)

    pct_raw = (total / wallet_credits * 100.0) if wallet_credits else 0.0
    return {
        "grand_total_credits": total,
        "wallet_credits": wallet_credits,
        "wallet_pct": round(pct_raw, 1),
        "wallet_state": _wallet_state(pct_raw),
        "estimate_unavailable": missing,
    }


async def _ordered_characters(project_id: str) -> List[dict]:
    """Return project characters sorted by order and backfill missing order.

    Legacy characters may not have `order`. For those, preserve the current
    natural chronology by created_at/id and assign sequential order values.
    """
    chars = await db.characters.find(
        {"project_id": project_id}, {"_id": 0}
    ).to_list(500)

    def _sort_key(c: dict):
        order = c.get("order")
        has_order = isinstance(order, int)
        return (
            0 if has_order else 1,
            order if has_order else 0,
            c.get("created_at", ""),
            c.get("id", ""),
        )

    chars = sorted(chars, key=_sort_key)
    needs_backfill = any(c.get("order") != i for i, c in enumerate(chars))
    if needs_backfill:
        for i, c in enumerate(chars):
            c["order"] = i
            await db.characters.update_one(
                {"id": c["id"], "project_id": project_id},
                {"$set": {"order": i}},
            )
    return chars


# Soft-delete helpers
SOFT_DELETE_TTL_HOURS = 24


def _active_project_filter(extra: Optional[dict] = None) -> dict:
    """Mongo filter that hides soft-deleted projects."""
    f: dict = {"$or": [{"deleted_at": {"$exists": False}}, {"deleted_at": None}]}
    if extra:
        return {"$and": [extra, f]}
    return f


@api.get("/projects")
async def list_projects(user: dict = Depends(current_user)):
    cfg = studio_config()
    projects = await db.projects.find(
        _active_project_filter({"user_id": user["id"]}), {"_id": 0}
    ).sort("created_at", -1).to_list(500)
    for p in projects:
        p["cost_summary"] = await _project_cost_summary(p["id"], cfg)
    return projects


@api.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    include_deleted: bool = False,
    user: dict = Depends(current_user),
):
    proj = await _owned_project(project_id, user, include_deleted=include_deleted)
    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0}).sort("order", 1).to_list(500)
    characters = await _ordered_characters(project_id)
    # attach segments to each scene
    for s in scenes:
        s["segments"] = await db.segments.find({"scene_id": s["id"]}, {"_id": 0}).sort("order", 1).to_list(50)
    return {"project": proj, "scenes": scenes, "characters": characters}


@api.put("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate, user: dict = Depends(current_user)):
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields to update")
    update["updated_at"] = now_iso()
    res = await db.projects.update_one(
        _active_project_filter({"id": project_id, "user_id": user["id"]}), {"$set": update}
    )
    if res.matched_count == 0:
        raise HTTPException(404, "Project not found")
    return await db.projects.find_one({"id": project_id, "user_id": user["id"]}, {"_id": 0})


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(current_user)):
    """Soft-delete a project.

    Sets deleted_at + delete_expires_at (now + 24h) and stashes the prior status
    in `previous_status` so restore can return the project to where it was.
    Child scenes/characters/segments are NOT touched yet — they're cleaned up by
    the purge endpoint after `delete_expires_at` passes.
    """
    proj = await db.projects.find_one({"id": project_id, "user_id": user["id"]}, {"_id": 0})
    if not proj:
        return {
            "ok": True,
            "soft_deleted": False,
            "project_id": project_id,
            "exists": False,
        }
    if proj.get("deleted_at"):
        # Already soft-deleted — idempotent.
        return {
            "ok": True,
            "soft_deleted": True,
            "project_id": project_id,
            "deleted_at": proj["deleted_at"],
            "delete_expires_at": proj.get("delete_expires_at"),
            "already_deleted": True,
        }
    now = datetime.now(timezone.utc)
    deleted_at = now.isoformat()
    expires_at = (now + timedelta(hours=SOFT_DELETE_TTL_HOURS)).isoformat()
    previous_status = proj.get("status") or "draft"
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "deleted_at": deleted_at,
            "deleted_by": user["id"],
            "delete_expires_at": expires_at,
            "previous_status": previous_status,
            "status": "deleted",
            "updated_at": deleted_at,
        }},
    )
    return {
        "ok": True,
        "soft_deleted": True,
        "project_id": project_id,
        "deleted_at": deleted_at,
        "delete_expires_at": expires_at,
        "previous_status": previous_status,
    }


@api.post("/projects/{project_id}/restore")
async def restore_project(project_id: str, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user, include_deleted=True)
    if not proj.get("deleted_at"):
        # Not soft-deleted — return as-is, no-op.
        return proj
    restore_status = proj.get("previous_status") or "draft"
    await db.projects.update_one(
        {"id": project_id},
        {
            "$set": {
                "status": restore_status,
                "updated_at": now_iso(),
            },
            "$unset": {
                "deleted_at": "",
                "deleted_by": "",
                "delete_expires_at": "",
                "previous_status": "",
            },
        },
    )
    return await db.projects.find_one({"id": project_id, "user_id": user["id"]}, {"_id": 0})


@api.post("/projects/{project_id}/rewrite")
async def rewrite_story(project_id: str, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user)
    # Provider execution guard — blocks real LLM call if a flag were on, runs mock otherwise.
    global_settings = await _load_provider_settings()
    mock_text = mock_rewrite_story(proj.get("idea", ""))
    # Real LLM rewrite (LLM modality only). Falls back to mock on failure.
    prompt = (
        "Rewrite the following idea into a tight 1–3 minute episode draft. "
        "Use vivid prose, a clear hook, escalating tension, and a memorable closing beat. "
        "Reply with only the episode text — no headings.\n\n"
        f"IDEA:\n{(proj.get('idea') or '').strip()}\n\n"
        f"BASELINE_DRAFT (rewrite or improve, do not copy verbatim):\n{mock_text}"
    )
    guard = await execute_llm(
        prompt=prompt,
        project=proj,
        global_settings=global_settings,
        estimated_credits=COSTS["rewrite"],
        project_id=project_id,
    )
    log.info("provider.rewrite mode=%s status=%s provider=%s/%s", guard.mode, guard.status, guard.provider_name, guard.model_name)
    rewritten = (guard.output.get("text") or "").strip() if guard.mode == "real" and guard.status == "success" else mock_text
    scores = compute_quality_scores(proj.get("idea", ""), rewritten)
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {
            "rewritten_story": rewritten,
            "status": "story_ready",
            "quality_scores": scores,
            "updated_at": now_iso(),
        }},
    )
    await log_generation("rewrite", project_id, COSTS["rewrite"], user_id=user["id"])
    return {
        "rewritten_story": rewritten,
        "cost": COSTS["rewrite"],
        "quality_scores": scores,
        "llm_mode": guard.mode,
        "llm_status": guard.status,
        "llm_duration_ms": int((guard.meta or {}).get("duration_ms") or 0),
    }


@api.post("/projects/{project_id}/split-scenes")
async def split_scenes(project_id: str, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user)
    # wipe existing scenes for clean split
    existing = await db.scenes.find({"project_id": project_id}, {"_id": 0, "id": 1}).to_list(500)
    for s in existing:
        await db.segments.delete_many({"scene_id": s["id"]})
    await db.scenes.delete_many({"project_id": project_id})

    new_scenes = []
    for idx, scene in enumerate(mock_split_scenes(proj.get("rewritten_story", ""))):
        scene["id"] = new_id()
        scene["project_id"] = project_id
        scene["created_at"] = now_iso()
        # Creative quality fields — deterministic mocks.
        scene["raw_visual_prompt"] = scene.get("visual_prompt", "")
        scene["enhanced_image_prompt"] = ""
        scene["enhanced_video_prompt"] = ""
        scene.update(compute_scene_tension(scene, idx))
        new_scenes.append(scene)
    if new_scenes:
        await db.scenes.insert_many([s.copy() for s in new_scenes])
    await db.projects.update_one({"id": project_id}, {"$set": {"status": "scenes_ready", "updated_at": now_iso()}})
    await log_generation("split_scenes", project_id, COSTS["split_scenes"], user_id=user["id"])
    return {"scenes": new_scenes}


# ---------------------------------------------------------------------------
# Creative Quality Engine (mock-only)
# ---------------------------------------------------------------------------
class ImproveStoryRequest(BaseModel):
    kind: Literal["suspenseful", "emotional", "romantic", "darker", "cliffhanger", "realistic-dialogue", "cinematic"]


class EnhanceSceneRequest(BaseModel):
    kind: Literal["image-prompt", "video-prompt", "scene-drama", "dialogue"]


@api.post("/projects/{project_id}/quality-score")
async def recompute_quality_score(project_id: str, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user)
    scores = compute_quality_scores(proj.get("idea", ""), proj.get("rewritten_story", ""))
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"quality_scores": scores, "updated_at": now_iso()}},
    )
    return {"quality_scores": scores}


@api.post("/projects/{project_id}/improve-story")
async def improve_story(project_id: str, body: ImproveStoryRequest, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user)
    if not (proj.get("rewritten_story") or "").strip():
        raise HTTPException(400, "Story is empty — rewrite it first.")
    mock_story, note = apply_improvement(proj["rewritten_story"], body.kind)
    # Real LLM improvement (LLM modality only). Falls back to mock on failure.
    global_settings = await _load_provider_settings()
    prompt = (
        f"Rewrite the following 1–3 minute episode so it becomes notably MORE {body.kind.replace('-', ' ')}.\n"
        "Preserve the overall arc and any character names. Reply with only the rewritten episode — no headings.\n\n"
        f"ORIGINAL:\n{proj['rewritten_story']}\n\n"
        f"BASELINE_REWRITE (you may improve on this):\n{mock_story}"
    )
    guard = await execute_llm(
        prompt=prompt,
        project=proj,
        global_settings=global_settings,
        estimated_credits=COSTS["rewrite"],
        project_id=project_id,
    )
    log.info("provider.improve mode=%s status=%s kind=%s", guard.mode, guard.status, body.kind)
    new_story = (guard.output.get("text") or "").strip() if guard.mode == "real" and guard.status == "success" else mock_story
    scores = compute_quality_scores(proj.get("idea", ""), new_story)
    history_entry = {
        "id": new_id(),
        "kind": body.kind,
        "note": note,
        "at": now_iso(),
        "llm_mode": guard.mode,
    }
    await db.projects.update_one(
        {"id": project_id},
        {
            "$set": {
                "rewritten_story": new_story,
                "quality_scores": scores,
                "updated_at": now_iso(),
            },
            "$push": {"improvement_history": history_entry},
        },
    )
    return {
        "rewritten_story": new_story,
        "quality_scores": scores,
        "improvement": history_entry,
        "llm_mode": guard.mode,
        "llm_status": guard.status,
        "llm_duration_ms": int((guard.meta or {}).get("duration_ms") or 0),
    }


@api.post("/scenes/{scene_id}/enhance-prompt")
async def enhance_scene_prompt(scene_id: str, body: EnhanceSceneRequest, user: dict = Depends(current_user)):
    scene = await _owned_scene(scene_id, user)
    global_settings = await _load_provider_settings()
    proj = await db.projects.find_one({"id": scene["project_id"]}, {"_id": 0})

    update: dict = {}
    llm_mode = "mock"
    llm_status = "success"
    llm_duration_ms = 0
    if body.kind == "image-prompt":
        update["raw_visual_prompt"] = scene.get("visual_prompt") or scene.get("raw_visual_prompt") or ""
        baseline = enhance_image_prompt(update["raw_visual_prompt"], scene)
        prompt = (
            "Rewrite this scene's image-generation prompt to maximize: realism, lighting, "
            "character consistency, and camera framing. Reply with only the rewritten prompt.\n\n"
            f"RAW:\n{update['raw_visual_prompt']}\n\nBASELINE_ENHANCEMENT:\n{baseline}"
        )
        guard = await execute_llm(prompt=prompt, project=proj, global_settings=global_settings,
                                  project_id=scene["project_id"], scene_id=scene_id)
        llm_mode = guard.mode
        llm_status = guard.status
        llm_duration_ms = int((guard.meta or {}).get("duration_ms") or 0)
        update["enhanced_image_prompt"] = (
            guard.output.get("text", "").strip()
            if guard.mode == "real" and guard.status == "success" and guard.output.get("text")
            else baseline
        )
    elif body.kind == "video-prompt":
        update["raw_visual_prompt"] = scene.get("visual_prompt") or scene.get("raw_visual_prompt") or ""
        baseline = enhance_video_prompt(update["raw_visual_prompt"], scene)
        prompt = (
            "Rewrite this scene's video-generation prompt to maximize: motion, continuity, "
            "emotion, and camera movement. Reply with only the rewritten prompt.\n\n"
            f"RAW:\n{update['raw_visual_prompt']}\n\nBASELINE_ENHANCEMENT:\n{baseline}"
        )
        guard = await execute_llm(prompt=prompt, project=proj, global_settings=global_settings,
                                  project_id=scene["project_id"], scene_id=scene_id)
        llm_mode = guard.mode
        llm_status = guard.status
        llm_duration_ms = int((guard.meta or {}).get("duration_ms") or 0)
        update["enhanced_video_prompt"] = (
            guard.output.get("text", "").strip()
            if guard.mode == "real" and guard.status == "success" and guard.output.get("text")
            else baseline
        )
    elif body.kind == "scene-drama":
        baseline = improve_scene_drama(scene)
        prompt = (
            "Rewrite this scene's dialogue to be more dramatic. Two short, charged lines. "
            "Reply with only the dialogue.\n\n"
            f"CURRENT:\n{scene.get('dialogue') or ''}"
        )
        guard = await execute_llm(prompt=prompt, project=proj, global_settings=global_settings,
                                  project_id=scene["project_id"], scene_id=scene_id)
        llm_mode = guard.mode
        llm_status = guard.status
        llm_duration_ms = int((guard.meta or {}).get("duration_ms") or 0)
        update.update(baseline)
        if guard.mode == "real" and guard.status == "success" and guard.output.get("text"):
            update["dialogue"] = guard.output["text"].strip()
    elif body.kind == "dialogue":
        baseline = improve_scene_dialogue(scene)
        prompt = (
            "Rewrite this dialogue to feel more realistic — contractions, interruptions, "
            "and natural rhythm. Reply with only the dialogue.\n\n"
            f"CURRENT:\n{scene.get('dialogue') or ''}"
        )
        guard = await execute_llm(prompt=prompt, project=proj, global_settings=global_settings,
                                  project_id=scene["project_id"], scene_id=scene_id)
        llm_mode = guard.mode
        llm_status = guard.status
        llm_duration_ms = int((guard.meta or {}).get("duration_ms") or 0)
        update.update(baseline)
        if guard.mode == "real" and guard.status == "success" and guard.output.get("text"):
            update["dialogue"] = guard.output["text"].strip()
    update["updated_at"] = now_iso()
    await db.scenes.update_one({"id": scene_id}, {"$set": update})
    out = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
    return {
        "kind": body.kind,
        "scene": out,
        "image_enhancement_hint": IMAGE_ENHANCEMENT_HINT,
        "video_enhancement_hint": VIDEO_ENHANCEMENT_HINT,
        "llm_mode": llm_mode,
        "llm_status": llm_status,
        "llm_duration_ms": llm_duration_ms,
    }


@api.get("/creative/enhancement-hints")
async def creative_enhancement_hints():
    """Static hints shown on the Images / Video Segments tabs."""
    return {
        "image_traits": list(IMAGE_PROMPT_TRAITS),
        "video_traits": list(VIDEO_PROMPT_TRAITS),
        "image_hint": IMAGE_ENHANCEMENT_HINT,
        "video_hint": VIDEO_ENHANCEMENT_HINT,
        "improve_kinds": list(IMPROVE_KINDS),
        "enhance_kinds": list(ENHANCE_KINDS),
        "quality_keys": list(QUALITY_KEYS),
    }


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------
@api.post("/projects/{project_id}/characters")
async def create_character(project_id: str, body: CharacterCreate, user: dict = Depends(current_user)):
    await _owned_project(project_id, user)
    await _ordered_characters(project_id)
    order = await db.characters.count_documents({"project_id": project_id})
    doc = {
        "id": new_id(),
        "project_id": project_id,
        "order": order,
        "name": body.name,
        "description": body.description,
        "voice_style": body.voice_style,
        "voice_provider": (body.voice_provider or "").strip(),
        "voice_model": (body.voice_model or "").strip(),
        "reference_image_url": body.reference_image_url or MOCK_CHARACTER_IMAGE,
        "created_at": now_iso(),
    }
    await db.characters.insert_one(doc.copy())
    return doc


@api.put("/characters/{character_id}")
async def update_character(character_id: str, body: CharacterUpdate, user: dict = Depends(current_user)):
    await _owned_character(character_id, user)
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields")
    # Validate voice_provider against catalog if it's being set to a non-empty value
    if "voice_provider" in update and update["voice_provider"]:
        valid = {p["id"] for p in PROVIDER_CATALOG["voice"]}
        if update["voice_provider"] not in valid:
            raise HTTPException(400, f"Unknown voice provider: {update['voice_provider']}")
    res = await db.characters.update_one({"id": character_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Character not found")
    return await db.characters.find_one({"id": character_id}, {"_id": 0})


@api.delete("/characters/{character_id}")
async def delete_character(character_id: str, user: dict = Depends(current_user)):
    char = await _owned_character(character_id, user)
    await db.characters.delete_one({"id": character_id})
    if char:
        await _ordered_characters(char["project_id"])
    return {"ok": True}


@api.put("/projects/{project_id}/characters/reorder")
async def reorder_characters(
    project_id: str,
    body: ReorderCharactersBody,
    user: dict = Depends(current_user),
):
    await _owned_project(project_id, user)
    existing = await _ordered_characters(project_id)
    existing_ids = {c["id"] for c in existing}
    incoming = list(body.character_ids)
    if len(incoming) != len(existing_ids) or set(incoming) != existing_ids:
        raise HTTPException(
            400,
            "character_ids must include every character of this project exactly once",
        )
    for i, cid in enumerate(incoming):
        await db.characters.update_one(
            {"id": cid, "project_id": project_id},
            {"$set": {"order": i}},
        )
    return {"characters": await _ordered_characters(project_id)}


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------
@api.post("/projects/{project_id}/scenes")
async def create_scene(project_id: str, body: SceneCreate, user: dict = Depends(current_user)):
    await _owned_project(project_id, user)
    count = await db.scenes.count_documents({"project_id": project_id})
    doc = {
        "id": new_id(),
        "project_id": project_id,
        "order": count,
        "title": body.title,
        "duration": body.duration,
        "location": body.location,
        "characters": body.characters,
        "visual_prompt": body.visual_prompt,
        "dialogue": body.dialogue,
        "music_mood": body.music_mood,
        "camera_direction": body.camera_direction,
        "voice": body.voice,
        "image_url": None,
        "status": "draft",
        "created_at": now_iso(),
    }
    await db.scenes.insert_one(doc.copy())
    return doc


@api.put("/scenes/{scene_id}")
async def update_scene(scene_id: str, body: SceneUpdate, user: dict = Depends(current_user)):
    await _owned_scene(scene_id, user)
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields")
    res = await db.scenes.update_one({"id": scene_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Scene not found")
    return await db.scenes.find_one({"id": scene_id}, {"_id": 0})


@api.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str, user: dict = Depends(current_user)):
    await _owned_scene(scene_id, user)
    await db.segments.delete_many({"scene_id": scene_id})
    await db.scenes.delete_one({"id": scene_id})
    return {"ok": True}


@api.post("/scenes/{scene_id}/generate-image")
async def generate_image(scene_id: str, user: dict = Depends(current_user)):
    scene = await _owned_scene(scene_id, user)
    # Provider execution guard — verifies flag + key before any real call.
    proj = await db.projects.find_one({"id": scene["project_id"]}, {"_id": 0})
    global_settings = await _load_provider_settings()
    guard = await execute_provider(
        modality="image",
        project=proj,
        global_settings=global_settings,
        estimated_credits=COSTS["image"],
        project_id=scene["project_id"],
        scene_id=scene_id,
    )
    log.info("provider.image mode=%s status=%s provider=%s/%s", guard.mode, guard.status, guard.provider_name, guard.model_name)
    # 5% mock failure to power admin failed jobs widget
    if random.random() < 0.05:
        await log_generation("image", scene["project_id"], 0, status="failed", error="mock provider timeout", user_id=user["id"])
        raise HTTPException(503, "Mock image provider timed out")
    url = random.choice(MOCK_SCENE_IMAGES)
    await db.scenes.update_one({"id": scene_id}, {"$set": {"image_url": url, "status": "image_ready"}})
    await log_generation("image", scene["project_id"], COSTS["image"], user_id=user["id"])
    return {"image_url": url, "cost": COSTS["image"]}


async def _create_scene_segment(
    scene_id: str,
    *,
    expand_mode: str,
    continuity_prompt: Optional[str],
    user: dict,
) -> dict:
    """Create a new 5s mock video segment for a scene.

    expand_mode = "initial" → first segment (parent_segment_id = None, start_second = 0)
    expand_mode = "expand"  → continues from latest segment under the same scene.
    """
    scene = await _owned_scene(scene_id, user)
    # Provider execution guard for video generation.
    proj = await db.projects.find_one({"id": scene["project_id"]}, {"_id": 0})
    global_settings = await _load_provider_settings()
    guard = await execute_provider(
        modality="video",
        project=proj,
        global_settings=global_settings,
        estimated_credits=COSTS["video_segment"],
        project_id=scene["project_id"],
        scene_id=scene_id,
    )
    log.info("provider.video mode=%s status=%s provider=%s/%s", guard.mode, guard.status, guard.provider_name, guard.model_name)
    if random.random() < 0.05:
        await log_generation("video_segment", scene["project_id"], 0, status="failed", error="mock render failed", user_id=user["id"])
        raise HTTPException(503, "Mock video render failed")

    siblings = await db.segments.find({"scene_id": scene_id}, {"_id": 0}).sort("order", 1).to_list(200)
    order = len(siblings)
    parent_segment_id: Optional[str] = None
    start_second = 0
    if siblings:
        last = siblings[-1]
        start_second = int(last.get("start_second", 0)) + int(last.get("duration", 5))
        if expand_mode == "expand":
            parent_segment_id = last["id"]

    duration = 5
    doc = {
        "id": new_id(),
        "scene_id": scene_id,
        "project_id": scene["project_id"],
        "order": order,
        "parent_segment_id": parent_segment_id,
        "start_second": start_second,
        "duration": duration,
        "expand_mode": expand_mode,
        "continuity_prompt": (continuity_prompt or scene.get("visual_prompt") or "").strip(),
        "video_url": random.choice(MOCK_VIDEO_URLS),
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.segments.insert_one(doc.copy())
    await db.scenes.update_one({"id": scene_id}, {"$set": {"status": "video_ready"}})
    await log_generation("video_segment", scene["project_id"], COSTS["video_segment"], user_id=user["id"])
    return doc


@api.post("/scenes/{scene_id}/segments")
async def create_segment(
    scene_id: str,
    body: Optional[SegmentCreate] = None,
    user: dict = Depends(current_user),
):
    siblings_count = await db.segments.count_documents({"scene_id": scene_id})
    mode = "initial" if siblings_count == 0 else "expand"
    return await _create_scene_segment(
        scene_id,
        expand_mode=mode,
        continuity_prompt=body.continuity_prompt if body else None,
        user=user,
    )


@api.post("/scenes/{scene_id}/expand")
async def expand_segment(
    scene_id: str,
    body: Optional[SegmentCreate] = None,
    user: dict = Depends(current_user),
):
    """Always treated as expansion of the latest segment ("+5s next")."""
    return await _create_scene_segment(
        scene_id,
        expand_mode="expand",
        continuity_prompt=body.continuity_prompt if body else None,
        user=user,
    )


@api.put("/segments/{segment_id}/status")
async def set_segment_status(segment_id: str, body: SegmentStatus, user: dict = Depends(current_user)):
    await _owned_segment(segment_id, user)
    res = await db.segments.update_one({"id": segment_id}, {"$set": {"status": body.status}})
    if res.matched_count == 0:
        raise HTTPException(404, "Segment not found")
    return await db.segments.find_one({"id": segment_id}, {"_id": 0})


@api.put("/segments/{segment_id}")
async def update_segment(segment_id: str, body: SegmentUpdate, user: dict = Depends(current_user)):
    """Generic partial update for a segment. Coexists with the dedicated
    /status route — both write to the same fields."""
    await _owned_segment(segment_id, user)
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields to update")
    if "continuity_prompt" in update and update["continuity_prompt"] is not None:
        update["continuity_prompt"] = update["continuity_prompt"].strip()
    if "duration" in update and update["duration"] is not None:
        if update["duration"] <= 0:
            raise HTTPException(400, "duration must be > 0")
    res = await db.segments.update_one({"id": segment_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Segment not found")
    return await db.segments.find_one({"id": segment_id}, {"_id": 0})


@api.put("/projects/{project_id}/scenes/reorder")
async def reorder_scenes(project_id: str, body: ReorderScenesBody, user: dict = Depends(current_user)):
    await _owned_project(project_id, user)
    existing = await db.scenes.find(
        {"project_id": project_id}, {"_id": 0, "id": 1}
    ).to_list(500)
    existing_ids = {s["id"] for s in existing}
    incoming = list(body.scene_ids)
    if len(incoming) != len(existing_ids) or set(incoming) != existing_ids:
        raise HTTPException(400, "scene_ids must include every scene of this project exactly once")
    for i, sid in enumerate(incoming):
        await db.scenes.update_one({"id": sid, "project_id": project_id}, {"$set": {"order": i}})
    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0}).sort("order", 1).to_list(500)
    return {"scenes": scenes}


@api.put("/scenes/{scene_id}/segments/reorder")
async def reorder_segments(scene_id: str, body: ReorderSegmentsBody, user: dict = Depends(current_user)):
    await _owned_scene(scene_id, user)
    existing = await db.segments.find(
        {"scene_id": scene_id}, {"_id": 0}
    ).to_list(200)
    existing_ids = {s["id"] for s in existing}
    incoming = list(body.segment_ids)
    if len(incoming) != len(existing_ids) or set(incoming) != existing_ids:
        raise HTTPException(400, "segment_ids must include every segment of this scene exactly once")

    by_id = {s["id"]: s for s in existing}
    start = 0
    for i, sid in enumerate(incoming):
        seg = by_id[sid]
        dur = int(seg.get("duration") or 5)
        await db.segments.update_one(
            {"id": sid, "scene_id": scene_id},
            {"$set": {"order": i, "start_second": start}},
        )
        start += dur
    segments = await db.segments.find(
        {"scene_id": scene_id}, {"_id": 0}
    ).sort("order", 1).to_list(200)
    return {"segments": segments}


@api.post("/segments/{segment_id}/regenerate")
async def regenerate_segment(segment_id: str, user: dict = Depends(current_user)):
    seg = await _owned_segment(segment_id, user)
    if random.random() < 0.05:
        await log_generation("video_segment", seg.get("project_id"), 0, status="failed", error="mock regen failed", user_id=user["id"])
        raise HTTPException(503, "Mock video regen failed")
    new_url = random.choice(MOCK_VIDEO_URLS)
    await db.segments.update_one(
        {"id": segment_id},
        {"$set": {"video_url": new_url, "status": "pending"}},
    )
    await log_generation("video_segment", seg.get("project_id"), COSTS["video_segment"], user_id=user["id"])
    return await db.segments.find_one({"id": segment_id}, {"_id": 0})


@api.post("/scenes/{scene_id}/reduce-to-draft")
async def reduce_scene_to_draft(scene_id: str, user: dict = Depends(current_user)):
    """Drop the scene's planned segments to 1 by deleting all video segments
    except the earliest one. Idempotent: a scene with 0 or 1 segment is a no-op.
    Returns the saved credits and the new segment list."""
    scene = await _owned_scene(scene_id, user)

    segs = await db.segments.find(
        {"scene_id": scene_id}, {"_id": 0}
    ).sort("order", 1).to_list(200)
    seg_cost = COSTS.get("video_segment", 0) or 0
    deleted_count = 0
    if len(segs) > 1:
        keep = segs[0]
        to_delete = [s["id"] for s in segs[1:]]
        await db.segments.delete_many({"id": {"$in": to_delete}})
        deleted_count = len(to_delete)
        # parent_segment_id of any orphan was the deleted ones — but we deleted them all.
        # The kept segment is unaffected.
        scene_status = "video_ready" if keep else "draft"
        await db.scenes.update_one({"id": scene_id}, {"$set": {"status": scene_status}})

    saved_credits = deleted_count * seg_cost
    remaining = await db.segments.find(
        {"scene_id": scene_id}, {"_id": 0}
    ).sort("order", 1).to_list(200)
    return {
        "scene_id": scene_id,
        "deleted_segments": deleted_count,
        "saved_credits": saved_credits,
        "segments": remaining,
        "mock_mode": True,
    }


@api.delete("/segments/{segment_id}")
async def delete_segment(segment_id: str, user: dict = Depends(current_user)):
    await _owned_segment(segment_id, user)
    await db.segments.delete_one({"id": segment_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Cost estimate
# ---------------------------------------------------------------------------
@api.post("/cost-estimate")
async def cost_estimate(body: CostEstimateRequest):
    total = 0
    breakdown = {}
    for op, qty in body.operations.items():
        unit = COSTS.get(op, 0)
        line = unit * int(qty or 0)
        breakdown[op] = {"qty": int(qty or 0), "unit": unit, "line": line}
        total += line
    return {"total_credits": total, "breakdown": breakdown}


@api.get("/projects/{project_id}/cost-estimate")
async def project_cost_estimate(project_id: str, user: dict = Depends(current_user)):
    await _owned_project(project_id, user)
    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0}).to_list(500)
    n_scenes = len(scenes)
    ops = {
        "rewrite": 1 if n_scenes == 0 else 0,
        "split_scenes": 1 if n_scenes == 0 else 0,
        "image": n_scenes,
        "video_segment": n_scenes,  # 1 per scene baseline
        "voice": n_scenes,
    }
    total = sum(COSTS.get(k, 0) * v for k, v in ops.items())
    return {"total_credits": total, "operations": ops, "unit_costs": COSTS}


# ---------------------------------------------------------------------------
# Final export (mock stitch)
# ---------------------------------------------------------------------------
@api.get("/projects/{project_id}/export")
async def export_project(project_id: str, user: dict = Depends(current_user)):
    proj = await _owned_project(project_id, user)
    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0}).sort("order", 1).to_list(500)
    approved = []
    total_seconds = 0
    for s in scenes:
        segs = await db.segments.find({"scene_id": s["id"], "status": "approved"}, {"_id": 0}).sort("order", 1).to_list(50)
        for seg in segs:
            approved.append({
                "segment_id": seg["id"],
                "scene_id": s["id"],
                "scene_title": s["title"],
                "video_url": seg["video_url"],
                "duration": seg["duration"],
            })
            total_seconds += seg.get("duration", 5)
    final_url = MOCK_VIDEO_URLS[0]  # mock stitched output
    return {
        "project": proj,
        "approved_segments": approved,
        "total_duration_seconds": total_seconds,
        "final_video_url": final_url if approved else None,
        "ready": len(approved) > 0,
    }


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------
@api.get("/admin/stats")
async def admin_stats():
    users = await db.users.count_documents({})
    projects = await db.projects.count_documents({})
    gens = await db.generations.count_documents({})
    failed = await db.generations.count_documents({"status": "failed"})
    cost_cursor = db.generations.aggregate([
        {"$group": {"_id": None, "credits": {"$sum": "$cost_credits"}}}
    ])
    cost_credits = 0
    async for row in cost_cursor:
        cost_credits = row.get("credits", 0)
    # internal cost estimate: $0.01 per credit
    internal_cost_usd = round(cost_credits * 0.01, 2)
    return {
        "users": users,
        "projects": projects,
        "generations": gens,
        "failed_jobs": failed,
        "credits_used": cost_credits,
        "internal_cost_usd": internal_cost_usd,
    }


@api.get("/admin/users")
async def admin_users():
    return await db.users.find({}, {"_id": 0}).to_list(500)


@api.get("/admin/projects")
async def admin_projects():
    return await db.projects.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)


@api.get("/admin/generations")
async def admin_generations():
    return await db.generations.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.get("/admin/failed-jobs")
async def admin_failed_jobs():
    return await db.generations.find({"status": "failed"}, {"_id": 0}).sort("created_at", -1).to_list(200)


async def _purge_expired_projects_now() -> dict:
    """Permanently remove soft-deleted projects whose delete_expires_at has passed.

    Shared by `POST /api/admin/purge-deleted-projects` (manual) and the
    background scheduler. Cascades to scenes/characters/segments and drops
    `provider_activity` rows scoped to those project_ids.
    Returns the purge-count dict.
    """
    now_iso_str = datetime.now(timezone.utc).isoformat()
    expired = await db.projects.find(
        {"deleted_at": {"$ne": None}, "delete_expires_at": {"$lte": now_iso_str}},
        {"_id": 0, "id": 1},
    ).to_list(1000)
    project_ids = [p["id"] for p in expired]
    if not project_ids:
        return {"projects": 0, "scenes": 0, "characters": 0, "segments": 0}
    proj_res = await db.projects.delete_many({"id": {"$in": project_ids}})
    scenes_res = await db.scenes.delete_many({"project_id": {"$in": project_ids}})
    chars_res = await db.characters.delete_many({"project_id": {"$in": project_ids}})
    segs_res = await db.segments.delete_many({"project_id": {"$in": project_ids}})
    await db.provider_activity.delete_many({"project_id": {"$in": project_ids}})
    return {
        "projects": proj_res.deleted_count,
        "scenes": scenes_res.deleted_count,
        "characters": chars_res.deleted_count,
        "segments": segs_res.deleted_count,
    }


@api.post("/admin/purge-deleted-projects")
async def admin_purge_deleted_projects():
    """Permanently remove soft-deleted projects whose delete_expires_at has passed."""
    purged = await _purge_expired_projects_now()
    return {"ok": True, "purged": purged}


@api.get("/admin/deleted-projects")
async def admin_deleted_projects():
    """Soft-deleted projects still inside the restore window (delete_expires_at > now).

    Returns child counts per project so the admin panel can show them at-a-glance.
    """
    now_iso_str = datetime.now(timezone.utc).isoformat()
    rows = await db.projects.find(
        {"deleted_at": {"$ne": None}, "delete_expires_at": {"$gt": now_iso_str}},
        {"_id": 0},
    ).sort("deleted_at", -1).to_list(500)
    items = []
    for p in rows:
        pid = p["id"]
        scenes_count = await db.scenes.count_documents({"project_id": pid})
        chars_count = await db.characters.count_documents({"project_id": pid})
        segs_count = await db.segments.count_documents({"project_id": pid})
        items.append({
            "id": pid,
            "title": p.get("title", ""),
            "deleted_at": p.get("deleted_at"),
            "delete_expires_at": p.get("delete_expires_at"),
            "previous_status": p.get("previous_status"),
            "scenes_count": scenes_count,
            "characters_count": chars_count,
            "segments_count": segs_count,
        })
    return {"count": len(items), "items": items}


@api.get("/admin/provider-activity")
async def admin_provider_activity(limit: int = 50):
    """Latest provider execution records (safe metadata only, no secrets)."""
    capped = max(1, min(int(limit or 50), 200))
    rows = await db.provider_activity.find({}, {"_id": 0}).sort("created_at", -1).to_list(capped)
    return {"limit": capped, "count": len(rows), "items": rows}


@api.get("/admin/provider-health")
async def admin_provider_health(window_minutes: int = 60):
    """Aggregated mock-mode health pulse for each modality over the last window.

    Status rules:
      no_activity → no calls in the window
      failing    → failure rate ≥ 25%
      slow       → avg duration > 3000 ms
      healthy    → otherwise
    """
    window = max(1, min(int(window_minutes or 60), 1440))
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(minutes=window)).isoformat()
    rows = await db.provider_activity.find(
        {"created_at": {"$gte": cutoff_iso}},
        {"_id": 0, "modality": 1, "status": 1, "duration_ms": 1},
    ).to_list(10000)

    out = []
    for modality in PROVIDER_LAYER_MODALITIES:
        bucket = [r for r in rows if r.get("modality") == modality]
        total = len(bucket)
        if total == 0:
            out.append({
                "modality": modality,
                "total_calls": 0,
                "success_calls": 0,
                "failed_calls": 0,
                "avg_duration_ms": 0,
                "status": "no_activity",
            })
            continue
        failed = sum(1 for r in bucket if r.get("status") == "failed")
        success = sum(1 for r in bucket if r.get("status") == "success")
        durations = [int(r.get("duration_ms") or 0) for r in bucket]
        avg_ms = round(sum(durations) / len(durations)) if durations else 0
        failure_rate = failed / total
        if failure_rate >= 0.25:
            status = "failing"
        elif avg_ms > 3000:
            status = "slow"
        else:
            status = "healthy"
        out.append({
            "modality": modality,
            "total_calls": total,
            "success_calls": success,
            "failed_calls": failed,
            "avg_duration_ms": avg_ms,
            "status": status,
        })
    return {"window_minutes": window, "modalities": out}


# ---------------------------------------------------------------------------
# Mount
# ---------------------------------------------------------------------------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    await ensure_default_user()
    await _backfill_creative_quality()
    # Background purge of expired soft-deleted projects.
    await _start_purge_scheduler()
    log.info("AI Episode Studio backend ready")


_purge_task: Optional[asyncio.Task] = None


async def _start_purge_scheduler() -> None:
    """Spawn the periodic purge loop. Runs an initial purge on boot, then
    every `DELETED_PROJECT_PURGE_INTERVAL_MINUTES` minutes (default 60).
    Set the interval to 0 to disable the scheduler entirely (tests can do this)."""
    global _purge_task
    interval_min = _int_env("DELETED_PROJECT_PURGE_INTERVAL_MINUTES", 60)
    if interval_min <= 0:
        log.info("Purge scheduler disabled (interval=%s)", interval_min)
        return
    if _purge_task is not None and not _purge_task.done():
        return  # already running

    async def _loop():
        # Initial purge on boot — runs once before the wait loop.
        try:
            purged = await _purge_expired_projects_now()
            if any(v > 0 for v in purged.values()):
                log.info("Startup purge: %s", purged)
        except Exception as exc:  # noqa: BLE001
            log.warning("Startup purge failed: %s", exc)
        while True:
            try:
                await asyncio.sleep(interval_min * 60)
                purged = await _purge_expired_projects_now()
                if any(v > 0 for v in purged.values()):
                    log.info("Scheduled purge: %s", purged)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("Scheduled purge failed: %s", exc)

    _purge_task = asyncio.create_task(_loop())


async def _backfill_creative_quality():
    """One-shot startup backfill so legacy projects/scenes acquire the
    Creative Quality fields without requiring users to re-run rewrite + split.

    Safe to run on every startup: skips documents that already have the fields.
    """
    # Projects missing quality_scores but with a rewritten_story → compute scores.
    cursor = db.projects.find(
        {"$or": [{"quality_scores": {"$exists": False}}, {"quality_scores": None}]},
        {"_id": 0, "id": 1, "idea": 1, "rewritten_story": 1},
    )
    proj_count = 0
    async for p in cursor:
        if not (p.get("rewritten_story") or "").strip():
            continue
        scores = compute_quality_scores(p.get("idea", ""), p["rewritten_story"])
        await db.projects.update_one(
            {"id": p["id"]}, {"$set": {"quality_scores": scores}}
        )
        proj_count += 1

    # Scenes missing tension fields → compute.
    scene_cursor = db.scenes.find(
        {"$or": [{"tension_level": {"$exists": False}}, {"tension_level": None}]},
        {"_id": 0},
    )
    scene_count = 0
    async for sc in scene_cursor:
        update = {
            "raw_visual_prompt": sc.get("raw_visual_prompt") or sc.get("visual_prompt", ""),
            "enhanced_image_prompt": sc.get("enhanced_image_prompt", ""),
            "enhanced_video_prompt": sc.get("enhanced_video_prompt", ""),
        }
        update.update(compute_scene_tension(sc))
        await db.scenes.update_one({"id": sc["id"]}, {"$set": update})
        scene_count += 1

    if proj_count or scene_count:
        log.info(
            "Creative-quality backfill: %d projects scored, %d scenes tensioned",
            proj_count, scene_count,
        )


@app.on_event("shutdown")
async def shutdown_event():
    global _purge_task
    if _purge_task is not None and not _purge_task.done():
        _purge_task.cancel()
        try:
            await _purge_task
        except (asyncio.CancelledError, Exception):
            pass
        _purge_task = None
    client.close()
