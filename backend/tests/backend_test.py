"""End-to-end backend tests for AI Episode Studio MVP."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ai-episode-studio.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    return sess


@pytest.fixture(scope="session")
def project_id(s):
    r = s.post(f"{API}/projects", json={"title": "TEST_Project", "idea": "A lighthouse keeper hears whispers"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    yield pid
    s.delete(f"{API}/projects/{pid}")


# ---------- Health & meta ----------
def test_root(s):
    r = s.get(f"{API}/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_meta_options(s):
    r = s.get(f"{API}/meta/options")
    assert r.status_code == 200
    d = r.json()
    assert "voices" in d and "music_moods" in d and "costs" in d
    assert isinstance(d["voices"], list) and len(d["voices"]) > 0
    assert "image" in d["costs"]


def test_me(s):
    r = s.get(f"{API}/me")
    assert r.status_code == 200
    assert r.json()["id"] == "user-demo"


# ---------- Projects ----------
def test_list_projects_contains_created(s, project_id):
    r = s.get(f"{API}/projects")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert project_id in ids


def test_get_project(s, project_id):
    r = s.get(f"{API}/projects/{project_id}")
    assert r.status_code == 200
    d = r.json()
    assert d["project"]["id"] == project_id
    assert isinstance(d["scenes"], list)
    assert isinstance(d["characters"], list)


def test_update_project(s, project_id):
    r = s.put(f"{API}/projects/{project_id}", json={"title": "TEST_Project_Renamed"})
    assert r.status_code == 200
    assert r.json()["title"] == "TEST_Project_Renamed"


def test_rewrite(s, project_id):
    r = s.post(f"{API}/projects/{project_id}/rewrite")
    assert r.status_code == 200
    d = r.json()
    assert d["cost"] == 3
    assert "ACT I" in d["rewritten_story"]


def test_split_scenes(s, project_id):
    r = s.post(f"{API}/projects/{project_id}/split-scenes")
    assert r.status_code == 200
    scenes = r.json()["scenes"]
    assert len(scenes) == 6


# ---------- Characters ----------
def test_character_crud(s, project_id):
    r = s.post(f"{API}/projects/{project_id}/characters", json={"name": "TEST_Hero", "voice_style": "Hero-Bold"})
    assert r.status_code == 200
    cid = r.json()["id"]
    assert r.json()["reference_image_url"]

    r2 = s.put(f"{API}/characters/{cid}", json={"description": "brave"})
    assert r2.status_code == 200
    assert r2.json()["description"] == "brave"

    r3 = s.delete(f"{API}/characters/{cid}")
    assert r3.status_code == 200


# ---------- Scenes & segments ----------
@pytest.fixture(scope="session")
def scene_id(s, project_id):
    # after split-scenes there should be 6, take the first
    r = s.get(f"{API}/projects/{project_id}")
    scenes = r.json()["scenes"]
    if not scenes:
        s.post(f"{API}/projects/{project_id}/split-scenes")
        r = s.get(f"{API}/projects/{project_id}")
        scenes = r.json()["scenes"]
    return scenes[0]["id"]


def test_update_scene(s, scene_id):
    r = s.put(f"{API}/scenes/{scene_id}", json={"dialogue": "hello", "characters": ["c1"]})
    assert r.status_code == 200
    assert r.json()["dialogue"] == "hello"
    assert r.json()["characters"] == ["c1"]


def test_create_scene(s, project_id):
    r = s.post(f"{API}/projects/{project_id}/scenes", json={"title": "TEST_Extra", "duration": 8})
    assert r.status_code == 200
    assert r.json()["title"] == "TEST_Extra"


def _retry(call):
    for _ in range(3):
        r = call()
        if r.status_code != 503:
            return r
        time.sleep(0.3)
    return r


def test_generate_image(s, scene_id):
    r = _retry(lambda: s.post(f"{API}/scenes/{scene_id}/generate-image"))
    assert r.status_code == 200, r.text
    assert r.json()["image_url"].startswith("http")


def test_create_segment_and_expand(s, scene_id):
    r = _retry(lambda: s.post(f"{API}/scenes/{scene_id}/segments"))
    assert r.status_code == 200
    seg = r.json()
    assert seg["video_url"].startswith("http")
    assert seg["status"] == "pending"
    # New segment-model fields
    for k in ("parent_segment_id", "start_second", "duration", "expand_mode", "continuity_prompt"):
        assert k in seg, f"missing {k}"
    # initial segment may or may not be the very first; assert shape only
    assert seg["duration"] == 5
    assert isinstance(seg["start_second"], int)
    assert seg["expand_mode"] in ("initial", "expand")

    r2 = _retry(lambda: s.post(f"{API}/scenes/{scene_id}/expand"))
    assert r2.status_code == 200
    seg2 = r2.json()
    assert seg2["expand_mode"] == "expand"
    # Expansion must reference an existing parent and continue from prior end
    assert seg2["parent_segment_id"] is not None
    assert seg2["start_second"] >= seg["start_second"] + seg["duration"]

    # approve original
    r3 = s.put(f"{API}/segments/{seg['id']}/status", json={"status": "approved"})
    assert r3.status_code == 200
    assert r3.json()["status"] == "approved"

    # regenerate keeps fields and resets to pending
    r4 = _retry(lambda: s.post(f"{API}/segments/{seg['id']}/regenerate"))
    assert r4.status_code == 200
    assert r4.json()["status"] == "pending"


def test_expand_chain_links_parents(s, project_id):
    """A fresh scene + 3 expansions must produce a linked chain with correct
    start_second progression and parent ids."""
    r = s.post(f"{API}/projects/{project_id}/scenes", json={"title": "TEST_Chain", "duration": 5})
    sid = r.json()["id"]

    first = _retry(lambda: s.post(f"{API}/scenes/{sid}/segments",
                                  json={"continuity_prompt": "moody neon street"}))
    assert first.status_code == 200, first.text
    first = first.json()
    assert first["expand_mode"] == "initial"
    assert first["parent_segment_id"] is None
    assert first["start_second"] == 0
    assert first["continuity_prompt"] == "moody neon street"

    prev = first
    for i in range(1, 4):
        r = _retry(lambda: s.post(f"{API}/scenes/{sid}/expand",
                                  json={"continuity_prompt": f"continuation {i}"}))
        assert r.status_code == 200, r.text
        cur = r.json()
        assert cur["expand_mode"] == "expand"
        assert cur["parent_segment_id"] == prev["id"]
        assert cur["start_second"] == prev["start_second"] + prev["duration"]
        assert cur["order"] == prev["order"] + 1
        assert cur["duration"] == 5
        assert cur["continuity_prompt"] == f"continuation {i}"
        prev = cur

    # cleanup
    s.delete(f"{API}/scenes/{sid}")


# ---------- Cost ----------
def test_cost_estimate(s):
    r = s.post(f"{API}/cost-estimate", json={"operations": {"image": 4, "video_segment": 6}})
    assert r.status_code == 200
    d = r.json()
    assert d["total_credits"] == 4 * 2 + 6 * 5
    assert "image" in d["breakdown"]


def test_project_cost_estimate(s, project_id):
    r = s.get(f"{API}/projects/{project_id}/cost-estimate")
    assert r.status_code == 200
    assert "total_credits" in r.json()
    assert "operations" in r.json()


# ---------- Export ----------
def test_export(s, project_id, scene_id):
    # ensure at least one approved segment
    seg = _retry(lambda: s.post(f"{API}/scenes/{scene_id}/segments")).json()
    s.put(f"{API}/segments/{seg['id']}/status", json={"status": "approved"})
    r = s.get(f"{API}/projects/{project_id}/export")
    assert r.status_code == 200
    d = r.json()
    assert d["ready"] is True
    assert d["final_video_url"]
    assert any(a["segment_id"] == seg["id"] for a in d["approved_segments"])


# ---------- Admin ----------
def test_admin_endpoints(s):
    for path in ["/admin/stats", "/admin/users", "/admin/projects", "/admin/generations", "/admin/failed-jobs"]:
        r = s.get(f"{API}{path}")
        assert r.status_code == 200, f"{path} failed"
    stats = s.get(f"{API}/admin/stats").json()
    for k in ["users", "projects", "generations", "failed_jobs", "credits_used", "internal_cost_usd"]:
        assert k in stats


# ---------- Provider settings ----------
def test_provider_options(s):
    r = s.get(f"{API}/settings/providers/options")
    assert r.status_code == 200
    d = r.json()
    assert d["mock_mode"] is True
    for m in ("llm", "image", "video", "voice", "music", "export"):
        assert m in d["catalog"]
        assert any(p["id"] == "custom" for p in d["catalog"][m])


def test_provider_settings_get_and_update(s):
    r = s.get(f"{API}/settings/providers")
    assert r.status_code == 200
    d = r.json()
    assert d["mock_mode"] is True
    for m in ("llm", "image", "video", "voice", "music", "export"):
        assert m in d
        assert "provider" in d[m]
        assert "model" in d[m]

    # Update a couple of modalities
    r2 = s.put(
        f"{API}/settings/providers",
        json={
            "image": {"provider": "openai-image", "model": "gpt-image-1"},
            "video": {"provider": "luma", "model": "ray-2"},
            "music": {"provider": "custom", "custom_provider": "internal-music", "custom_model": "v1"},
        },
    )
    assert r2.status_code == 200, r2.text
    out = r2.json()
    assert out["image"]["provider"] == "openai-image"
    assert out["video"]["provider"] == "luma"
    assert out["music"]["provider"] == "custom"
    assert out["music"]["custom_provider"] == "internal-music"
    assert out["mock_mode"] is True

    # No API key field is ever returned or accepted
    for m in ("llm", "image", "video", "voice", "music", "export"):
        assert "api_key" not in out[m]


def test_provider_settings_rejects_unknown_provider(s):
    r = s.put(
        f"{API}/settings/providers",
        json={"image": {"provider": "totally-not-real", "model": "x"}},
    )
    assert r.status_code == 400


def test_provider_test_connection_is_mocked(s):
    r = s.post(f"{API}/settings/providers/test", json={"modality": "voice"})
    assert r.status_code == 200
    d = r.json()
    assert d["mock_mode"] is True
    assert d["ok"] is True
    assert "Mock mode" in d["message"]
    assert d["modality"] == "voice"
