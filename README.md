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

Real image provider preparation is documented in
[docs/IMAGE_PROVIDER_PLAN.md](/home/ec2-user/ai-series-studio/docs/IMAGE_PROVIDER_PLAN.md).
The current recommendation is OpenAI `gpt-image-1` as the first MVP image
provider after the secrets/storage gates are implemented. No real image
provider is connected yet.

## Current Product State

- Story, scene, character, image, video segment, voice/music, provider, and
  export workflows are implemented for the mock-first studio.
- MVP auth is implemented with local email/password beta accounts, JWT bearer
  access tokens, and per-user project ownership. Requests without a token still
  use `user-demo` when `AUTH_ENABLED=false` and `AUTH_DEMO_MODE=true` for local
  demo compatibility.
- Per-user credit balances are enforced for generation actions. The backend
  checks credits before story rewrite, story improvement, scene split, prompt
  enhancement, image generation, video segment generation/regeneration, and
  mock export, deducts only after successful generation, and blocks
  insufficient-credit requests with HTTP 402.
- Characters support an `order` field and drag handles in the Cast /
  Characters view.
- Scene, segment, and character reorder are implemented with optimistic
  drag-and-drop in the frontend.
- Soft delete, restore, Admin Recently Deleted, and expired-project purge are
  implemented.
- Real LLM support exists for text operations, gated behind
  `USE_REAL_LLM_PROVIDER`.
- Image, video, voice, music, and export providers remain mock-only.
- Real image generation remains blocked until `USE_REAL_IMAGE_PROVIDER=true`,
  a server-side secret is available, credit/cost checks pass, and generated
  image storage is ready.
- A backend-only secrets resolver foundation exists. It defaults to disabled
  mode and can later resolve provider API keys from AWS SSM Parameter Store
  `SecureString` without exposing secret values to MongoDB or the frontend.

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

## Auth And Ownership

Local/demo mode is enabled by default. With `AUTH_ENABLED=false` and no
`Authorization` header, the API uses the seeded `user-demo` account so existing
local tests and demos keep working. Real beta accounts can register or sign in:

```http
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout
GET /api/me
```

Authenticated requests use `Authorization: Bearer <token>`. Project listing,
project detail/mutation, character, scene, segment, export, and provider
project views are scoped to the current user. To require auth for every request
in a non-demo environment, set:

```bash
AUTH_ENABLED=true
AUTH_DEMO_MODE=false
JWT_SECRET_KEY=replace-with-a-long-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
PASSWORD_MIN_LENGTH=8
SECRETS_BACKEND=disabled
AWS_REGION=us-east-1
SSM_PROVIDER_KEY_PREFIX=/ai-series-studio/providers
```

`AUTH_JWT_SECRET` and `AUTH_TOKEN_EXPIRES_MINUTES` are accepted only as
backward-compatible aliases. New deployments should use the `JWT_*` names
shown above. Never commit real JWT secrets.

## Billing Status

Stripe test-mode checkout and webhook credit fulfillment are implemented. The
app refuses checkout unless `STRIPE_TEST_MODE=true`, the secret key is a
`sk_test_...` key, and the credit price id is configured. Live payments are
always disabled, card data is never stored, and webhook fulfillment is
idempotent.

```http
GET /api/billing/status
```

The billing config helper reports whether safe test-mode env vars are
configured without returning secret values. The Settings page shows the Stripe
test metering status. Leave billing disabled locally unless you are explicitly
testing Stripe:

```bash
STRIPE_TEST_MODE=false
STRIPE_SECRET_KEY=
STRIPE_CREDIT_PRICE_ID=
STRIPE_WEBHOOK_SECRET=
STRIPE_CREDIT_PACK_CREDITS=500
BILLING_SUCCESS_URL=http://localhost:3000/billing/success
BILLING_CANCEL_URL=http://localhost:3000/billing/cancel
```

No real credentials are committed.

Checkout and webhook endpoints:

```http
POST /api/billing/create-checkout-session
POST /api/billing/webhook
```

Checkout metadata includes `user_id`, `credits`, and `environment=test`.
`checkout.session.completed` webhooks add credits to the matching user wallet,
write `billing_events` and `credit_events`, and ignore duplicate event/session
delivery.

## Credit Wallet

MVP credit ownership is implemented without Stripe checkout or webhooks. Each
user record stores available, reserved, and used credits. Local/demo mode uses
the seeded `user-demo` wallet.

```http
GET /api/credits/status
```

Response shape:

```json
{
  "user_id": "user-demo",
  "credits_available": 250,
  "credits_reserved": 0,
  "credits_used": 0,
  "currency": "credits"
}
```

Server-side credit guards protect expensive mock generation actions before
work starts. Successful actions deduct credits and write safe `credit_events`
metadata for admin visibility. Failed or blocked actions do not deduct credits.

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
python -m pytest tests/test_provider_layer.py tests/test_phase2b_llm.py tests/test_auth_helpers.py tests/test_credit_utils.py tests/test_billing_utils.py
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

Completed:

- Mock MVP workflow.
- Creative Quality Engine.
- Provider architecture.
- Real LLM gated behind `USE_REAL_LLM_PROVIDER`.
- Character drag handles in Cast view.
- Scene and segment reorder.
- Safe delete / Undo delete.
- Recently Deleted admin panel.
- Background purge scheduler.
- Developer reproducibility.
- Stripe test-mode readiness gate.

Still remaining before paid MVP:

- Production auth/user ownership hardening.
- Real credit wallet tied to users and Stripe fulfillment.
- Stripe checkout/session creation and webhooks.
- Real Image provider.
- Real Video provider.
- Real Voice provider.
- Real Music provider.
- Real Export / FFmpeg worker.
- Asset storage.
- Public sharing.
- Multi-tenant teams.
- Versioned scene revisions.

Auth and project ownership must stay ahead of real Stripe checkout/webhook work
because billing and credits need a reliable user owner.

## Useful Paths

- Backend API: `backend/server.py`
- Provider layer: `backend/providers/`
- Creative quality helpers: `backend/creative_quality.py`
- Frontend app: `frontend/src/`
- Studio tabs: `frontend/src/pages/tabs/`
- Shared studio UI: `frontend/src/components/studio/`
