# Real Image Provider Integration Plan

## Purpose

This plan tracks the guarded OpenAI image integration. OpenAI GPT Image support
now exists for scene and character images, but it remains disabled by default
and cannot run unless all feature flag, secret, credit, storage, and provider
activity gates pass. Video, Voice, Music, and Export must remain mock-only
until their own plans and gates are in place.

## Current Architecture Review

Current provider flow:

- `backend/providers/resolver.py` resolves provider/model using project
  override, global settings, then hard fallback.
- `backend/providers/executor.py` is the central execution guard. It reads
  feature flags, checks `key_present_for_modality`, runs real OpenAI image only
  when the image gates pass, otherwise runs the mock provider, and records safe
  provider activity metadata.
- `backend/providers/keys.py` preserves LLM runtime detection and routes
  non-LLM key checks through the backend-only secrets resolver.
- `backend/providers/image_openai.py` implements the first real image provider
  for OpenAI GPT Image models.
- `backend/server.py` registers provider activity logging with a strict
  allowlist: modality, provider/model, source, mode, status, estimated credits,
  job id, duration, project/scene/segment ids, feature flag state, and
  key-present state. Prompts, raw outputs, and keys are not logged.
- `generate_image` and `generate_character_image` check user credits before
  work and deduct credits only after successful generation.

Current safety state:

- `USE_REAL_IMAGE_PROVIDER=true` alone cannot call a real image provider.
- A missing key makes provider status show blocked/mock.
- The frontend has no provider API key inputs.
- Provider settings store provider/model choices only.
- Credits are user-owned and enforced server-side.
- Successful real image bytes are saved through asset storage and represented
  by `assets` metadata records; raw binary data is not stored in MongoDB.

## Provider Comparison

| Provider | Quality | API Complexity | Cost Model | Speed | Commercial Fit | Character Consistency | Integration Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI `gpt-image-1` | High fidelity and strong prompt following; supports text/image input and image output. | Low for this repo because OpenAI-style provider concepts already exist around LLM settings. | Token/image based; official docs list per-image examples and token pricing, so map to fixed app credits per output first. | Slower than some lighter providers. | Strong, with safety systems and broad product support. | Good with reference image workflows, but explicit multi-character consistency workflow is less central than Gemini's docs. | Low to medium. Main risk is cost and latency. |
| Gemini Nano Banana family | Strong image generation and editing. Google docs emphasize conversational image work, reference images, character consistency workflows, and SynthID watermarking. | Medium. Requires Google client or REST path and response parsing for image parts. | Token based by generated size/model. | Gemini 2.5 Flash Image is optimized for speed; newer preview models balance quality/cost/latency. | Strong, but preview model stability and API naming may shift. | Best documented character-consistency story among the compared options. | Medium. Model names and preview status increase change risk. |
| fal.ai image models | Broad model marketplace with fast inference choices and many specialized models. | Medium to high because each model can have different request/response and pricing behavior. | Per image, per megapixel, or fallback GPU-time billing depending on model. | Often fast, depending on model and queue. | Good for experimentation and specialized styles. | Depends on selected model; may require ControlNet/IP-adapter/reference-image model choice. | Medium to high. Provider abstraction must normalize many model-specific shapes. |

Sources reviewed:

- OpenAI image generation guide: `https://platform.openai.com/docs/guides/image-generation`
- OpenAI model documentation: `https://platform.openai.com/docs/models/gpt-image-1`
- OpenAI image API reference: `https://platform.openai.com/docs/api-reference/images`
- Gemini image generation docs: `https://ai.google.dev/gemini-api/docs/image-generation`
- fal.ai pricing docs: `https://fal.ai/docs/documentation/model-apis/pricing`

## Recommendation

Recommended first MVP provider: **OpenAI `gpt-image-1`**.

Reasoning:

- It is the lowest-risk first provider for this codebase because real LLM
  gating already uses OpenAI-compatible concepts and the provider catalog
  already includes `openai-image`.
- It supports prompt-based scene image generation and image-input workflows for
  future character/reference consistency.
- It has straightforward server-side key handling and clean error handling.
- It is commercially suitable for an MVP when guarded by test credits, per-user
  credits, and low generation limits.

Planned follow-up: evaluate Gemini Nano Banana as the second provider after the
OpenAI path proves the storage, approval, and credit flows. Gemini is promising
for character consistency, but the first production seam should be conservative.

