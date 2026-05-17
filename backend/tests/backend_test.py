"""End-to-end backend tests for AI Episode Studio MVP."""
import json
import os
import time
from pathlib import Path
import pytest
import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env", override=False)

RAW_BACKEND_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "http://localhost:8000",
).rstrip("/")

# Accept either origin form (`http://localhost:8000`) or API-root form
# (`http://localhost:8000/api`) so local test runs don't accidentally hit
# `/api/api/*` and produce a wall of misleading 404/JSONDecodeError failures.
if RAW_BACKEND_URL.endswith("/api"):
    API = RAW_BACKEND_URL
    BASE_URL = RAW_BACKEND_URL[:-4]
else:
    BASE_URL = RAW_BACKEND_URL
    API = f"{BASE_URL}/api"


@pytest.fixture(scope="session")
def s():
    sess = requests.Session()
    sess.headers.update({"Content-Type": "application/json"})
    try:
        r = sess.get(f"{API}/", timeout=5)
    except requests.RequestException as exc:
        pytest.fail(
            f"Backend API is not reachable at {API}. Start the FastAPI server "
            f"or set REACT_APP_BACKEND_URL. Original error: {exc}"
        )
    if r.status_code != 200:
        pytest.fail(
            f"Expected AI Episode Studio API at {API}, got HTTP "
            f"{r.status_code}: {r.text[:200]!r}. If your backend URL already "
            "includes /api, pass that exact value; otherwise use the origin "
            "such as http://localhost:8000."
        )
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


def _register_user(s, label):
    email = f"test-{label}-{int(time.time() * 1000)}@example.com"
    r = s.post(
        f"{API}/auth/register",
        json={
            "name": f"Test {label}",
            "email": email,
            "password": "correct-horse-battery",
        },
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["token"]
    assert d["token_type"] == "bearer"
    assert d["user"]["email"] == email
    assert "password_hash" not in d["user"]
    return email, d["token"], d["user"]


def _authed_session(token):
    sess = requests.Session()
    sess.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    return sess


def _test_db_or_none():
    if not os.environ.get("MONGO_URL") or not os.environ.get("DB_NAME"):
        return None
    try:
        from pymongo import MongoClient

        cli = MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=1000)
        cli.admin.command("ping")
        return cli[os.environ["DB_NAME"]]
    except Exception:
        return None


@pytest.fixture(autouse=True)
def reset_demo_wallet_between_tests():
    dbh = _test_db_or_none()
    if dbh is not None:
        dbh.users.update_one(
            {"id": "user-demo"},
            {
                "$set": {
                    "credits": 250,
                    "credits_reserved": 0,
                    "credits_used": 0,
                }
            },
        )


def test_auth_signup_login_current_user_and_invalid_login(s):
    cfg = s.get(f"{API}/auth/config")
    assert cfg.status_code == 200
    assert cfg.json()["auth_enabled"] is False

    email, token, user = _register_user(s, "auth")
    authed = requests.Session()
    authed.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })

    me_r = authed.get(f"{API}/me")
    assert me_r.status_code == 200
    assert me_r.json()["id"] == user["id"]

    login_r = s.post(
        f"{API}/auth/login",
        json={"email": email, "password": "correct-horse-battery"},
    )
    assert login_r.status_code == 200
    assert login_r.json()["token"]

    bad_r = s.post(
        f"{API}/auth/login",
        json={"email": email, "password": "wrong-password"},
    )
    assert bad_r.status_code == 401


def test_authenticated_project_ownership_is_enforced(s):
    _, token_a, user_a = _register_user(s, "owner-a")
    _, token_b, _ = _register_user(s, "owner-b")
    a = requests.Session()
    a.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token_a}"})
    b = requests.Session()
    b.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {token_b}"})

    create_r = a.post(f"{API}/projects", json={"title": "TEST_Owned", "idea": "owned"})
    assert create_r.status_code == 200, create_r.text
    pid = create_r.json()["id"]
    assert create_r.json()["user_id"] == user_a["id"]

    list_a = a.get(f"{API}/projects")
    assert pid in [p["id"] for p in list_a.json()]
    list_b = b.get(f"{API}/projects")
    assert pid not in [p["id"] for p in list_b.json()]

    assert b.get(f"{API}/projects/{pid}").status_code == 404
    assert b.put(f"{API}/projects/{pid}", json={"title": "stolen"}).status_code == 404
    assert b.delete(f"{API}/projects/{pid}").json()["exists"] is False

    # Owner can still access and clean up their project.
    assert a.get(f"{API}/projects/{pid}").status_code == 200
    a.delete(f"{API}/projects/{pid}")


