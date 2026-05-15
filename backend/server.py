"""AI Episode Studio – MVP backend (mock generation, no external APIs)."""
from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import random
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import uuid
from datetime import datetime, timezone


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="AI Episode Studio API")
api = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("episode-studio")

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

COSTS = {"rewrite": 3, "split_scenes": 4, "image": 2, "video_segment": 5, "voice": 1}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


async def log_generation(gen_type: str, project_id: Optional[str], cost: int,
                         status: str = "success", error: Optional[str] = None) -> None:
    await db.generations.insert_one({
        "id": new_id(),
        "user_id": DEFAULT_USER_ID,
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


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    title: str
    idea: str = ""


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    idea: Optional[str] = None
    rewritten_story: Optional[str] = None
    status: Optional[str] = None


class CharacterCreate(BaseModel):
    name: str
    description: str = ""
    voice_style: str = "Narrator-Warm"
    reference_image_url: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    voice_style: Optional[str] = None
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


@api.get("/me")
async def me():
    await ensure_default_user()
    return await db.users.find_one({"id": DEFAULT_USER_ID}, {"_id": 0})


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
@api.post("/projects")
async def create_project(body: ProjectCreate):
    await ensure_default_user()
    doc = {
        "id": new_id(),
        "user_id": DEFAULT_USER_ID,
        "title": body.title,
        "idea": body.idea,
        "rewritten_story": "",
        "status": "draft",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.projects.insert_one(doc.copy())
    return doc


@api.get("/projects")
async def list_projects():
    cursor = db.projects.find({}, {"_id": 0}).sort("created_at", -1)
    return await cursor.to_list(500)


@api.get("/projects/{project_id}")
async def get_project(project_id: str):
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    scenes = await db.scenes.find({"project_id": project_id}, {"_id": 0}).sort("order", 1).to_list(500)
    characters = await db.characters.find({"project_id": project_id}, {"_id": 0}).to_list(500)
    # attach segments to each scene
    for s in scenes:
        s["segments"] = await db.segments.find({"scene_id": s["id"]}, {"_id": 0}).sort("order", 1).to_list(50)
    return {"project": proj, "scenes": scenes, "characters": characters}


@api.put("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectUpdate):
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields to update")
    update["updated_at"] = now_iso()
    res = await db.projects.update_one({"id": project_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Project not found")
    return await db.projects.find_one({"id": project_id}, {"_id": 0})


@api.delete("/projects/{project_id}")
async def delete_project(project_id: str):
    await db.projects.delete_one({"id": project_id})
    await db.scenes.delete_many({"project_id": project_id})
    await db.characters.delete_many({"project_id": project_id})
    # delete segments belonging to deleted scenes (already deleted scenes; cascade by project tag isn't stored on segments)
    # we filter via remaining scene ids
    return {"ok": True}


@api.post("/projects/{project_id}/rewrite")
async def rewrite_story(project_id: str):
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    rewritten = mock_rewrite_story(proj.get("idea", ""))
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"rewritten_story": rewritten, "status": "story_ready", "updated_at": now_iso()}},
    )
    await log_generation("rewrite", project_id, COSTS["rewrite"])
    return {"rewritten_story": rewritten, "cost": COSTS["rewrite"]}


@api.post("/projects/{project_id}/split-scenes")
async def split_scenes(project_id: str):
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
    # wipe existing scenes for clean split
    existing = await db.scenes.find({"project_id": project_id}, {"_id": 0, "id": 1}).to_list(500)
    for s in existing:
        await db.segments.delete_many({"scene_id": s["id"]})
    await db.scenes.delete_many({"project_id": project_id})

    new_scenes = []
    for scene in mock_split_scenes(proj.get("rewritten_story", "")):
        scene["id"] = new_id()
        scene["project_id"] = project_id
        scene["created_at"] = now_iso()
        new_scenes.append(scene)
    if new_scenes:
        await db.scenes.insert_many([s.copy() for s in new_scenes])
    await db.projects.update_one({"id": project_id}, {"$set": {"status": "scenes_ready", "updated_at": now_iso()}})
    await log_generation("split_scenes", project_id, COSTS["split_scenes"])
    return {"scenes": new_scenes}


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------
@api.post("/projects/{project_id}/characters")
async def create_character(project_id: str, body: CharacterCreate):
    doc = {
        "id": new_id(),
        "project_id": project_id,
        "name": body.name,
        "description": body.description,
        "voice_style": body.voice_style,
        "reference_image_url": body.reference_image_url or MOCK_CHARACTER_IMAGE,
        "created_at": now_iso(),
    }
    await db.characters.insert_one(doc.copy())
    return doc


@api.put("/characters/{character_id}")
async def update_character(character_id: str, body: CharacterUpdate):
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields")
    res = await db.characters.update_one({"id": character_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Character not found")
    return await db.characters.find_one({"id": character_id}, {"_id": 0})


@api.delete("/characters/{character_id}")
async def delete_character(character_id: str):
    await db.characters.delete_one({"id": character_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------
@api.post("/projects/{project_id}/scenes")
async def create_scene(project_id: str, body: SceneCreate):
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
async def update_scene(scene_id: str, body: SceneUpdate):
    update = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(400, "No fields")
    res = await db.scenes.update_one({"id": scene_id}, {"$set": update})
    if res.matched_count == 0:
        raise HTTPException(404, "Scene not found")
    return await db.scenes.find_one({"id": scene_id}, {"_id": 0})


@api.delete("/scenes/{scene_id}")
async def delete_scene(scene_id: str):
    await db.segments.delete_many({"scene_id": scene_id})
    await db.scenes.delete_one({"id": scene_id})
    return {"ok": True}


@api.post("/scenes/{scene_id}/generate-image")
async def generate_image(scene_id: str):
    scene = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
    if not scene:
        raise HTTPException(404, "Scene not found")
    # 5% mock failure to power admin failed jobs widget
    if random.random() < 0.05:
        await log_generation("image", scene["project_id"], 0, status="failed", error="mock provider timeout")
        raise HTTPException(503, "Mock image provider timed out")
    url = random.choice(MOCK_SCENE_IMAGES)
    await db.scenes.update_one({"id": scene_id}, {"$set": {"image_url": url, "status": "image_ready"}})
    await log_generation("image", scene["project_id"], COSTS["image"])
    return {"image_url": url, "cost": COSTS["image"]}


@api.post("/scenes/{scene_id}/segments")
async def create_segment(scene_id: str):
    scene = await db.scenes.find_one({"id": scene_id}, {"_id": 0})
    if not scene:
        raise HTTPException(404, "Scene not found")
    if random.random() < 0.05:
        await log_generation("video_segment", scene["project_id"], 0, status="failed", error="mock render failed")
        raise HTTPException(503, "Mock video render failed")
    count = await db.segments.count_documents({"scene_id": scene_id})
    doc = {
        "id": new_id(),
        "scene_id": scene_id,
        "project_id": scene["project_id"],
        "order": count,
        "video_url": random.choice(MOCK_VIDEO_URLS),
        "duration": 5,
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.segments.insert_one(doc.copy())
    await db.scenes.update_one({"id": scene_id}, {"$set": {"status": "video_ready"}})
    await log_generation("video_segment", scene["project_id"], COSTS["video_segment"])
    return doc


@api.post("/scenes/{scene_id}/expand")
async def expand_segment(scene_id: str):
    # Same as creating a new segment – semantically "+5s next"
    return await create_segment(scene_id)


@api.put("/segments/{segment_id}/status")
async def set_segment_status(segment_id: str, body: SegmentStatus):
    res = await db.segments.update_one({"id": segment_id}, {"$set": {"status": body.status}})
    if res.matched_count == 0:
        raise HTTPException(404, "Segment not found")
    return await db.segments.find_one({"id": segment_id}, {"_id": 0})


@api.post("/segments/{segment_id}/regenerate")
async def regenerate_segment(segment_id: str):
    seg = await db.segments.find_one({"id": segment_id}, {"_id": 0})
    if not seg:
        raise HTTPException(404, "Segment not found")
    if random.random() < 0.05:
        await log_generation("video_segment", seg.get("project_id"), 0, status="failed", error="mock regen failed")
        raise HTTPException(503, "Mock video regen failed")
    new_url = random.choice(MOCK_VIDEO_URLS)
    await db.segments.update_one(
        {"id": segment_id},
        {"$set": {"video_url": new_url, "status": "pending"}},
    )
    await log_generation("video_segment", seg.get("project_id"), COSTS["video_segment"])
    return await db.segments.find_one({"id": segment_id}, {"_id": 0})


@api.delete("/segments/{segment_id}")
async def delete_segment(segment_id: str):
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
async def project_cost_estimate(project_id: str):
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
async def export_project(project_id: str):
    proj = await db.projects.find_one({"id": project_id}, {"_id": 0})
    if not proj:
        raise HTTPException(404, "Project not found")
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
    log.info("AI Episode Studio backend ready")


@app.on_event("shutdown")
async def shutdown_event():
    client.close()