## Secrets Strategy

Current implementation status:

- `backend/secrets_resolver.py` exists.
- Default `SECRETS_BACKEND=disabled` returns safe `not_configured`.
- `SECRETS_BACKEND=ssm` attempts AWS SSM Parameter Store lookup and fails
  closed if AWS SDK/configuration/parameter lookup is unavailable.
- Secret values are never returned to provider status responses, provider
  activity, MongoDB provider settings, or frontend code.
- The OpenAI image provider can read the secret backend-side only when
  `SECRETS_BACKEND=ssm` and the expected parameter exists.

Rules:

- Do not store provider keys in MongoDB.
- Do not store provider keys in frontend code or browser storage.
- Do not commit provider keys.
- Do not use plain `.env` for production provider keys.
- Store only secret references or provider/model selections in the database.

Local/test placeholders only:

```bash
SECRETS_BACKEND=disabled
AWS_REGION=us-east-1
SSM_PROVIDER_KEY_PREFIX=/ai-series-studio/providers
USE_REAL_IMAGE_PROVIDER=false
IMAGE_REAL_PROVIDER=openai
IMAGE_REAL_MODEL=gpt-image-1
IMAGE_PROVIDER_SECRET_REF=
```

Production recommendation: **AWS SSM Parameter Store SecureString first**.

Why SSM first:

- Simpler operational model for a small MVP.
- Lower overhead than Secrets Manager for a small number of static provider
  secrets.
- Easy IAM-scoped reads by the backend task/instance role.
- Versioned parameters are enough for early rotation.

Use AWS Secrets Manager later if the product needs automatic rotation,
cross-account secret sharing, or a larger provider-secret lifecycle.

Production shape:

- Store `/ai-series-studio/prod/providers/openai-image/api-key` as
  SecureString.
- Set `IMAGE_PROVIDER_SECRET_REF` to that parameter name.
- Backend resolves the secret at runtime using IAM; the secret value never
  enters MongoDB or frontend responses.

Provider key naming convention:

- `/ai-series-studio/providers/image/openai/api-key`
- `/ai-series-studio/providers/image/gemini/api-key`
- `/ai-series-studio/providers/image/fal/api-key`
- `/ai-series-studio/providers/video/luma/api-key`
- `/ai-series-studio/providers/voice/elevenlabs/api-key`

## Feature Flag Gate

Real image execution must remain blocked unless all of these are true:

- `USE_REAL_IMAGE_PROVIDER=true`
- resolved image provider is enabled and allowlisted
- server-side image provider key is present
- user has enough available credits
- requested operation has an estimated cost
- request passes safety and cost checks
- provider call timeout is configured
- provider activity logging is active

If any gate fails:

- no real network call is made
- user credits are not deducted
- provider activity records `blocked` or `failed` with safe metadata only
- frontend gets a clear message and mock fallback remains available where
  intended

## Credit Cost Plan

Initial app-credit mapping:

- Character image generation: 2 credits
- Scene image generation: 2 credits
- Regenerate image: 2 credits
- Prompt enhancement: use existing rewrite/enhancement cost, not image cost
- Failed image provider call: 0 deducted credits
- Provider timeout: log failure, preserve credits, return clear error
- Successful real image generation: deduct credits after image asset is stored
  or a durable provider URL is confirmed

Before enabling video providers, image costs should be reviewed against real
provider spend and adjusted so one app credit has a stable internal value.

## Backend API Design

Current implementation:

- `backend/providers/image_openai.py` contains the guarded OpenAI GPT Image
  provider.
- `OpenAIImageProvider.run(...)` accepts a prompt and `image_kind` of `scene`
  or `character`.
- The provider returns a `ProviderResult` with:
  - `modality="image"`
  - `mode="real"`
  - `status="success" | "failed"`
  - `provider_job_id` when available
  - `output={"image_bytes": ..., "mime_type": "image/png", "image_kind": ...}`
  - `error`
  - `meta={"duration_ms": ..., "image_kind": ..., "size": ..., "quality": ...}`
- `keys.key_present_for_modality("image", provider)` checks only server-side
  resolved secrets.
- `execute_provider` has a real image branch for `openai-image` / `openai` and
  otherwise keeps mock fallback explicit and test-covered.
- Scene images use `POST /api/scenes/{scene_id}/generate-image`.
- Character images use `POST /api/characters/{character_id}/generate-image`.