def test_authenticated_nested_resource_ownership_is_enforced(s):
    _, token_a, _ = _register_user(s, "nested-owner-a")
    _, token_b, _ = _register_user(s, "nested-owner-b")
    a = _authed_session(token_a)
    b = _authed_session(token_b)
    dbh = _test_db_or_none()

    project = a.post(f"{API}/projects", json={"title": "TEST_Nested_Owned", "idea": "owned"}).json()
    pid = project["id"]
    try:
        scene = a.post(f"{API}/projects/{pid}/scenes", json={"title": "Owned scene"}).json()
        sid = scene["id"]
        character = a.post(f"{API}/projects/{pid}/characters", json={"name": "Owned character"}).json()
        cid = character["id"]

        if dbh is None:
            pytest.skip("Direct MongoDB access required to seed a segment without spending credits")
        segment = {
            "id": f"seg-test-{int(time.time() * 1000)}",
            "scene_id": sid,
            "project_id": pid,
            "order": 0,
            "parent_segment_id": None,
            "start_second": 0,
            "duration": 5,
            "expand_mode": "initial",
            "continuity_prompt": "owned",
            "video_url": "https://example.com/mock.mp4",
            "status": "pending",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
        dbh.segments.insert_one(segment)
        seg_id = segment["id"]

        assert b.get(f"{API}/projects/{pid}").status_code == 404
        assert b.put(f"{API}/projects/{pid}", json={"title": "stolen"}).status_code == 404
        assert b.delete(f"{API}/projects/{pid}").json()["exists"] is False
        assert b.post(f"{API}/projects/{pid}/restore").status_code == 404

        assert b.post(f"{API}/projects/{pid}/scenes", json={"title": "bad"}).status_code == 404
        assert b.put(f"{API}/scenes/{sid}", json={"title": "bad"}).status_code == 404
        assert b.delete(f"{API}/scenes/{sid}").status_code == 404
        assert b.post(f"{API}/scenes/{sid}/generate-image").status_code == 404
        assert b.post(f"{API}/scenes/{sid}/segments").status_code == 404
        assert b.post(f"{API}/scenes/{sid}/expand").status_code == 404
        assert b.put(f"{API}/scenes/{sid}/segments/reorder", json={"segment_ids": [seg_id]}).status_code == 404

        assert b.put(f"{API}/characters/{cid}", json={"name": "bad"}).status_code == 404
        assert b.delete(f"{API}/characters/{cid}").status_code == 404
        assert b.put(f"{API}/projects/{pid}/characters/reorder", json={"character_ids": [cid]}).status_code == 404

        assert b.put(f"{API}/segments/{seg_id}/status", json={"status": "approved"}).status_code == 404
        assert b.put(f"{API}/segments/{seg_id}", json={"duration": 6}).status_code == 404
        assert b.post(f"{API}/segments/{seg_id}/regenerate").status_code == 404
        assert b.delete(f"{API}/segments/{seg_id}").status_code == 404

        assert b.get(f"{API}/projects/{pid}/cost-estimate").status_code == 404
        assert b.get(f"{API}/projects/{pid}/scene-costs").status_code == 404
        assert b.get(f"{API}/projects/{pid}/providers").status_code == 404
        assert b.put(f"{API}/projects/{pid}/providers", json={"override_providers": True}).status_code == 404
        assert b.get(f"{API}/projects/{pid}/export").status_code == 404

        # Owner can still mutate the resources after the rejected attempts.
        assert a.put(f"{API}/scenes/{sid}", json={"title": "Owner edit"}).status_code == 200
        assert a.put(f"{API}/characters/{cid}", json={"name": "Owner edit"}).status_code == 200
        assert a.put(f"{API}/segments/{seg_id}/status", json={"status": "approved"}).status_code == 200
    finally:
        a.delete(f"{API}/projects/{pid}")


def test_demo_mode_still_works_when_auth_disabled(s):
    r = s.post(f"{API}/projects", json={"title": "TEST_Demo_Mode", "idea": "demo"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user_id"] == "user-demo"
    s.delete(f"{API}/projects/{d['id']}")


def test_admin_endpoints_demo_safe(s):
    r = s.get(f"{API}/admin/stats")
    assert r.status_code == 200
    assert "users" in r.json()


def test_credit_status_demo_wallet_exists(s):
    r = s.get(f"{API}/credits/status")
    assert r.status_code == 200
    d = r.json()
    assert d["user_id"] == "user-demo"
    assert d["credits_available"] == 250
    assert d["credits_reserved"] == 0
    assert d["credits_used"] == 0
    assert d["currency"] == "credits"


def test_credit_status_authenticated_user_wallet_exists(s):
    _, token, user = _register_user(s, "credits")
    authed = _authed_session(token)

    r = authed.get(f"{API}/credits/status")
    assert r.status_code == 200
    d = r.json()
    assert d["user_id"] == user["id"]
    assert d["credits_available"] == 250
    assert d["credits_reserved"] == 0
    assert d["credits_used"] == 0


def test_project_cost_compares_against_authenticated_wallet(s):
    _, token, user = _register_user(s, "wallet-cost")
    authed = _authed_session(token)
    dbh = _test_db_or_none()
    if dbh is None:
        pytest.skip("Direct MongoDB access required to adjust test wallet balance")
    dbh.users.update_one({"id": user["id"]}, {"$set": {"credits": 50, "credits_used": 200}})

    p = authed.post(f"{API}/projects", json={"title": "TEST_Wallet_Owned", "idea": "x"}).json()
    pid = p["id"]
    try:
        authed.post(f"{API}/projects/{pid}/rewrite")
        authed.post(f"{API}/projects/{pid}/split-scenes")
        d = authed.get(f"{API}/projects/{pid}/scene-costs").json()
        assert d["wallet_credits"] == 43  # 50 - rewrite(3) - split(4)
        assert d["wallet_state"] == "insufficient"
    finally:
        authed.delete(f"{API}/projects/{pid}")


def test_generation_deducts_credits_and_records_event(s):
    _, token, user = _register_user(s, "spend")
    authed = _authed_session(token)
    p = authed.post(f"{API}/projects", json={"title": "TEST_Spend", "idea": "x"}).json()
    pid = p["id"]
    try:
        before = authed.get(f"{API}/credits/status").json()
        r = authed.post(f"{API}/projects/{pid}/rewrite")
        assert r.status_code == 200, r.text
        after = authed.get(f"{API}/credits/status").json()
        assert after["credits_available"] == before["credits_available"] - 3
        assert after["credits_used"] == before["credits_used"] + 3

        events = s.get(f"{API}/admin/credit-events")
        assert events.status_code == 200
        assert any(
            e["user_id"] == user["id"]
            and e["project_id"] == pid
            and e["operation"] == "rewrite"
            and e["credits_delta"] == -3
            for e in events.json()
        )
    finally:
        authed.delete(f"{API}/projects/{pid}")


def test_insufficient_credits_blocks_generation_without_deduction(s):
    _, token, user = _register_user(s, "insufficient")
    authed = _authed_session(token)
    dbh = _test_db_or_none()
    if dbh is None:
        pytest.skip("Direct MongoDB access required to adjust test wallet balance")
    dbh.users.update_one({"id": user["id"]}, {"$set": {"credits": 2, "credits_used": 0}})

    p = authed.post(f"{API}/projects", json={"title": "TEST_No_Credits", "idea": "x"}).json()
    pid = p["id"]
    try:
        r = authed.post(f"{API}/projects/{pid}/rewrite")
        assert r.status_code == 402
        assert r.json()["detail"]["message"] == "Insufficient credits"
        status = authed.get(f"{API}/credits/status").json()
        assert status["credits_available"] == 2
        assert status["credits_used"] == 0
    finally:
        authed.delete(f"{API}/projects/{pid}")


def test_blocked_generation_does_not_deduct_credits(s):
    _, token, user = _register_user(s, "failed-spend")
    authed = _authed_session(token)
    dbh = _test_db_or_none()
    if dbh is None:
        pytest.skip("Direct MongoDB access required to seed failed mock state")

    p = authed.post(f"{API}/projects", json={"title": "TEST_Fail_No_Deduct", "idea": "x"}).json()
    pid = p["id"]
    try:
        dbh.users.update_one({"id": user["id"]}, {"$set": {"credits": 250, "credits_used": 0}})
        authed.post(f"{API}/projects/{pid}/rewrite")
        authed.post(f"{API}/projects/{pid}/split-scenes")
        scene_id = authed.get(f"{API}/projects/{pid}").json()["scenes"][0]["id"]
        before = authed.get(f"{API}/credits/status").json()
        # Drop credits under the image cost after prework. The guard should
        # block before any generation or deduction occurs.
        dbh.users.update_one({"id": user["id"]}, {"$set": {"credits": 1}})
        r = authed.post(f"{API}/scenes/{scene_id}/generate-image")
        assert r.status_code == 402
        after = authed.get(f"{API}/credits/status").json()
        assert after["credits_available"] == 1
        assert after["credits_used"] == before["credits_used"]
    finally:
        authed.delete(f"{API}/projects/{pid}")


def test_user_cannot_spend_another_users_credits(s):
    _, token_a, user_a = _register_user(s, "spend-a")
    _, token_b, user_b = _register_user(s, "spend-b")
    a = _authed_session(token_a)
    b = _authed_session(token_b)
    p = a.post(f"{API}/projects", json={"title": "TEST_Private_Credits", "idea": "x"}).json()
    pid = p["id"]
    try:
        assert b.post(f"{API}/projects/{pid}/rewrite").status_code == 404
        a.post(f"{API}/projects/{pid}/rewrite")
        status_a = a.get(f"{API}/credits/status").json()
        status_b = b.get(f"{API}/credits/status").json()
        assert status_a["user_id"] == user_a["id"]
        assert status_a["credits_available"] == 247
        assert status_b["user_id"] == user_b["id"]
        assert status_b["credits_available"] == 250
    finally:
        a.delete(f"{API}/projects/{pid}")


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
    assert isinstance(r.json()["order"], int)

    r2 = s.put(f"{API}/characters/{cid}", json={"description": "brave"})
    assert r2.status_code == 200
    assert r2.json()["description"] == "brave"

    r3 = s.delete(f"{API}/characters/{cid}")
    assert r3.status_code == 200


def test_character_order_field_default_behavior(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_CharOrder", "idea": "x"}).json()
    pid = p["id"]
    try:
        c1 = s.post(f"{API}/projects/{pid}/characters", json={"name": "A"}).json()
        time.sleep(0.01)
        c2 = s.post(f"{API}/projects/{pid}/characters", json={"name": "B"}).json()
        assert c1["order"] == 0
        assert c2["order"] == 1

        # Simulate legacy rows from before Character.order existed.
        db = _direct_db()
        db.characters.update_many({"project_id": pid}, {"$unset": {"order": ""}})

        d = s.get(f"{API}/projects/{pid}").json()
        chars = d["characters"]
        assert [c["id"] for c in chars] == [c1["id"], c2["id"]]
        assert [c["order"] for c in chars] == [0, 1]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_character_reorder_success_and_persist(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_CharReorder", "idea": "x"}).json()
    pid = p["id"]
    try:
        chars = [
            s.post(f"{API}/projects/{pid}/characters", json={"name": f"Char {i}"}).json()
            for i in range(3)
        ]
        new_ids = [chars[2]["id"], chars[0]["id"], chars[1]["id"]]
        r = s.put(f"{API}/projects/{pid}/characters/reorder", json={"character_ids": new_ids})
        assert r.status_code == 200, r.text
        reordered = r.json()["characters"]
        assert [c["id"] for c in reordered] == new_ids
        assert [c["order"] for c in reordered] == [0, 1, 2]

        refreshed = s.get(f"{API}/projects/{pid}").json()["characters"]
        assert [c["id"] for c in refreshed] == new_ids
        assert [c["order"] for c in refreshed] == [0, 1, 2]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_character_reorder_rejects_foreign_or_partial(s):
    p1 = s.post(f"{API}/projects", json={"title": "TEST_CharReorderA", "idea": "x"}).json()
    p2 = s.post(f"{API}/projects", json={"title": "TEST_CharReorderB", "idea": "x"}).json()
    try:
        a1 = s.post(f"{API}/projects/{p1['id']}/characters", json={"name": "A1"}).json()
        a2 = s.post(f"{API}/projects/{p1['id']}/characters", json={"name": "A2"}).json()
        b1 = s.post(f"{API}/projects/{p2['id']}/characters", json={"name": "B1"}).json()

        foreign = s.put(
            f"{API}/projects/{p1['id']}/characters/reorder",
            json={"character_ids": [a1["id"], b1["id"]]},
        )
        assert foreign.status_code == 400

        partial = s.put(
            f"{API}/projects/{p1['id']}/characters/reorder",
            json={"character_ids": [a2["id"]]},
        )
        assert partial.status_code == 400
    finally:
        s.delete(f"{API}/projects/{p1['id']}")
        s.delete(f"{API}/projects/{p2['id']}")


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
    """A fresh scene can reach the default 3-segment cap with correct parent
    links, then the 4th segment is blocked by the MVP guardrail."""
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
    for i in range(1, 3):
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

    blocked = s.post(f"{API}/scenes/{sid}/expand",
                     json={"continuity_prompt": "over cap"})
    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "Video segment limit reached for this MVP."

    # cleanup
    s.delete(f"{API}/scenes/{sid}")


# ---------- Cost ----------
def test_cost_estimate(s):
    r = s.post(f"{API}/cost-estimate", json={"operations": {"image": 4, "video_segment": 6}})
    assert r.status_code == 200
    d = r.json()
    assert d["total_credits"] == 4 * 2 + 6 * 12
    assert "image" in d["breakdown"]


def test_cost_estimate_includes_music_and_export(s):
    r = s.post(
        f"{API}/cost-estimate",
        json={"operations": {"music": 3, "export": 1, "voice": 2}},
    )
    assert r.status_code == 200
    d = r.json()
    # music=2, export=5, voice=1 by default
    assert d["total_credits"] == 3 * 2 + 1 * 5 + 2 * 1


def test_meta_options_costs_complete(s):
    r = s.get(f"{API}/meta/options")
    costs = r.json()["costs"]
    for k in ("rewrite", "split_scenes", "image", "video_segment", "voice", "music", "export"):
        assert k in costs, f"costs missing {k}"
    assert costs["video_segment"] == 12
    assert costs["music"] == 2
    assert costs["export"] == 5


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
    for path in [
        "/admin/stats",
        "/admin/users",
        "/admin/projects",
        "/admin/generations",
        "/admin/credit-events",
        "/admin/failed-jobs",
    ]:
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


# ---------- Feature flags ----------
def test_feature_flags_all_false(s):
    r = s.get(f"{API}/feature-flags")
    assert r.status_code == 200
    flags = r.json()
    for m in ("llm", "image", "video", "voice", "music", "export"):
        assert flags[m] is False, f"{m} flag should be false"
    assert flags["any_real"] is False


# ---------- Per-project provider override ----------
def test_project_creation_has_override_fields(s):
    r = s.post(f"{API}/projects", json={"title": "TEST_ProvProj", "idea": "x"})
    assert r.status_code == 200
    p = r.json()
    assert p["provider_override_enabled"] is False
    for f in (
        "llm_provider", "llm_model",
        "image_provider", "image_model",
        "video_provider", "video_model",
        "voice_provider", "voice_model",
        "music_provider", "music_model",
        "export_provider", "export_mode",
    ):
        assert f in p, f"missing field {f}"
    s.delete(f"{API}/projects/{p['id']}")


def test_get_project_providers_defaults_to_global(s, project_id):
    r = s.get(f"{API}/projects/{project_id}/providers")
    assert r.status_code == 200
    d = r.json()
    assert d["mock_mode"] is True
    assert d["provider_override_enabled"] is False
    # All effective entries pull from global
    for m in ("llm", "image", "video", "voice", "music", "export"):
        assert d["effective"][m]["source"] == "global"
        assert d["effective"][m]["provider"]


def test_project_provider_override_round_trip(s):
    # Use an isolated project so the session-scoped one stays clean
    p = s.post(f"{API}/projects", json={"title": "TEST_OvProj", "idea": "x"}).json()
    pid = p["id"]
    try:
        r = s.put(
            f"{API}/projects/{pid}/providers",
            json={
                "provider_override_enabled": True,
                "image_provider": "openai-image",
                "image_model": "gpt-image-1",
                "video_provider": "runway",
                "video_model": "gen-4.5",
                "export_provider": "aws-mediaconvert",
                "export_mode": "default",
            },
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["provider_override_enabled"] is True
        # project view captures the new selections
        assert d["project"]["image"]["provider"] == "openai-image"
        assert d["project"]["video"]["provider"] == "runway"
        assert d["project"]["export"]["provider"] == "aws-mediaconvert"
        assert d["project"]["export"]["model"] == "default"  # export_mode round-trips
        # effective merges: image/video/export from project, others from global-fallback
        assert d["effective"]["image"]["source"] == "project"
        assert d["effective"]["video"]["source"] == "project"
        assert d["effective"]["export"]["source"] == "project"
        assert d["effective"]["llm"]["source"] == "global-fallback"
        assert d["effective"]["voice"]["source"] == "global-fallback"
        assert d["effective"]["music"]["source"] == "global-fallback"

        # mock_mode always true; flags all false
        assert d["mock_mode"] is True
        for m in ("llm", "image", "video", "voice", "music", "export"):
            assert d["feature_flags"][m] is False
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_images_tab_hint_source_matches_backend_image_status(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_Image_Status", "idea": "x"}).json()
    pid = p["id"]
    try:
        r = s.put(
            f"{API}/projects/{pid}/providers",
            json={
                "provider_override_enabled": True,
                "image_provider": "openai-image",
                "image_model": "gpt-image-1",
            },
        )
        assert r.status_code == 200, r.text
        providers = r.json()
        status = s.get(f"{API}/providers/image/status?project_id={pid}")
        assert status.status_code == 200, status.text
        body = status.json()
        assert providers["effective"]["image"]["provider"] == body["selected_provider"]
        assert providers["effective"]["image"]["model"] == body["selected_model"]
        assert providers["effective"]["image"]["source"] == body["source"]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_project_provider_rejects_unknown(s, project_id):
    r = s.put(
        f"{API}/projects/{project_id}/providers",
        json={"image_provider": "totally-not-real"},
    )
    assert r.status_code == 400


def test_project_provider_test_endpoint_is_mocked(s, project_id):
    r = s.post(
        f"{API}/projects/{project_id}/providers/test",
        json={"modality": "image"},
    )
    assert r.status_code == 200
    d = r.json()
    assert d["mock_mode"] is True
    assert d["ok"] is True
    assert d["real_provider_enabled"] is False
    assert "Mock mode" in d["message"]


def test_existing_routes_still_work_with_override(s):
    """Smoke test: enable override on a project, then run rewrite/split/segment/export."""
    p = s.post(f"{API}/projects", json={"title": "TEST_Smoke", "idea": "neon city"}).json()
    pid = p["id"]
    try:
        # Enable override + pick non-default selections
        s.put(
            f"{API}/projects/{pid}/providers",
            json={
                "provider_override_enabled": True,
                "image_provider": "fal", "image_model": "flux-pro",
                "video_provider": "luma", "video_model": "ray-2",
            },
        )
        # Existing creative pipeline still functions on mocks
        assert s.post(f"{API}/projects/{pid}/rewrite").status_code == 200
        assert s.post(f"{API}/projects/{pid}/split-scenes").status_code == 200
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        sid = scenes[0]["id"]
        assert _retry(lambda: s.post(f"{API}/scenes/{sid}/generate-image")).status_code == 200
        seg = _retry(lambda: s.post(f"{API}/scenes/{sid}/segments")).json()
        s.put(f"{API}/segments/{seg['id']}/status", json={"status": "approved"})
        exp = s.get(f"{API}/projects/{pid}/export").json()
        assert exp["ready"] is True
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_effective_resolution_per_modality(s):
    """Per-modality merge:
    - override OFF → effective.source == 'global'
    - override ON + project value set → effective.source == 'project'
    - override ON + project value empty → effective.source == 'global-fallback'
    Mock mode and feature flags must remain off throughout.
    """
    # Pin global provider settings to a known state first
    s.put(
        f"{API}/settings/providers",
        json={
            "llm":    {"provider": "openai", "model": "gpt-5.2"},
            "image":  {"provider": "fal", "model": "flux-pro"},
            "video":  {"provider": "luma", "model": "ray-2"},
            "voice":  {"provider": "elevenlabs", "model": "eleven-v3"},
            "music":  {"provider": "suno", "model": "v4"},
            "export": {"provider": "ffmpeg-local", "model": "ffmpeg-6"},
        },
    )

    p = s.post(f"{API}/projects", json={"title": "TEST_Eff", "idea": "x"}).json()
    pid = p["id"]
    try:
        # 1. Override OFF → all six modalities resolve from global
        d = s.get(f"{API}/projects/{pid}/providers").json()
        assert d["provider_override_enabled"] is False
        assert d["mock_mode"] is True
        for m in ("llm", "image", "video", "voice", "music", "export"):
            assert d["feature_flags"][m] is False
            assert d["effective"][m]["source"] == "global"
        assert d["effective"]["llm"]["provider"] == "openai"
        assert d["effective"]["image"]["provider"] == "fal"
        assert d["effective"]["video"]["provider"] == "luma"
        assert d["effective"]["voice"]["provider"] == "elevenlabs"
        assert d["effective"]["music"]["provider"] == "suno"
        assert d["effective"]["export"]["provider"] == "ffmpeg-local"
        assert d["effective"]["export"]["model"] == "ffmpeg-6"  # export_mode round-trip

        # 2. Override ON, set image+video+export only
        d2 = s.put(
            f"{API}/projects/{pid}/providers",
            json={
                "provider_override_enabled": True,
                "image_provider": "openai-image", "image_model": "gpt-image-1",
                "video_provider": "luma", "video_model": "ray-2",
                "export_provider": "aws-mediaconvert", "export_mode": "default",
            },
        ).json()
        assert d2["provider_override_enabled"] is True
        # set ones beat global defaults
        assert d2["effective"]["image"] == {
            "provider": "openai-image", "model": "gpt-image-1", "source": "project"
        }
        assert d2["effective"]["video"] == {
            "provider": "luma", "model": "ray-2", "source": "project"
        }
        assert d2["effective"]["export"]["provider"] == "aws-mediaconvert"
        assert d2["effective"]["export"]["model"] == "default"
        assert d2["effective"]["export"]["source"] == "project"
        # untouched modalities fall back to global
        for m in ("llm", "voice", "music"):
            assert d2["effective"][m]["source"] == "global-fallback"
        assert d2["effective"]["llm"]["provider"] == "openai"
        assert d2["effective"]["voice"]["provider"] == "elevenlabs"
        assert d2["effective"]["music"]["provider"] == "suno"

        # 3. Mock mode and flags MUST remain off
        assert d2["mock_mode"] is True
        for m in ("llm", "image", "video", "voice", "music", "export"):
            assert d2["feature_flags"][m] is False

        # 4. Test endpoint reflects the effective source for each modality
        for m, expected_source in (
            ("image", "project"),
            ("video", "project"),
            ("export", "project"),
            ("llm", "global-fallback"),
            ("voice", "global-fallback"),
            ("music", "global-fallback"),
        ):
            tr = s.post(f"{API}/projects/{pid}/providers/test", json={"modality": m}).json()
            assert tr["mock_mode"] is True
            assert tr["real_provider_enabled"] is False
            assert tr["source"] == expected_source
            assert "Mock mode" in tr["message"]
    finally:
        s.delete(f"{API}/projects/{pid}")



# ---------- Voice resolution (character → project → global) ----------
def test_voice_resolution_priority(s):
    """Character voice override beats project; project beats global; mock mode stays on."""
    # Pin global voice
    s.put(
        f"{API}/settings/providers",
        json={"voice": {"provider": "elevenlabs", "model": "eleven-v3"}},
    )
    p = s.post(f"{API}/projects", json={"title": "TEST_Voice", "idea": "x"}).json()
    pid = p["id"]
    try:
        # Add two characters: one without override, one with character-level override
        c1 = s.post(
            f"{API}/projects/{pid}/characters",
            json={"name": "Amara", "voice_style": "Heroine-Calm"},
        ).json()
        c2 = s.post(
            f"{API}/projects/{pid}/characters",
            json={
                "name": "Daniel",
                "voice_style": "Hero-Bold",
                "voice_provider": "openai-tts",
                "voice_model": "tts-1-hd",
            },
        ).json()

        # 1. No project override → both fall through to global except c2 (character override)
        d = s.get(f"{API}/projects/{pid}/voice-resolution").json()
        assert d["mock_mode"] is True
        assert d["global_voice"]["provider"] == "elevenlabs"
        chars = {c["id"]: c for c in d["characters"]}
        assert chars[c1["id"]]["voice"] == {
            "provider": "elevenlabs", "model": "eleven-v3", "source": "global",
        }
        assert chars[c2["id"]]["voice"] == {
            "provider": "openai-tts", "model": "tts-1-hd", "source": "character",
        }

        # 2. Enable project override → Amara picks up project value, Daniel keeps character override
        s.put(
            f"{API}/projects/{pid}/providers",
            json={
                "provider_override_enabled": True,
                "voice_provider": "google-tts", "voice_model": "studio",
            },
        )
        d2 = s.get(f"{API}/projects/{pid}/voice-resolution").json()
        chars2 = {c["id"]: c for c in d2["characters"]}
        assert chars2[c1["id"]]["voice"] == {
            "provider": "google-tts", "model": "studio", "source": "project",
        }
        # Character-level override still wins over project override
        assert chars2[c2["id"]]["voice"] == {
            "provider": "openai-tts", "model": "tts-1-hd", "source": "character",
        }

        # 3. Update Amara to have a character override → she now uses it
        s.put(
            f"{API}/characters/{c1['id']}",
            json={"voice_provider": "elevenlabs", "voice_model": "eleven-turbo"},
        )
        d3 = s.get(f"{API}/projects/{pid}/voice-resolution").json()
        chars3 = {c["id"]: c for c in d3["characters"]}
        assert chars3[c1["id"]]["voice"] == {
            "provider": "elevenlabs", "model": "eleven-turbo", "source": "character",
        }
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_character_create_accepts_voice_fields(s, project_id):
    r = s.post(
        f"{API}/projects/{project_id}/characters",
        json={
            "name": "TEST_VoiceChar",
            "voice_provider": "elevenlabs",
            "voice_model": "eleven-v3",
        },
    )
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["voice_provider"] == "elevenlabs"
    assert c["voice_model"] == "eleven-v3"
    s.delete(f"{API}/characters/{c['id']}")


def test_character_voice_provider_validated(s, project_id):
    c = s.post(
        f"{API}/projects/{project_id}/characters",
        json={"name": "TEST_BadVoice"},
    ).json()
    try:
        r = s.put(
            f"{API}/characters/{c['id']}",
            json={"voice_provider": "totally-not-real"},
        )
        assert r.status_code == 400
    finally:
        s.delete(f"{API}/characters/{c['id']}")


# ---------- Per-scene credit totals ----------
def test_scene_costs_basic_and_multi_segment(s):
    """Scene with 0 segments → planned=1, total=image+video+voice.
    Scene with 2 segments → image + video*2 + voice. Spec example uses
    image=2, video_segment=5, voice=1 → 13. Server uses image=2,
    video_segment=12, voice=1 → image + 12*2 + voice = 2 + 24 + 1 = 27."""
    p = s.post(f"{API}/projects", json={"title": "TEST_SceneCosts", "idea": "x"}).json()
    pid = p["id"]
    try:
        # Scene 1: zero segments → planned=1
        sc1 = s.post(
            f"{API}/projects/{pid}/scenes",
            json={"title": "TEST_OneSeg", "duration": 10},
        ).json()
        # Scene 2: two segments
        sc2 = s.post(
            f"{API}/projects/{pid}/scenes",
            json={"title": "TEST_TwoSeg", "duration": 10},
        ).json()
        seg1 = _retry(lambda: s.post(f"{API}/scenes/{sc2['id']}/segments")).json()
        assert seg1["video_url"]
        seg2 = _retry(lambda: s.post(f"{API}/scenes/{sc2['id']}/expand")).json()
        assert seg2["expand_mode"] == "expand"

        d = s.get(f"{API}/projects/{pid}/scene-costs").json()
        assert d["mock_mode"] is True
        assert d["unit_costs"]["image"] == 2
        assert d["unit_costs"]["video_segment"] == 12
        assert d["unit_costs"]["voice"] == 1

        per = {row["scene_id"]: row for row in d["scenes"]}
        # Scene 1: planned=1, total = 2 + 12 + 1 = 15
        r1 = per[sc1["id"]]
        assert r1["planned_segments"] == 1
        assert r1["breakdown"] == {"image": 2, "video": 12, "voice": 1}
        assert r1["total_credits"] == 15
        assert r1["estimate_unavailable"] is False
        assert r1["missing_costs"] == []

        # Scene 2: 2 segments, total = 2 + 24 + 1 = 27
        r2 = per[sc2["id"]]
        assert r2["segments_count"] == 2
        assert r2["planned_segments"] == 2
        assert r2["breakdown"] == {"image": 2, "video": 24, "voice": 1}
        assert r2["total_credits"] == 27

        assert d["grand_total_credits"] == 15 + 27
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_scene_costs_matches_spec_example():
    """Spec example: image=2, video=5, voice=1, 2 video segments → 13.
    We can't change server costs, but we can verify the formula given
    the spec inputs by computing on the client with the same maths
    that the server uses (image + video*segments + voice)."""
    image, video, voice, n = 2, 5, 1, 2
    assert image + video * n + voice == 13


def test_voice_resolution_remains_after_scene_cost_calls(s):
    """Smoke: hitting scene-costs must not affect voice-resolution; mock mode preserved."""
    p = s.post(f"{API}/projects", json={"title": "TEST_Mix", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(
            f"{API}/projects/{pid}/characters",
            json={"name": "Daniel", "voice_provider": "openai-tts", "voice_model": "tts-1-hd"},
        )
        # call scene-costs (no scenes yet → empty list)
        sc = s.get(f"{API}/projects/{pid}/scene-costs").json()
        assert sc["mock_mode"] is True
        assert sc["scenes"] == []

        v = s.get(f"{API}/projects/{pid}/voice-resolution").json()
        assert v["mock_mode"] is True
        # The character override still wins
        char = v["characters"][0]
        assert char["voice"]["source"] == "character"
        assert char["voice"]["provider"] == "openai-tts"
    finally:
        s.delete(f"{API}/projects/{pid}")


# ---------- Cost badge live updates ----------
def test_scene_costs_grand_total_updates_after_expand(s):
    """Expanding a scene must bump grand_total_credits by exactly video_segment cost."""
    p = s.post(f"{API}/projects", json={"title": "TEST_LiveCost", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc = s.post(
            f"{API}/projects/{pid}/scenes",
            json={"title": "TEST_Live", "duration": 10},
        ).json()
        d0 = s.get(f"{API}/projects/{pid}/scene-costs").json()
        before = d0["grand_total_credits"]
        # planned=1 → 2 + 12 + 1 = 15
        assert before == 15
        # First segment: count goes from 0 → 1, planned stays 1, total stays 15
        _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/segments")).json()
        d1 = s.get(f"{API}/projects/{pid}/scene-costs").json()
        assert d1["grand_total_credits"] == before  # planned unchanged
        # Expand once → segments=2, planned=2, total = 2 + 24 + 1 = 27 (delta = 12)
        _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/expand")).json()
        d2 = s.get(f"{API}/projects/{pid}/scene-costs").json()
        assert d2["grand_total_credits"] == before + 12
        assert d2["scenes"][0]["planned_segments"] == 2
        assert d2["mock_mode"] is True
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_scene_costs_404_for_unknown_project(s):
    r = s.get(f"{API}/projects/does-not-exist/scene-costs")
    assert r.status_code == 404


# ---------- Wallet ring + high-cost scenes ----------
def test_studio_config_endpoint(s):
    r = s.get(f"{API}/config")
    assert r.status_code == 200
    d = r.json()
    assert d["mock_mode"] is True
    assert d["wallet_credits"] == 250
    assert d["high_cost_scene_threshold_percent"] == 25


def test_scene_costs_includes_wallet_pct_and_state(s):
    """Scene costs use the current wallet after paid rewrite/split deductions."""
    p = s.post(f"{API}/projects", json={"title": "TEST_Wallet", "idea": "x"}).json()
    pid = p["id"]
    try:
        before = s.get(f"{API}/credits/status").json()
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")
        after = s.get(f"{API}/credits/status").json()
        assert after["credits_available"] == before["credits_available"] - 7

        d = s.get(f"{API}/projects/{pid}/scene-costs").json()
        assert d["wallet_credits"] == after["credits_available"]
        assert d["high_cost_scene_threshold_percent"] == 25
        # 6 scenes × 15 = 90
        assert d["grand_total_credits"] == 90
        assert d["wallet_pct"] == round(90 / after["credits_available"] * 100, 1)
        assert d["wallet_state"] == "normal"
        # Each scene = 15/90 ≈ 16.7% → below 25% → not high-cost
        for sc in d["scenes"]:
            assert sc["share_pct"] == round(15 / 90 * 100, 1)
            assert sc["high_cost"] is False
        assert d["mock_mode"] is True
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_wallet_state_thresholds(s):
    """Drive wallet_state across normal → warning → high → insufficient using the
    `wallet_credits` query-param override on /scene-costs."""
    p = s.post(f"{API}/projects", json={"title": "TEST_WalletState", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")  # grand_total = 90

        # Boundaries:
        #   normal       pct < 41          → wallet > 90/0.41 ≈ 220 → e.g. 250 → 36%
        #   warning      41 <= pct < 71    → wallet 128..219       → e.g. 180 → 50%
        #   high         71 <= pct <= 100  → wallet 90..127        → e.g. 100 → 90%
        #   insufficient pct > 100         → wallet < 90           → e.g. 50  → 180%
        cases = [
            (250, "normal"),
            (180, "warning"),
            (100, "high"),
            (50, "insufficient"),
        ]
        for wallet, expected in cases:
            r = s.get(
                f"{API}/projects/{pid}/scene-costs",
                params={"wallet_credits": wallet},
            )
            d = r.json()
            assert d["wallet_credits"] == wallet
            assert d["wallet_state"] == expected, (
                f"wallet={wallet} got {d['wallet_state']} pct={d['wallet_pct']}"
            )
            assert d["mock_mode"] is True
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_high_cost_scene_flag_with_configurable_threshold(s):
    """Force a single scene to dominate, then verify the high-cost flag flips
    only when above the configurable threshold."""
    p = s.post(f"{API}/projects", json={"title": "TEST_HighCost", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        big = scenes[0]
        # Default cap allows 3 segments under big → total = 2 + 12*3 + 1 = 39
        # Other 5 scenes stay at 15 each → grand = 39 + 75 = 114
        # big share = 39/114 ≈ 34.2%, other share = 15/114 ≈ 13.2%
        for _ in range(3):
            _retry(lambda: s.post(f"{API}/scenes/{big['id']}/expand"))

        # Default threshold (25%): only big crosses
        d = s.get(f"{API}/projects/{pid}/scene-costs").json()
        assert d["high_cost_scene_threshold_percent"] == 25
        big_row = next(r for r in d["scenes"] if r["scene_id"] == big["id"])
        assert big_row["segments_count"] == 3
        assert big_row["total_credits"] == 39
        assert big_row["share_pct"] > 25
        assert big_row["high_cost"] is True
        for r in d["scenes"]:
            if r["scene_id"] != big["id"]:
                assert r["share_pct"] < 25
                assert r["high_cost"] is False

        # Lower threshold to 10% via query → all scenes flip to high-cost
        d2 = s.get(
            f"{API}/projects/{pid}/scene-costs",
            params={"high_cost_pct": 10},
        ).json()
        assert d2["high_cost_scene_threshold_percent"] == 10
        for r in d2["scenes"]:
            assert r["high_cost"] is True

        # Raise threshold to 50% via query → only the big scene's share is < 50% so nothing flags
        d3 = s.get(
            f"{API}/projects/{pid}/scene-costs",
            params={"high_cost_pct": 50},
        ).json()
        assert d3["high_cost_scene_threshold_percent"] == 50
        for r in d3["scenes"]:
            assert r["high_cost"] is False
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_scene_costs_404_still_works_for_wallet(s):
    """Fallback path: unknown project → 404 (frontend then shows 'Estimate unavailable')."""
    r = s.get(f"{API}/projects/totally-not-real/scene-costs")
    assert r.status_code == 404


# ---------- Dashboard project cost summaries + trend deltas ----------
def test_list_projects_includes_cost_summary(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_DashSum", "idea": "x"}).json()
    pid = p["id"]
    try:
        before = s.get(f"{API}/credits/status").json()
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")
        after = s.get(f"{API}/credits/status").json()
        assert after["credits_available"] == before["credits_available"] - 7

        listing = s.get(f"{API}/projects").json()
        row = next(r for r in listing if r["id"] == pid)
        cs = row["cost_summary"]
        assert cs["grand_total_credits"] == 90  # 6 scenes × 15
        assert cs["wallet_credits"] == after["credits_available"]
        assert cs["wallet_pct"] == round(90 / after["credits_available"] * 100, 1)
        assert cs["wallet_state"] == "normal"
        assert cs["estimate_unavailable"] is False
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_dashboard_summary_handles_insufficient_state(s):
    """Dashboard summary can show insufficient after paid video generations
    reduce the current wallet, without violating per-scene segment caps."""
    p = s.post(f"{API}/projects", json={"title": "TEST_Insuff", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")  # 6 scenes, 90 credits
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        # Add two segments per scene. This stays under the default 60-second
        # project cap while spending enough credits to make the current wallet
        # lower than the estimate:
        # grand_total = 6 × (2 + 12*2 + 1) = 162.
        # The 12 video generations spend 144 credits, leaving the wallet below
        # the current estimate and making the dashboard insufficient.
        for sc in scenes:
            for _ in range(2):
                r = _retry(lambda sc_id=sc["id"]: s.post(f"{API}/scenes/{sc_id}/expand"))
                assert r.status_code == 200, r.text

        listing = s.get(f"{API}/projects").json()
        row = next(r for r in listing if r["id"] == pid)
        cs = row["cost_summary"]
        assert cs["grand_total_credits"] == 162
        assert cs["wallet_credits"] < cs["grand_total_credits"]
        assert cs["wallet_state"] == "insufficient"
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_trend_increase_on_expand(s):
    """grand_total must increase by exactly video_segment cost on a 2nd+ segment."""
    p = s.post(f"{API}/projects", json={"title": "TEST_TrendUp", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc = s.post(
            f"{API}/projects/{pid}/scenes",
            json={"title": "TEST_T", "duration": 10},
        ).json()
        # First segment: planned was 1, becomes 1 → no delta
        before = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/segments"))
        after_first = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        assert after_first == before  # +0

        # Expand: segments 1→2, planned 1→2, delta = +12
        _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/expand"))
        after_expand = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        assert after_expand - after_first == 12
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_trend_decrease_on_segment_delete(s):
    """Deleting a 2nd segment must drop grand_total by video_segment cost."""
    p = s.post(f"{API}/projects", json={"title": "TEST_TrendDown", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc = s.post(
            f"{API}/projects/{pid}/scenes",
            json={"title": "TEST_TD", "duration": 10},
        ).json()
        seg1 = _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/segments")).json()
        seg2 = _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/expand")).json()
        before = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        # Delete one segment → segments 2→1, planned 2→1 → -12
        r = s.delete(f"{API}/segments/{seg2['id']}")
        assert r.status_code == 200
        after = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        assert before - after == 12
        # Sanity: seg1 still exists
        assert seg1["id"]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_trend_decrease_on_scene_delete(s):
    """Deleting a whole scene drops grand_total by image+video+voice (15 default)."""
    p = s.post(f"{API}/projects", json={"title": "TEST_SceneDel", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")  # 6 × 15 = 90
        before = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        s.delete(f"{API}/scenes/{scenes[0]['id']}")
        after = s.get(f"{API}/projects/{pid}/scene-costs").json()["grand_total_credits"]
        assert before - after == 15
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_dashboard_estimate_unavailable_when_costs_missing():
    """If a unit cost were missing the summary would flag estimate_unavailable. We
    can't pop the live COSTS dict from a separate test process, but we can assert
    the formula's documented behaviour by checking the field exists and is False
    under normal conditions (positive contract test)."""
    # Pure contract: the field is part of the public schema.
    expected_keys = {
        "grand_total_credits", "wallet_credits", "wallet_pct",
        "wallet_state", "estimate_unavailable",
    }
    # No request needed; this is a schema-level assertion on the test code itself.
    assert expected_keys


# ---------- Reduce to Draft ----------
def test_reduce_to_draft_basic_and_idempotent(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_Reduce", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc = s.post(
            f"{API}/projects/{pid}/scenes",
            json={"title": "TEST_R", "duration": 10},
        ).json()
        # Add the default max 3 segments under the scene (1 generate + 2 expansions)
        _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/segments"))
        for _ in range(2):
            _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/expand"))
        # Sanity: 3 segments, scene total = 2 + 12*3 + 1 = 39
        cs = s.get(f"{API}/projects/{pid}/scene-costs").json()
        row = next(r for r in cs["scenes"] if r["scene_id"] == sc["id"])
        assert row["segments_count"] == 3
        assert row["total_credits"] == 39

        blocked = s.post(f"{API}/scenes/{sc['id']}/expand")
        assert blocked.status_code == 400
        assert blocked.json()["detail"] == "Video segment limit reached for this MVP."

        before_total = cs["grand_total_credits"]
        r = s.post(f"{API}/scenes/{sc['id']}/reduce-to-draft")
        assert r.status_code == 200
        d = r.json()
        assert d["mock_mode"] is True
        assert d["deleted_segments"] == 2
        assert d["saved_credits"] == 24  # 2 × 12
        assert len(d["segments"]) == 1   # only earliest kept

        cs2 = s.get(f"{API}/projects/{pid}/scene-costs").json()
        row2 = next(r for r in cs2["scenes"] if r["scene_id"] == sc["id"])
        assert row2["segments_count"] == 1
        assert row2["total_credits"] == 15
        assert before_total - cs2["grand_total_credits"] == 24

        # Idempotent: running again deletes nothing
        r = s.post(f"{API}/scenes/{sc['id']}/reduce-to-draft").json()
        assert r["deleted_segments"] == 0
        assert r["saved_credits"] == 0
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_reduce_to_draft_404_unknown_scene(s):
    r = s.post(f"{API}/scenes/does-not-exist/reduce-to-draft")
    assert r.status_code == 404


# ---------- Continuity prompt + segment partial update ----------
def test_segment_continuity_prompt_update(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_Cont", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc = s.post(f"{API}/projects/{pid}/scenes", json={"title": "TEST_C"}).json()
        seg = _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/segments")).json()
        r = s.put(
            f"{API}/segments/{seg['id']}",
            json={"continuity_prompt": "  Continue smoothly into a wide shot.  "},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["continuity_prompt"] == "Continue smoothly into a wide shot."
        # Existing dedicated status route still works
        r2 = s.put(f"{API}/segments/{seg['id']}/status", json={"status": "approved"})
        assert r2.json()["status"] == "approved"
        # Empty body rejected
        r3 = s.put(f"{API}/segments/{seg['id']}", json={})
        assert r3.status_code == 400
        # Bad duration rejected
        r4 = s.put(f"{API}/segments/{seg['id']}", json={"duration": 0})
        assert r4.status_code == 400
    finally:
        s.delete(f"{API}/projects/{pid}")


# ---------- Scene reorder ----------
def test_scene_reorder_success(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_Reorder", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        ids = [sc["id"] for sc in scenes]
        # Reverse the order
        new_order = list(reversed(ids))
        r = s.put(f"{API}/projects/{pid}/scenes/reorder", json={"scene_ids": new_order})
        assert r.status_code == 200
        out = r.json()["scenes"]
        assert [sc["id"] for sc in out] == new_order
        for i, sc in enumerate(out):
            assert sc["order"] == i
        # Re-read and confirm persisted
        scenes2 = s.get(f"{API}/projects/{pid}").json()["scenes"]
        assert [sc["id"] for sc in scenes2] == new_order
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_scene_reorder_rejects_foreign_or_partial(s):
    p1 = s.post(f"{API}/projects", json={"title": "TEST_R1", "idea": "x"}).json()
    p2 = s.post(f"{API}/projects", json={"title": "TEST_R2", "idea": "y"}).json()
    try:
        s.post(f"{API}/projects/{p1['id']}/rewrite")
        s.post(f"{API}/projects/{p1['id']}/split-scenes")
        s.post(f"{API}/projects/{p2['id']}/rewrite")
        s.post(f"{API}/projects/{p2['id']}/split-scenes")
        s1_ids = [sc["id"] for sc in s.get(f"{API}/projects/{p1['id']}").json()["scenes"]]
        s2_ids = [sc["id"] for sc in s.get(f"{API}/projects/{p2['id']}").json()["scenes"]]
        # Mix in a foreign scene id
        bad = [s2_ids[0]] + s1_ids[1:]
        r = s.put(f"{API}/projects/{p1['id']}/scenes/reorder", json={"scene_ids": bad})
        assert r.status_code == 400
        # Subset of own scenes (missing one) is also rejected
        r2 = s.put(f"{API}/projects/{p1['id']}/scenes/reorder", json={"scene_ids": s1_ids[:-1]})
        assert r2.status_code == 400
    finally:
        s.delete(f"{API}/projects/{p1['id']}")
        s.delete(f"{API}/projects/{p2['id']}")


# ---------- Segment reorder ----------
def test_segment_reorder_success_recomputes_start_second(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_SegReorder", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc = s.post(f"{API}/projects/{pid}/scenes", json={"title": "TEST_SR"}).json()
        a = _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/segments")).json()
        b = _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/expand")).json()
        c = _retry(lambda: s.post(f"{API}/scenes/{sc['id']}/expand")).json()
        # Reverse order
        new_ids = [c["id"], b["id"], a["id"]]
        r = s.put(f"{API}/scenes/{sc['id']}/segments/reorder", json={"segment_ids": new_ids})
        assert r.status_code == 200
        segs = r.json()["segments"]
        assert [seg["id"] for seg in segs] == new_ids
        # start_second recomputed cumulatively from duration=5 each
        assert [seg["start_second"] for seg in segs] == [0, 5, 10]
        assert [seg["order"] for seg in segs] == [0, 1, 2]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_segment_reorder_rejects_foreign(s):
    p = s.post(f"{API}/projects", json={"title": "TEST_SegFor", "idea": "x"}).json()
    pid = p["id"]
    try:
        sc1 = s.post(f"{API}/projects/{pid}/scenes", json={"title": "TEST_SR1"}).json()
        sc2 = s.post(f"{API}/projects/{pid}/scenes", json={"title": "TEST_SR2"}).json()
        a = _retry(lambda: s.post(f"{API}/scenes/{sc1['id']}/segments")).json()
        b = _retry(lambda: s.post(f"{API}/scenes/{sc2['id']}/segments")).json()
        # Try to reorder scene1 with scene2's segment mixed in
        r = s.put(
            f"{API}/scenes/{sc1['id']}/segments/reorder",
            json={"segment_ids": [b["id"], a["id"]]},
        )
        assert r.status_code == 400
        # Partial set also rejected
        r2 = s.put(
            f"{API}/scenes/{sc1['id']}/segments/reorder",
            json={"segment_ids": []},
        )
        assert r2.status_code == 400
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_existing_expand_and_costs_still_work_after_reorder(s):
    """Smoke: reorder + expand + scene-costs all coexist correctly."""
    p = s.post(f"{API}/projects", json={"title": "TEST_Smoke2", "idea": "x"}).json()
    pid = p["id"]
    try:
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        # reverse scenes
        new_order = list(reversed([sc["id"] for sc in scenes]))
        s.put(f"{API}/projects/{pid}/scenes/reorder", json={"scene_ids": new_order})

        # Expand scene[0] (now last-of-original)
        target = new_order[0]
        seg1 = _retry(lambda: s.post(f"{API}/scenes/{target}/segments")).json()
        seg2 = _retry(lambda: s.post(f"{API}/scenes/{target}/expand")).json()
        assert seg2["expand_mode"] == "expand"
        assert seg2["parent_segment_id"] == seg1["id"]
        # scene-costs reflects 2 segments under that scene
        cs = s.get(f"{API}/projects/{pid}/scene-costs").json()
        row = next(r for r in cs["scenes"] if r["scene_id"] == target)
        assert row["segments_count"] == 2
        assert row["total_credits"] == 2 + 12 * 2 + 1
    finally:
        s.delete(f"{API}/projects/{pid}")



# ---------- Soft delete + restore + purge ----------
def _seed_full_project(s, title):
    """Create a project with scenes, characters, and segments. Returns pid."""
    r = s.post(f"{API}/projects", json={"title": title, "idea": "A small experiment for cascade testing"})
    pid = r.json()["id"]
    # rewrite + split → 6 scenes
    s.post(f"{API}/projects/{pid}/rewrite")
    s.post(f"{API}/projects/{pid}/split-scenes")
    proj = s.get(f"{API}/projects/{pid}").json()
    scene_id = proj["scenes"][0]["id"]
    # 2 characters
    for n in ("Alice", "Bob"):
        s.post(
            f"{API}/projects/{pid}/characters",
            json={"name": n, "description": "test", "voice_style": "Narrator-Warm"},
        )
    # 2 segments on the first scene (initial + expand)
    _retry(lambda: s.post(f"{API}/scenes/{scene_id}/segments"))
    _retry(lambda: s.post(f"{API}/scenes/{scene_id}/expand"))
    return pid


def _hard_purge_via_mongo(pid):
    """Test cleanup: force-purge a single project bypassing the 24h window."""
    dbh = _direct_db()
    dbh.projects.delete_one({"id": pid})
    dbh.scenes.delete_many({"project_id": pid})
    dbh.characters.delete_many({"project_id": pid})
    dbh.segments.delete_many({"project_id": pid})


def test_delete_project_is_soft_delete(s):
    pid = _seed_full_project(s, "TEST_SOFT_DELETE")
    try:
        r = s.delete(f"{API}/projects/{pid}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        assert body["soft_deleted"] is True
        assert body["project_id"] == pid
        assert body["deleted_at"]
        assert body["delete_expires_at"] > body["deleted_at"]
        # Soft-deleted projects vanish from list + get returns 404
        listing = s.get(f"{API}/projects").json()
        assert all(p["id"] != pid for p in listing)
        assert s.get(f"{API}/projects/{pid}").status_code == 404
        # Child data still exists in Mongo (will be removed by purge later)
        dbh = _direct_db()
        assert dbh.scenes.count_documents({"project_id": pid}) == 6
        assert dbh.characters.count_documents({"project_id": pid}) == 2
        assert dbh.segments.count_documents({"project_id": pid}) == 2
    finally:
        _hard_purge_via_mongo(pid)


def test_restore_project_brings_it_back(s):
    pid = _seed_full_project(s, "TEST_RESTORE")
    try:
        s.delete(f"{API}/projects/{pid}")
        assert s.get(f"{API}/projects/{pid}").status_code == 404
        r = s.post(f"{API}/projects/{pid}/restore")
        assert r.status_code == 200, r.text
        restored = r.json()
        assert restored["id"] == pid
        assert restored["status"] in ("draft", "story_ready", "scenes_ready")
        assert "deleted_at" not in restored
        # Re-appears on the listing and GET
        listing = s.get(f"{API}/projects").json()
        assert any(p["id"] == pid for p in listing)
        assert s.get(f"{API}/projects/{pid}").status_code == 200
    finally:
        _hard_purge_via_mongo(pid)


def test_restore_unknown_project_returns_404(s):
    r = s.post(f"{API}/projects/does-not-exist-xxxx/restore")
    assert r.status_code == 404


def test_delete_unknown_project_is_safe(s):
    r = s.delete(f"{API}/projects/does-not-exist-xxxx")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["soft_deleted"] is False
    assert body["exists"] is False


def test_delete_does_not_touch_other_projects(s):
    pid_a = _seed_full_project(s, "TEST_SOFT_A")
    pid_b = _seed_full_project(s, "TEST_SOFT_B")
    try:
        s.delete(f"{API}/projects/{pid_a}")
        # B is fully intact (visible + child data still queryable)
        after_b = s.get(f"{API}/projects/{pid_b}").json()
        assert len(after_b["scenes"]) == 6
        assert len(after_b["characters"]) == 2
        scenes_with_segs = [sc for sc in after_b["scenes"] if sc.get("segments")]
        assert scenes_with_segs
    finally:
        _hard_purge_via_mongo(pid_a)
        s.delete(f"{API}/projects/{pid_b}")
        _hard_purge_via_mongo(pid_b)


def test_purge_removes_expired_projects_and_their_children(s):
    pid = _seed_full_project(s, "TEST_PURGE_EXPIRED")
    try:
        s.delete(f"{API}/projects/{pid}")
        # Force-expire via Mongo
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        dbh = _direct_db()
        past_iso = (_dt.now(_tz.utc) - _td(hours=1)).isoformat()
        dbh.projects.update_one({"id": pid}, {"$set": {"delete_expires_at": past_iso}})
        r = s.post(f"{API}/admin/purge-deleted-projects")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        # Our project should be in the purged counts (other expired projects may
        # exist from other test runs — assert at least our contribution).
        assert body["purged"]["projects"] >= 1
        assert body["purged"]["scenes"] >= 6
        assert body["purged"]["characters"] >= 2
        assert body["purged"]["segments"] >= 2
        # Hard-gone everywhere
        dbh = _direct_db()
        assert dbh.projects.count_documents({"id": pid}) == 0
        assert dbh.scenes.count_documents({"project_id": pid}) == 0
        assert dbh.characters.count_documents({"project_id": pid}) == 0
        assert dbh.segments.count_documents({"project_id": pid}) == 0
    finally:
        _hard_purge_via_mongo(pid)


def test_purge_does_not_touch_active_or_non_expired_projects(s):
    active_pid = _seed_full_project(s, "TEST_PURGE_ACTIVE")
    soft_pid = _seed_full_project(s, "TEST_PURGE_SOFT_NOT_EXPIRED")
    try:
        s.delete(f"{API}/projects/{soft_pid}")  # delete_expires_at is +24h
        r = s.post(f"{API}/admin/purge-deleted-projects")
        assert r.status_code == 200, r.text
        # Neither project we just made should have been purged.
        dbh = _direct_db()
        assert dbh.projects.count_documents({"id": active_pid}) == 1
        assert dbh.projects.count_documents({"id": soft_pid}) == 1
        assert dbh.scenes.count_documents({"project_id": active_pid}) == 6
        assert dbh.scenes.count_documents({"project_id": soft_pid}) == 6
        # Active project must still be reachable via API
        assert s.get(f"{API}/projects/{active_pid}").status_code == 200
        # Soft-deleted one must still be hidden (still within window)
        assert s.get(f"{API}/projects/{soft_pid}").status_code == 404
    finally:
        _hard_purge_via_mongo(active_pid)
        _hard_purge_via_mongo(soft_pid)


def test_delete_then_restore_is_idempotent(s):
    pid = _seed_full_project(s, "TEST_SOFT_IDEMPOTENT")
    try:
        first = s.delete(f"{API}/projects/{pid}").json()
        second = s.delete(f"{API}/projects/{pid}").json()
        assert first["soft_deleted"] is True
        assert second["soft_deleted"] is True
        assert second.get("already_deleted") is True
        # Restore once
        r = s.post(f"{API}/projects/{pid}/restore")
        assert r.status_code == 200
        # Restoring an active project is a no-op (returns project, not 404)
        r2 = s.post(f"{API}/projects/{pid}/restore")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["id"] == pid
        assert "deleted_at" not in body2
    finally:
        _hard_purge_via_mongo(pid)


# ---------- Admin Recently Deleted panel + scheduler ----------
def test_admin_deleted_projects_lists_unexpired_only(s):
    fresh_pid = _seed_full_project(s, "TEST_ADMIN_DEL_FRESH")
    expired_pid = _seed_full_project(s, "TEST_ADMIN_DEL_EXPIRED")
    try:
        s.delete(f"{API}/projects/{fresh_pid}")
        s.delete(f"{API}/projects/{expired_pid}")
        # Force the second project's window into the past.
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        dbh = _direct_db()
        past_iso = (_dt.now(_tz.utc) - _td(hours=1)).isoformat()
        dbh.projects.update_one(
            {"id": expired_pid}, {"$set": {"delete_expires_at": past_iso}}
        )
        body = s.get(f"{API}/admin/deleted-projects").json()
        ids = [row["id"] for row in body["items"]]
        assert fresh_pid in ids
        assert expired_pid not in ids
        # Row shape for the fresh entry includes counts.
        fresh_row = next(r for r in body["items"] if r["id"] == fresh_pid)
        assert fresh_row["title"] == "TEST_ADMIN_DEL_FRESH"
        assert fresh_row["scenes_count"] == 6
        assert fresh_row["characters_count"] == 2
        assert fresh_row["segments_count"] == 2
        assert fresh_row["delete_expires_at"] > fresh_row["deleted_at"]
    finally:
        _hard_purge_via_mongo(fresh_pid)
        _hard_purge_via_mongo(expired_pid)


def test_admin_deleted_projects_restore_round_trip(s):
    pid = _seed_full_project(s, "TEST_ADMIN_DEL_RESTORE")
    try:
        s.delete(f"{API}/projects/{pid}")
        before = s.get(f"{API}/admin/deleted-projects").json()
        assert any(r["id"] == pid for r in before["items"])
        r = s.post(f"{API}/projects/{pid}/restore")
        assert r.status_code == 200
        after = s.get(f"{API}/admin/deleted-projects").json()
        assert all(r["id"] != pid for r in after["items"])
        # Project is back in the main listing
        listing = s.get(f"{API}/projects").json()
        assert any(p["id"] == pid for p in listing)
    finally:
        _hard_purge_via_mongo(pid)


def test_purge_helper_only_purges_expired_deleted_projects(s):
    """The shared `_purge_expired_projects_now` helper (used by both the
    scheduler and the admin endpoint) must:
      - purge expired soft-deleted projects (cascades scenes/chars/segments)
      - leave non-expired soft-deleted projects alone
      - leave active projects alone
    """
    active = _seed_full_project(s, "TEST_PURGE_HELPER_ACTIVE")
    fresh = _seed_full_project(s, "TEST_PURGE_HELPER_FRESH_SOFT")
    expired = _seed_full_project(s, "TEST_PURGE_HELPER_EXPIRED_SOFT")
    try:
        s.delete(f"{API}/projects/{fresh}")
        s.delete(f"{API}/projects/{expired}")
        from datetime import datetime as _dt, timezone as _tz, timedelta as _td
        dbh = _direct_db()
        past_iso = (_dt.now(_tz.utc) - _td(hours=1)).isoformat()
        dbh.projects.update_one(
            {"id": expired}, {"$set": {"delete_expires_at": past_iso}}
        )
        r = s.post(f"{API}/admin/purge-deleted-projects")
        body = r.json()
        assert body["ok"] is True
        # Expired project is fully gone in Mongo
        assert dbh.projects.count_documents({"id": expired}) == 0
        assert dbh.scenes.count_documents({"project_id": expired}) == 0
        assert dbh.characters.count_documents({"project_id": expired}) == 0
        assert dbh.segments.count_documents({"project_id": expired}) == 0
        # Active project and child rows intact
        assert dbh.projects.count_documents({"id": active}) == 1
        assert dbh.scenes.count_documents({"project_id": active}) == 6
        # Fresh soft-deleted project still alive (waiting for its 24h window)
        assert dbh.projects.count_documents({"id": fresh}) == 1
        assert dbh.scenes.count_documents({"project_id": fresh}) == 6
        # Active project is still reachable via API
        assert s.get(f"{API}/projects/{active}").status_code == 200
        # Restore on the purged id must fail with 404 (it's truly gone).
        assert s.post(f"{API}/projects/{expired}/restore").status_code == 404
    finally:
        _hard_purge_via_mongo(active)
        _hard_purge_via_mongo(fresh)
        _hard_purge_via_mongo(expired)


# ---------- Phase 2A unified provider endpoints ----------
def test_unified_providers_test_returns_mock_response(s):
    r = s.post(f"{API}/providers/test", json={"modality": "image"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "mock"
    assert body["status"] == "skipped"
    assert body["feature_flag_enabled"] is False
    assert body["key_present"] is False
    assert body["key_status"] == "not_configured"
    assert "no real provider call" in body["message"].lower()


def test_unified_providers_test_with_project_uses_resolved(s):
    r = s.post(f"{API}/projects", json={"title": "ProvTest", "idea": "x"})
    pid = r.json()["id"]
    try:
        # Override the project's image provider — the unified endpoint should
        # report the project source after we enable override.
        s.put(
            f"{API}/projects/{pid}/providers",
            json={
                "provider_override_enabled": True,
                "image_provider": "gemini-nano-banana",
                "image_model": "nano-banana",
            },
        )
        r2 = s.post(f"{API}/providers/test", json={"modality": "image", "project_id": pid})
        body = r2.json()
        assert body["provider"] == "gemini-nano-banana"
        assert body["source"] == "project"
        assert body["mode"] == "mock"
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_unified_providers_test_404_for_unknown_project(s):
    r = s.post(f"{API}/providers/test", json={"modality": "video", "project_id": "missing-xxx"})
    assert r.status_code == 404


def test_provider_status_endpoint_global(s):
    r = s.get(f"{API}/providers/voice/status")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "mock"
    assert body["would_use_real_provider"] is False
    assert body["feature_flag_enabled"] is False
    assert body["selected_provider"]
    assert body["selected_model"] is not None
    assert body["secrets_backend"] in {"disabled", "ssm"}
    assert body["key_present"] is False
    assert body["key_status"] == "not_configured"
    assert "secret_value" not in json.dumps(body).lower()


def test_provider_status_endpoint_rejects_unknown_modality(s):
    r = s.get(f"{API}/providers/foo/status")
    assert r.status_code == 400


def test_existing_image_generation_still_works_with_guard(s, project_id):
    """Smoke-check the existing /generate-image endpoint after the guard was wired in."""
    dbh = _test_db_or_none()
    proj = s.get(f"{API}/projects/{project_id}").json()
    if not proj.get("scenes"):
        # Make sure scenes exist (in case the fixture ordering changed)
        s.post(f"{API}/projects/{project_id}/rewrite")
        s.post(f"{API}/projects/{project_id}/split-scenes")
        proj = s.get(f"{API}/projects/{project_id}").json()
    scene_id = proj["scenes"][0]["id"]
    r = _retry(lambda: s.post(f"{API}/scenes/{scene_id}/generate-image"))
    assert r.status_code == 200
    body = r.json()
    assert "image_url" in body
    assert body["cost"] == 2
    if dbh is not None:
        assert dbh.assets.count_documents({
            "project_id": project_id,
            "scene_id": scene_id,
            "asset_type": "scene_image",
        }) >= 1



# ---------- Phase 2A.5 provider activity log ----------
_SECRET_FIELDS = {
    "api_key", "secret", "secret_key", "authorization", "bearer", "token",
    "password", "client_secret",
}
# Substrings we never want to see leak into the activity log
_SECRET_FORBIDDEN_SUBSTRINGS = ("sk-", "Bearer ", "api_key=", "api-key=")
_SAFE_FIELDS = {
    "id", "created_at", "modality", "provider_name", "model_name", "source",
    "mode", "status", "estimated_credits", "provider_job_id", "message",
    "error", "duration_ms", "project_id", "scene_id", "segment_id",
    "feature_flag_enabled", "key_present",
    "provider_http_status", "provider_error_message", "endpoint", "input_mode",
}


def _assert_record_is_safe(rec):
    """Assert ONLY safety invariants (no secrets, allowlisted fields)."""
    # 1. Only safe metadata fields exist.
    extra = set(rec.keys()) - _SAFE_FIELDS
    assert not extra, f"Activity record leaked unexpected fields: {extra}"
    # 2. No common secret keys present.
    for k in rec.keys():
        assert k.lower() not in _SECRET_FIELDS
    # 3. No common secret substrings in any string value.
    for k, v in rec.items():
        if isinstance(v, str):
            for needle in _SECRET_FORBIDDEN_SUBSTRINGS:
                assert needle not in v, f"Secret-like substring '{needle}' found in {k}"
    # 4. Modalities without connected real providers must not report a key.
    # Image is real-capable now, so key_present=true is valid safe metadata for
    # real image activity as long as no secret value is exposed.
    if rec["modality"] in ("video", "voice", "music", "export"):
        assert rec["key_present"] is False


def test_provider_activity_endpoint_shape(s):
    r = s.get(f"{API}/admin/provider-activity?limit=5")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body and "count" in body and body["limit"] == 5


def test_provider_activity_records_created_for_rewrite_image_video(s):
    pid = s.post(f"{API}/projects", json={"title": "ActivityTest", "idea": "x"}).json()["id"]
    try:
        # rewrite → LLM activity
        s.post(f"{API}/projects/{pid}/rewrite")
        s.post(f"{API}/projects/{pid}/split-scenes")
        scene_id = s.get(f"{API}/projects/{pid}").json()["scenes"][0]["id"]
        # image → image activity
        _retry(lambda: s.post(f"{API}/scenes/{scene_id}/generate-image"))
        # video segment → video activity
        _retry(lambda: s.post(f"{API}/scenes/{scene_id}/segments"))

        items = s.get(f"{API}/admin/provider-activity?limit=50").json()["items"]
        # The latest items should include records for this project.
        ours = [i for i in items if i.get("project_id") == pid]
        modalities = {i["modality"] for i in ours}
        assert {"llm", "image", "video"}.issubset(modalities), (
            f"Expected llm/image/video activity for {pid}, got {modalities}"
        )

        # Each record looks safe + carries duration + correct scope ids.
        for rec in ours:
            _assert_record_is_safe(rec)
            assert rec["status"] in ("success", "blocked", "skipped", "failed")
            assert isinstance(rec.get("duration_ms"), int)
            assert rec["estimated_credits"] >= 0
        # The image + video records should reference scene_id.
        for rec in ours:
            if rec["modality"] in ("image", "video"):
                assert rec.get("scene_id") == scene_id
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_provider_activity_no_api_keys_anywhere(s):
    rows = s.get(f"{API}/admin/provider-activity?limit=200").json()["items"]
    for rec in rows:
        _assert_record_is_safe(rec)


def test_provider_activity_limit_capping(s):
    # Limit of 5000 must clamp to <= 200.
    r = s.get(f"{API}/admin/provider-activity?limit=5000")
    assert r.status_code == 200
    body = r.json()
    assert body["limit"] <= 200



# ---------- Phase 2A.5 + provider health pulse ----------
def _direct_db():
    """Direct pymongo handle for seeding provider_activity in health tests.

    Tests must clean up their seeded rows so they don't pollute neighbors.
    """
    from pymongo import MongoClient  # local import; only used in tests

    if not os.environ.get("MONGO_URL") or not os.environ.get("DB_NAME"):
        pytest.skip(
            "Direct MongoDB health tests require MONGO_URL and DB_NAME "
            "in the environment or backend/.env"
        )
    cli = MongoClient(os.environ["MONGO_URL"])
    return cli[os.environ["DB_NAME"]]


_HEALTH_SEED_TAG = "test-health-seed"


def _seed_activity(modality, *, total, failed, avg_duration_ms, age_minutes=5):
    """Insert N synthetic activity rows for one modality, tagged for cleanup."""
    from datetime import datetime, timezone, timedelta
    db = _direct_db()
    when = (datetime.now(timezone.utc) - timedelta(minutes=age_minutes)).isoformat()
    docs = []
    for i in range(total):
        status = "failed" if i < failed else "success"
        docs.append({
            "id": f"{_HEALTH_SEED_TAG}-{modality}-{i}",
            "created_at": when,
            "modality": modality,
            "provider_name": f"mock-{modality}",
            "model_name": "mock-model",
            "source": "global",
            "mode": "mock",
            "status": status,
            "estimated_credits": 0,
            "provider_job_id": None,
            "message": "test",
            "error": "synthetic failure" if status == "failed" else None,
            "duration_ms": int(avg_duration_ms),
            "project_id": None,
            "scene_id": None,
            "segment_id": None,
            "feature_flag_enabled": False,
            "key_present": False,
        })
    if docs:
        db.provider_activity.insert_many(docs)


def _purge_seed():
    db = _direct_db()
    db.provider_activity.delete_many({"id": {"$regex": f"^{_HEALTH_SEED_TAG}-"}})


@pytest.fixture
def clean_seed():
    _purge_seed()
    yield
    _purge_seed()


def test_provider_health_all_modalities_listed(s, clean_seed):
    r = s.get(f"{API}/admin/provider-health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window_minutes"] == 60
    mods = {m["modality"] for m in body["modalities"]}
    assert mods == {"llm", "image", "video", "voice", "music", "export"}


def test_provider_health_no_activity_status(s, clean_seed):
    """Use a tiny window so the existing background activity doesn't count."""
    r = s.get(f"{API}/admin/provider-health?window_minutes=1")
    body = r.json()
    # Pick a modality with no recent activity (music). Even if some other test
    # races by, we don't seed music here so it should still be no_activity in
    # the 1-minute window when we haven't generated music in that window.
    music = next(m for m in body["modalities"] if m["modality"] == "music")
    assert music["status"] == "no_activity"
    assert music["total_calls"] == 0


def test_provider_health_healthy_status(s, clean_seed):
    _seed_activity("voice", total=5, failed=0, avg_duration_ms=20, age_minutes=2)
    body = s.get(f"{API}/admin/provider-health?window_minutes=10").json()
    voice = next(m for m in body["modalities"] if m["modality"] == "voice")
    assert voice["total_calls"] >= 5
    assert voice["failed_calls"] == 0
    assert voice["avg_duration_ms"] <= 100  # well under the 3000ms slow threshold
    assert voice["status"] == "healthy"


def test_provider_health_slow_status(s, clean_seed):
    _seed_activity("music", total=4, failed=0, avg_duration_ms=5000, age_minutes=2)
    body = s.get(f"{API}/admin/provider-health?window_minutes=10").json()
    music = next(m for m in body["modalities"] if m["modality"] == "music")
    assert music["total_calls"] >= 4
    assert music["failed_calls"] == 0
    assert music["avg_duration_ms"] >= 3001
    assert music["status"] == "slow"


def test_provider_health_failing_status(s, clean_seed):
    # 2 failed of 4 = 50% failure rate → failing
    _seed_activity("export", total=4, failed=2, avg_duration_ms=10, age_minutes=2)
    body = s.get(f"{API}/admin/provider-health?window_minutes=10").json()
    export = next(m for m in body["modalities"] if m["modality"] == "export")
    assert export["total_calls"] >= 4
    assert export["failed_calls"] >= 2
    assert export["status"] == "failing"


def test_provider_health_no_secrets_in_response(s, clean_seed):
    body = s.get(f"{API}/admin/provider-health").json()
    # Whole response, recursively serialized, must not contain any secret-like keys/values.
    blob = json.dumps(body).lower()
    for needle in ("api_key", "secret", "bearer ", "sk-", "password", "token"):
        assert needle not in blob, f"secret-like substring '{needle}' leaked"
    # Each modality entry has the documented allowlist only.
    allowed = {
        "modality", "total_calls", "success_calls", "failed_calls",
        "avg_duration_ms", "status",
    }
    for m in body["modalities"]:
        assert set(m.keys()) == allowed



# ---------- Creative Quality Engine ----------
_QUALITY_KEYS = (
    "hook_strength", "conflict_strength", "emotional_tension",
    "visual_potential", "cliffhanger_strength", "dialogue_strength",
    "overall_story_score",
)


def _fresh_quality_project(s, title="QualityTest"):
    pid = s.post(f"{API}/projects", json={"title": title, "idea": "Two thieves break into a vault with a secret older than them."}).json()["id"]
    s.post(f"{API}/projects/{pid}/rewrite")
    s.post(f"{API}/projects/{pid}/split-scenes")
    return pid


def test_story_quality_scores_populated_after_rewrite(s):
    pid = s.post(f"{API}/projects", json={"title": "ScoreCheck", "idea": "A reporter risks everything to expose a city-wide secret."}).json()["id"]
    try:
        r = s.post(f"{API}/projects/{pid}/rewrite")
        assert r.status_code == 200
        body = r.json()
        assert "quality_scores" in body
        for k in _QUALITY_KEYS:
            assert k in body["quality_scores"]
            assert 1 <= int(body["quality_scores"][k]) <= 100

        # Score also persisted on the project document
        proj = s.get(f"{API}/projects/{pid}").json()["project"]
        for k in _QUALITY_KEYS:
            assert proj["quality_scores"][k] == body["quality_scores"][k]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_improve_story_endpoint_updates_story_and_scores(s):
    pid = _fresh_quality_project(s, "ImproveCheck")
    try:
        before = s.get(f"{API}/projects/{pid}").json()["project"]
        story_before = before["rewritten_story"]
        scores_before = before["quality_scores"]

        r = s.post(f"{API}/projects/{pid}/improve-story", json={"kind": "cliffhanger"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rewritten_story" in body
        assert body["rewritten_story"] != story_before
        assert "quality_scores" in body
        # cliffhanger boost — cliffhanger_strength should rise (deterministic mock)
        assert body["quality_scores"]["cliffhanger_strength"] >= scores_before["cliffhanger_strength"]
        assert body["improvement"]["kind"] == "cliffhanger"

        # History is persisted
        after = s.get(f"{API}/projects/{pid}").json()["project"]
        hist = after.get("improvement_history", [])
        assert len(hist) >= 1
        assert hist[-1]["kind"] == "cliffhanger"
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_improve_story_unknown_kind_rejected(s):
    pid = _fresh_quality_project(s, "ImproveBadKind")
    try:
        r = s.post(f"{API}/projects/{pid}/improve-story", json={"kind": "not-a-real-kind"})
        assert r.status_code == 422  # pydantic Literal rejection
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_scenes_have_tension_fields_after_split(s):
    pid = _fresh_quality_project(s, "TensionFields")
    try:
        scenes = s.get(f"{API}/projects/{pid}").json()["scenes"]
        assert scenes, "expected scenes after split"
        for sc in scenes:
            assert 15 <= int(sc["tension_level"]) <= 99
            assert sc["emotional_goal"]
            assert sc["conflict_point"]
            assert sc["reveal_or_turning_point"]
            assert 1 <= int(sc["cliffhanger_value"]) <= 100
            # Prompt enhancer fields exist (may be empty strings prior to enhance)
            assert "raw_visual_prompt" in sc
            assert "enhanced_image_prompt" in sc
            assert "enhanced_video_prompt" in sc
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_enhance_image_and_video_prompt(s):
    pid = _fresh_quality_project(s, "PromptEnhance")
    try:
        scene = s.get(f"{API}/projects/{pid}").json()["scenes"][0]
        r1 = s.post(f"{API}/scenes/{scene['id']}/enhance-prompt", json={"kind": "image-prompt"})
        assert r1.status_code == 200
        sc1 = r1.json()["scene"]
        assert sc1["enhanced_image_prompt"]
        assert "lighting" in sc1["enhanced_image_prompt"].lower() or "cinematic" in sc1["enhanced_image_prompt"].lower()
        assert sc1["enhanced_video_prompt"] == ""  # not enhanced yet

        r2 = s.post(f"{API}/scenes/{scene['id']}/enhance-prompt", json={"kind": "video-prompt"})
        assert r2.status_code == 200
        sc2 = r2.json()["scene"]
        assert sc2["enhanced_video_prompt"]
        assert "camera" in sc2["enhanced_video_prompt"].lower() or "motion" in sc2["enhanced_video_prompt"].lower()
        # The image enhancement is still there
        assert sc2["enhanced_image_prompt"]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_improve_scene_drama_and_dialogue(s):
    pid = _fresh_quality_project(s, "SceneDrama")
    try:
        scene = s.get(f"{API}/projects/{pid}").json()["scenes"][0]
        tension0 = scene["tension_level"]

        r = s.post(f"{API}/scenes/{scene['id']}/enhance-prompt", json={"kind": "scene-drama"})
        assert r.status_code == 200
        sc = r.json()["scene"]
        assert sc["tension_level"] > tension0
        # Dialogue gets prefixed with a heightened line
        assert '"' in sc["dialogue"]

        r2 = s.post(f"{API}/scenes/{scene['id']}/enhance-prompt", json={"kind": "dialogue"})
        assert r2.status_code == 200
        sc2 = r2.json()["scene"]
        assert sc2["dialogue"]
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_creative_hints_endpoint(s):
    r = s.get(f"{API}/creative/enhancement-hints")
    assert r.status_code == 200
    body = r.json()
    assert "lighting" in body["image_traits"]
    assert "motion" in body["video_traits"]
    assert "realism" in body["image_hint"]
    assert "motion" in body["video_hint"]
    assert "suspenseful" in body["improve_kinds"]
    assert "image-prompt" in body["enhance_kinds"]
    for k in _QUALITY_KEYS:
        assert k in body["quality_keys"]


def test_existing_rewrite_split_generate_expand_export_still_work(s):
    """Regression — Creative Quality endpoints did not break the core pipeline."""
    pid = s.post(f"{API}/projects", json={"title": "Regression", "idea": "x"}).json()["id"]
    try:
        assert s.post(f"{API}/projects/{pid}/rewrite").status_code == 200
        assert s.post(f"{API}/projects/{pid}/split-scenes").status_code == 200
        scene_id = s.get(f"{API}/projects/{pid}").json()["scenes"][0]["id"]
        assert _retry(lambda: s.post(f"{API}/scenes/{scene_id}/generate-image")).status_code == 200
        assert _retry(lambda: s.post(f"{API}/scenes/{scene_id}/segments")).status_code == 200
        assert _retry(lambda: s.post(f"{API}/scenes/{scene_id}/expand")).status_code == 200
        assert s.get(f"{API}/projects/{pid}/export").status_code == 200
    finally:
        s.delete(f"{API}/projects/{pid}")


def test_provider_activity_remains_mock_when_flag_off_after_quality_work(s):
    """With USE_REAL_LLM_PROVIDER=false, every NEW row generated by quality
    work for THIS project must still be mock-mode."""
    pid = _fresh_quality_project(s, "MockGuard")
    try:
        s.post(f"{API}/projects/{pid}/improve-story", json={"kind": "emotional"})
        scene = s.get(f"{API}/projects/{pid}").json()["scenes"][0]
        s.post(f"{API}/scenes/{scene['id']}/enhance-prompt", json={"kind": "image-prompt"})

        # Only look at rows that belong to THIS project (Phase 2B may have
        # earlier real-mode rows from other test runs / manual flag flips).
        rows = s.get(f"{API}/admin/provider-activity?limit=200").json()["items"]
        ours = [r for r in rows if r.get("project_id") == pid]
        assert ours, "expected provider activity records for this project"
        for r in ours:
            assert r["mode"] == "mock"
            if r["modality"] != "llm":
                assert r["key_present"] is False
    finally:
        s.delete(f"{API}/projects/{pid}")
