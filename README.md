# AI Episode Studio

AI Episode Studio is a full-stack mock AI production tool for drafting short
1-3 minute story videos. Creators can create a project, rewrite a story idea,
split it into scenes, manage characters, generate mock images/video segments,
review voice/music settings, estimate credits, and export a mock stitched
preview.

The app is intentionally mock-first. Provider selection and provider activity
plumbing exist, and real LLM execution is gated behind server-side flags and
keys. Image, video, voice, music, and export providers remain mock-only.

## MVP Plan

The complete path to a 100% MVP is documented in
[docs/MVP_PLAN.md](/home/ec2-user/ai-series-studio/docs/MVP_PLAN.md). It
tracks what is already complete, what remains, build order, provider strategy,
cost controls, testing strategy, launch criteria, and post-MVP scope.

## Current Product State

- Story, scene, character, image, video segment, voice/music, provider, and
  export workflows are implemented for the mock-first studio.
- Characters support an `order` field and drag handles in the Cast /
  Characters view.
- Scene, segment, and character reorder are implemented with optimistic
  drag-and-drop in the frontend.
- Soft delete, restore, Admin Recently Deleted, and expired-project purge are
  implemented.
- Real LLM support exists for text operations, gated behind
  `USE_REAL_LLM_PROVIDER`.
- Image, video, voice, music, and export providers remain mock-only.

## Reorder Endpoints

Scenes:

```http
PUT /api/projects/{project_id}/scenes/reorder
```

```json
{ "scene_ids": ["scene1", "scene2", "scene3"] }
```

Characters:

```http
PUT /api/projects/{project_id}/characters/reorder
```

```json
{ "character_ids": ["char1", "char2", "char3"] }
```

Segments:

```http
PUT /api/scenes/{scene_id}/segments/reorder
```

```json
{ "segment_ids": ["segment1", "segment2", "segment3"] }
```

Each reorder endpoint validates ownership, rejects foreign or partial ID lists,
updates `order` based on list position, and returns the reordered records.

## Prerequisites

- Python 3.11+
- Node.js 20+ with Yarn 1.x
- MongoDB running locally or a reachable MongoDB URI

MongoDB is required for the backend. For a local instance:

```bash
mongod --dbpath /path/to/local/mongo-data
```

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` if your MongoDB is not at `mongodb://localhost:27017`.
The default development values are:

```bash
MONGO_URL=mongodb://localhost:27017
DB_NAME=ai_episode_studio
CORS_ORIGINS=http://localhost:3000
```

Real LLM mode uses an optional runtime package that is not required for Codex
local development. Most local development and all mock-mode tests use only
`requirements.txt`. If you have access to the package source and need to
exercise real LLM calls, install:

```bash
pip install -r requirements-real-llm.txt
```

Start the backend:

```bash
cd backend
source .venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/api/
```

## Frontend Setup

This project uses Yarn. Do not generate `package-lock.json`.

```bash
cd frontend
yarn install
cp .env.example .env
```

Start the frontend:

```bash
cd frontend
yarn start
```

Open `http://localhost:3000`.

## Developer Commands

From the repository root:

```bash
make backend-test
make backend-http-test
make frontend-lint
make frontend-build
make dev-check
```

If `make` is not installed, use the shell fallback:

```bash
bash scripts/dev-check.sh
```

`make dev-check` runs self-contained backend provider tests, frontend lint, and
frontend production build in sequence. `make backend-http-test` exports
`REACT_APP_BACKEND_URL=http://localhost:8000`, so the HTTP integration tests
target your local backend by default.

## Backend Tests

For self-contained backend tests:

```bash
make backend-test
```

For the complete backend HTTP integration suite, start MongoDB and the backend
first:

```bash
cd backend
source .venv/bin/activate
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Then, in another shell:

```bash
make backend-http-test
```

Provider-layer unit tests can run without a running backend:

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/test_provider_layer.py tests/test_phase2b_llm.py
```

## Frontend Lint And Build

```bash
cd frontend
yarn lint
yarn build
```

The production build requires `REACT_APP_BACKEND_URL` in `frontend/.env`.

## Remote Preview Test Mode

`backend/tests/backend_test.py` reads `REACT_APP_BACKEND_URL` and defaults to
`http://localhost:8000` when the variable is not set. To run the HTTP suite
against a remote preview explicitly:

```bash
REACT_APP_BACKEND_URL=https://your-preview-host.example.com python -m pytest backend/tests/backend_test.py
```

To force local mode:

```bash
REACT_APP_BACKEND_URL=http://localhost:8000 python -m pytest backend/tests/backend_test.py
```

## Provider Status

- Real LLM calls are guarded by `USE_REAL_LLM_PROVIDER=true` and the required
  server-side LLM key/runtime. If the flag is off, missing, or the real call
  fails, the app falls back to mock behavior.
- Image, video, voice, music, and export remain mock-only even if their
  `USE_REAL_*_PROVIDER` flags are set.
- Do not put real API keys in `.env.example`, README examples, or committed
  files.

## Backlog

P1 completed:

- Character drag handles in Cast view.
- Safe delete / Undo delete.
- Recently Deleted admin panel.
- Background purge scheduler.

P2 remaining:

- Auth.
- Stripe metering.
- Real Image provider.
- Real Video provider.
- Real Voice provider.
- Real Music provider.
- Real Export / FFmpeg worker.
- Public sharing.
- Multi-tenant teams.
- Versioned scene revisions.

## Useful Paths

- Backend API: `backend/server.py`
- Provider layer: `backend/providers/`
- Creative quality helpers: `backend/creative_quality.py`
- Frontend app: `frontend/src/`
- Studio tabs: `frontend/src/pages/tabs/`
- Shared studio UI: `frontend/src/components/studio/`