The implementation must not return secret values, raw provider request
payloads, raw image bytes, or unfiltered provider metadata to the frontend.
The public response shape remains `image_url`, `cost`, and
`remaining_credits` for scenes; character image generation also returns
`reference_image_url`.

## Storage Gate

Current implementation status:

- `backend/storage_service.py` exists.
- `ASSET_STORAGE_BACKEND=local` is the default development mode.
- Local files are served through `GET /assets/{path}` by FastAPI when local
  mode is active.
- Mock image generation creates an `assets` metadata record for the selected
  external mock URL without downloading remote content.
- S3/R2 backend classes exist as explicit stubs and do not require credentials
  yet.
- Raw binary data is not stored in MongoDB.

Local/test placeholders only:

```bash
ASSET_STORAGE_BACKEND=local
ASSET_LOCAL_DIR=./generated_assets
ASSET_PUBLIC_BASE_URL=http://localhost:8000/assets
ASSET_S3_BUCKET=
ASSET_S3_REGION=us-east-1
ASSET_S3_PREFIX=ai-series-studio
ASSET_SIGNED_URL_EXPIRE_SECONDS=3600
```

Asset records use the `assets` collection with:

- `id`
- `user_id`
- `project_id`
- optional `scene_id`
- optional `segment_id`
- `asset_type`
- `storage_backend`
- `storage_key`
- `url`
- `mime_type`
- `size_bytes`
- `provider_name`
- `provider_job_id`
- `created_at`

Supported asset types:

- `character_image`
- `scene_image`
- `video_segment`
- `voice_audio`
- `music_audio`
- `export_video`

Do not rely on temporary provider URLs for launch. Before broad real image
enablement, choose one:

- Local development: store mock/real test output under a local dev asset path.
- Production: store generated images in S3 or R2 and save only durable asset
  URLs/references in MongoDB.

For MVP production, S3/R2 storage should happen before enabling broad private
beta image generation.

Current safety status:

- The real OpenAI image provider is connected but disabled by default.
- No real image API calls are made unless `USE_REAL_IMAGE_PROVIDER=true`, the
  selected provider is `openai-image` or `openai`, the server-side secret is
  present, user credits are sufficient, and storage succeeds.
- No real video, voice, music, or export providers are connected.
- No frontend API key inputs exist.
- No AWS credentials are committed or required for local storage mode.
- Stripe behavior is unchanged.
- Real LLM behavior is unchanged.

## Frontend UX Plan

Image tab should show:

- provider/model used
- real/mock status
- estimated credits
- generating state
- failure message from backend
- regenerate button
- image approval state if/when approval is added

The button should stay enabled in mock mode. In real mode, backend failures
should show a toast and leave the previous image intact.

## Tests Needed

Backend tests:

- real image blocked when `USE_REAL_IMAGE_PROVIDER=false`
- real image blocked when key is missing
- live key is never accepted from MongoDB or frontend payloads
- insufficient credits block image generation before provider execution
- failed provider does not deduct credits
- provider timeout does not deduct credits
- successful provider deducts credits after output is persisted
- provider activity logs success with safe metadata
- provider activity logs failure/blocked with safe metadata
- mock fallback remains working
- no real network calls in unit tests

Frontend tests/checks:

- Image tab shows mock/real status.
- Missing config shows a clear toast.
- Generation button cannot double-submit while busy.
- Existing image stays visible after provider failure.

## Rollout Plan

1. Add secrets resolver abstraction with SSM placeholder support.
2. Add image key-present checks, still returning false by default.
3. Add storage abstraction for generated images. Completed.
4. Add real OpenAI `gpt-image-1` provider class behind unit-test mocks.
   Completed.
5. Enable in a local/staging test environment with SSM test secret and capped
   credits.
6. Run capped private beta with low per-user credits.
7. Review provider activity, failure rate, and cost per generated image.

Operational staging details live in
[`docs/REAL_IMAGE_STAGING_RUNBOOK.md`](REAL_IMAGE_STAGING_RUNBOOK.md).
Real video planning lives in
[`docs/VIDEO_PROVIDER_PLAN.md`](VIDEO_PROVIDER_PLAN.md); video remains
mock-only.

## Non-Goals Still In Force

- No video, voice, music, or export provider work.
- No frontend API key fields.
- No secrets stored in MongoDB.
- No real image calls unless the runtime guard is explicitly configured.
