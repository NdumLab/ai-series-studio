# Real Image Provider Integration Plan

## Purpose

This plan prepares AI Series Studio for real image generation without enabling
real provider calls yet. Image, Video, Voice, Music, and Export must remain
mock-only until secrets, cost controls, tests, and rollout gates are in place.

## Current Architecture Review

Current provider flow:

- `backend/providers/resolver.py` resolves provider/model using project
  override, global settings, then hard fallback.
- `backend/providers/executor.py` is the central execution guard. It reads
  feature flags, checks `key_present_for_modality`, runs the mock provider, and
  records safe provider activity metadata.
- `backend/providers/keys.py` only permits real-key detection for LLM today.
  Every non-LLM modality, including image, returns `False`.
- `backend/server.py` registers provider activity logging with a strict
  allowlist: modality, provider/model, source, mode, status, estimated credits,
  job id, duration, project/scene/segment ids, feature flag state, and
  key-present state. Prompts, raw outputs, and keys are not logged.
- `generate_image` checks user credits before work and deducts credits only
  after successful generation.

Current safety state:

- `USE_REAL_IMAGE_PROVIDER=true` alone cannot call a real image provider.
- A missing key makes provider status show blocked/mock.
- The frontend has no provider API key inputs.
- Provider settings store provider/model choices only.
- Credits are user-owned and enforced server-side.

## Provider Comparison

| Provider | Quality | API Complexity | Cost Model | Speed | Commercial Fit | Character Consistency | Integration Risk |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OpenAI `gpt-image-1` | High fidelity and strong prompt following; supports text/image input and image output. | Low for this repo because OpenAI-style provider concepts already exist around LLM settings. | Token/image based; official docs list per-image examples and token pricing, so map to fixed app credits per output first. | Slower than some lighter providers. | Strong, with safety systems and broad product support. | Good with reference image workflows, but explicit multi-character consistency workflow is less central than Gemini's docs. | Low to medium. Main risk is cost and latency. |
| Gemini Nano Banana family | Strong image generation and editing. Google docs emphasize conversational image work, reference images, character consistency workflows, and SynthID watermarking. | Medium. Requires Google client or REST path and response parsing for image parts. | Token based by generated size/model. | Gemini 2.5 Flash Image is optimized for speed; newer preview models balance quality/cost/latency. | Strong, but preview model stability and API naming may shift. | Best documented character-consistency story among the compared options. | Medium. Model names and preview status increase change risk. |
| fal.ai image models | Broad model marketplace with fast inference choices and many specialized models. | Medium to high because each model can have different request/response and pricing behavior. | Per image, per megapixel, or fallback GPU-time billing depending on model. | Often fast, depending on model and queue. | Good for experimentation and specialized styles. | Depends on selected model; may require ControlNet/IP-adapter/reference-image model choice. | Medium to high. Provider abstraction must normalize many model-specific shapes. |

Sources reviewed:

- OpenAI model documentation: `https://developers.openai.com/api/docs/models/gpt-image-1`
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

Rules:

- Do not store provider keys in MongoDB.
- Do not store provider keys in frontend code or browser storage.
- Do not commit provider keys.
- Do not use plain `.env` for production provider keys.
- Store only secret references or provider/model selections in the database.

Local/test placeholders only:

```bash
USE_REAL_IMAGE_PROVIDER=false
IMAGE_REAL_PROVIDER=openai
IMAGE_REAL_MODEL=gpt-image-1
OPENAI_IMAGE_API_KEY=
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

Implementation outline for a future code pass:

- Add `backend/providers/image_real.py`.
- Add a `RealImageProvider` class with a `run(prompt, aspect_ratio,
  reference_image_url, output_kind, safety_context)` method.
- Use `ProviderResult`:
  - `modality="image"`
  - `mode="real"`
  - `status="success" | "failed" | "blocked"`
  - `provider_job_id`
  - `output={"image_url": ..., "asset_id": ..., "mime_type": ...}`
  - `error`
  - `meta={"duration_ms": ..., "image_kind": "scene" | "character"}`
- Extend `keys.key_present_for_modality("image", provider)` to check only
  server-side resolved secrets.
- Extend `execute_provider` with a real image branch, but keep mock fallback
  explicit and test-covered.
- Keep `POST /api/scenes/{scene_id}/generate-image` as the first real image
  endpoint.
- Add a later character endpoint only when character image UX is ready, for
  example `POST /api/characters/{character_id}/generate-image`.

The future implementation must not return secret values, raw provider request
payloads, or unfiltered provider metadata to the frontend.

## Storage Gate

Do not rely on temporary provider URLs for launch. Before real image is enabled,
choose one:

- Local development: store mock/real test output under a local dev asset path.
- Production: store generated images in S3 or R2 and save only durable asset
  URLs/references in MongoDB.

For MVP production, S3/R2 storage should happen before enabling broad private
beta image generation.

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
3. Add real image provider class behind unit-test mocks.
4. Add storage abstraction for generated images.
5. Enable in a local/staging test environment with fake or test provider client.
6. Run capped private beta with low per-user credits.
7. Review provider activity, failure rate, and cost per generated image.

## Non-Goals For This Pass

- No real image provider code.
- No real image API calls.
- No video, voice, music, or export provider work.
- No frontend API key fields.
- No secrets stored in MongoDB.
