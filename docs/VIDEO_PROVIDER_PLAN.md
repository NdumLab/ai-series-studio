# Real Video Provider Integration Plan

## Purpose

This plan designs the safest path for adding the first real video provider
later. It does not implement a real video provider and does not enable real
video calls. The future integration must follow the same guard pattern already
used for real image generation: feature flag, server-side SSM secret, credit
guardrails, generated asset storage, provider activity logging, and disabled by
default.

## Current Video Workflow

The current Video Segments tab is mock-first:

- Scenes are created from the story workflow.
- Each scene can generate an initial 5-second video segment.
- Each segment can be approved, rejected, deleted, or regenerated.
- Users can expand a scene with "Expand Next 5 Seconds".
- Segment order can be rearranged with drag handles.
- `start_second` is recomputed from segment order and duration.
- Project/scene cost widgets include video segment cost.
- Provider activity records safe metadata only.
- Disabled-by-default video provider guard foundation exists. Provider status
  recognizes Luma, Runway, OpenAI/Sora, and fal.ai video providers, but no real
  video provider class or network call exists yet.
- Mock segment creation and expansion enforce configured segment/project
  duration caps before credits are deducted.

Current mock video segment behavior:

- `POST /api/scenes/{scene_id}/segments` creates a mock segment using
  `VIDEO_SEGMENT_SECONDS`.
- `POST /api/scenes/{scene_id}/expand` creates the next mock
  segment with `parent_segment_id`, `expand_mode="expand"`, and a continuity
  prompt.
- `POST /api/segments/{segment_id}/regenerate` keeps the segment record but
  swaps the mock video URL.
- Mock video URLs come from static public sample videos.
- Credits are checked before generation and deducted only after successful mock
  generation.

## Expand Next 5 Seconds Behavior

Future real provider expansion must preserve the existing data contract:

- Initial segment: `expand_mode="initial"`, `start_second=0`, duration from
  `VIDEO_SEGMENT_SECONDS`.
- Expanded segment: `expand_mode="expand"`, `parent_segment_id` points to the
  previous segment, and `start_second` equals the end of the previous ordered
  segment.
- Segment duration defaults to `VIDEO_SEGMENT_SECONDS`.
- Expand should use the parent segment asset or provider job id when the
  selected provider supports continuation.
- If the provider cannot extend a previous clip, expansion must be blocked or
  clearly marked as a new generation rather than silently breaking continuity.

## Provider Requirements

The first real video provider should support:

- Image-to-video from an approved scene image.
- Short clip generation around 5 seconds.
- Continuation or extension from a previous generated clip.
- Polling or webhook-compatible job status.
- Downloadable final video asset.
- Clear failed/cancelled job states.
- Backend-only API key usage.
- Predictable cost controls.
- Commercial usage terms suitable for a private beta.

## Provider Comparison

| Provider | API Maturity | Image-to-Video | Extension | 5s Clips | Cost Model | Speed | Quality | Commercial Fit | Ease | Failure/Retry |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Luma Ray | Dedicated API docs for text-to-video, image-to-video, generation status, and extend. | Strong fit; Ray 2 docs include image-to-video. | Strong fit; docs include extend and reverse extend using generated video ids. | Strong fit; docs show `duration: "5s"`. | Request/generation based; provisioned throughput exists for scale. | Good for short clips; async jobs still require polling. | Strong cinematic motion and camera control. | Good for creative-product private beta. | Best first fit for current segment model. | Poll generation status; retry failed jobs explicitly. |
| Runway | Mature API surface with image-to-video, text-to-video, video-to-video, uploads, task detail, and cancel/delete. | Strong fit. | Possible through video-to-video/edit style flows, but extension semantics are less directly aligned with current Expand Next 5 Seconds model. | Likely supported by model settings, but app-specific duration mapping must be validated. | Credit/task based. | Good, but task latency varies. | Strong creative quality. | Good, established creative tooling. | Medium; broader API surface to normalize. | Task status/cancel endpoints help operational control. |
| Sora/OpenAI video | Official Videos API supports prompts, image references, video extension, content download, and batch jobs. | Strong fit. | Strong API fit, but docs currently note Sora 2/Videos API deprecation with a shutdown date. | Docs examples show seconds values such as 8; 5s support must be verified against current model constraints. | Potentially high generated-video cost. | Strong but expensive. | Very high. | Risky until product/API continuity is clearer. | Medium because OpenAI SDK patterns are familiar, but platform risk is high. | Job management and content download are documented. |
| fal.ai-hosted video models | Broad model marketplace and documented video model APIs. | Depends on selected model. | Depends on selected model; continuation support varies. | Depends on selected model. | Model-specific; can be hard to normalize. | Often fast depending on model and queue. | Varies widely by model. | Good for experimentation. | Higher integration risk because each model has distinct schema and output. | Queue/status behavior varies by model. |

Sources reviewed:

- Luma API and video generation docs: `https://lumalabs.ai/api/`,
  `https://docs.lumalabs.ai/docs/video-generation`
- Runway API reference: `https://docs.dev.runwayml.com/api/`
- OpenAI video generation guide: `https://platform.openai.com/docs/guides/video-generation`
- fal.ai model API reference: `https://fal.ai/docs/model-api-reference`

## Recommendation

Recommended first MVP video provider: **Luma Ray**.

Reasoning:

- Luma best matches the existing app shape: scene image -> 5-second video
  segment -> Expand Next 5 Seconds.
- Luma docs explicitly cover image-to-video, 5-second duration, generation
  status, and extension from generated video ids.
- The provider job model maps cleanly to future polling and asset download.
- It avoids OpenAI Sora platform/deprecation risk for the first MVP video path.
- It is narrower and more predictable than choosing a fal.ai marketplace model
  before the app has one stable video integration.

Runway is the strongest second candidate if Luma quality, cost, or reliability
does not fit. Sora/OpenAI video should be re-evaluated later because its API
capability is strong, but current deprecation/platform-risk notes make it a
poor first MVP dependency.

## Feature Flag Design

Required disabled-by-default envs:

```bash
USE_REAL_VIDEO_PROVIDER=false
VIDEO_REAL_PROVIDER=luma
VIDEO_REAL_MODEL=ray
VIDEO_SEGMENT_SECONDS=5
VIDEO_MAX_SEGMENTS_PER_SCENE=3
VIDEO_MAX_PROJECT_SECONDS=60
```

Runtime rules:

- `USE_REAL_VIDEO_PROVIDER=false` always uses mock video.
- Real video can run only when the effective provider is allowlisted.
- `VIDEO_SEGMENT_SECONDS` controls initial and expanded segment duration.
- `VIDEO_MAX_SEGMENTS_PER_SCENE` blocks runaway expand loops.
- `VIDEO_MAX_PROJECT_SECONDS` blocks project-wide overspend.
- Current mock generation already enforces the segment and project duration
  limits and returns `Video segment limit reached for this MVP.` when blocked.
- `/api/providers/video/status` returns selected provider/model, feature flag
  state, secrets backend, key presence, `real_capable`, and `status` values.
- Feature flag changes require backend restart unless runtime config hot-reload
  is explicitly implemented later.

## Secrets Design

Use the existing backend-only secrets resolver. Do not store video provider
keys in MongoDB, frontend code, browser storage, logs, provider settings, or
committed files.

Likely SSM SecureString paths:

```text
/ai-series-studio/providers/video/luma/api-key
/ai-series-studio/providers/video/runway/api-key
/ai-series-studio/providers/video/openai/api-key
/ai-series-studio/providers/video/fal/api-key
```

Provider status should expose only safe metadata:

- selected provider/model
- `feature_flag_enabled`
- `secrets_backend`
- `key_present`
- `real_capable`
- `status`

It must never return a secret value.

## Credit And Cost Design

Initial app-credit rules:

- Initial video segment generation: use `COSTS["video_segment"]`.
- Expand Next 5 Seconds: same cost as one video segment.
- Regeneration: same cost as one video segment.
- Provider failure: no credit deduction.
- Provider timeout: no credit deduction; log failure.
- User cancellation before provider completion: no deduction unless the
  provider has already produced a usable asset.
- Successful real video: deduct only after the video asset is stored and the
  segment record points to the stored asset URL.
- Mock fallback after failed real provider should not happen automatically for
  real mode, because it can hide provider failures and confuse cost auditing.

Before provider call:

- Check authenticated user credits.
- Check scene segment count against `VIDEO_MAX_SEGMENTS_PER_SCENE`.
- Check project duration against `VIDEO_MAX_PROJECT_SECONDS`.
- Check scene/project ownership.
- Check source image availability for image-to-video.

Future queued job option:

- Reserve credits before submitting a long-running provider job.
- Deduct reserved credits only after successful asset storage.
- Release reserved credits on failed, timed-out, blocked, or cancelled jobs.

## Storage Requirements

Real video output must be stored outside MongoDB:

- Download provider output once the job completes.
- Save bytes through `backend/storage_service.py`.
- Create an `assets` record with `asset_type=video_segment`.
- Store `provider_name`, `provider_job_id`, `mime_type`, `size_bytes`,
  `storage_backend`, `storage_key`, and durable URL.
- Update segment `video_url` to the stored asset URL.
- Raw video bytes must not be stored in MongoDB.

Local storage is acceptable for local/staging smoke tests. S3/R2 should be
implemented before broad private beta video generation.

## Backend API Design

Future implementation modules:

- `backend/providers/video_luma.py`
- Optional shared `backend/providers/video_base.py` if more providers follow.

Provider result shape:

- `modality="video"`
- `provider_name`
- `model_name`
- `mode="real"`
- `status="success" | "failed" | "blocked" | "cancelled" | "timeout"`
- `estimated_credits`
- `provider_job_id`
- `output={"video_bytes": ..., "mime_type": "video/mp4", "duration": 5}`
- `error`
- `message`
- safe `meta` with duration, provider status, and timing only

Endpoint behavior:

- `POST /api/scenes/{scene_id}/segments`
  - Use source scene image for image-to-video when real mode is ready.
  - Submit provider job.
  - Poll until completion or timeout, or persist pending job if async jobs are
    introduced.
  - Store completed video asset.
  - Create segment and deduct credits after successful storage.
- `POST /api/scenes/{scene_id}/segments/expand`
  - Use previous segment provider job id or stored video asset as continuation
    source.
  - Enforce max segment and project duration limits.
  - Preserve `parent_segment_id`, `expand_mode`, `duration`, and `start_second`.
- `POST /api/segments/{segment_id}/regenerate`
  - Replace the segment video asset only after the new provider job succeeds.
  - Keep old asset URL until replacement succeeds.
- Future polling path if needed:
  - `provider_jobs` collection or generation record with provider job id,
    status, operation, user/project/scene/segment ids, estimated credits, and
    reservation state.

Failure handling:

- Fail closed on missing flag, key, provider mismatch, or insufficient credits.
- Do not deduct credits on failed provider jobs.
- Log provider activity for success, failure, blocked, timeout, and cancelled.
- Do not log prompts, raw provider payloads, raw video data, or secrets.

## Frontend UX Plan

Video Segments tab should show:

- real/mock mode
- provider/model
- estimated credits per 5-second segment
- max allowed segments per scene
- max project seconds
- current project video duration
- generation progress state
- failed state with retry/regenerate action
- insufficient credits warning
- approval/rejection flow
- continuity prompt for expansion

Real mode should avoid surprise behavior:

- Disable duplicate submits while a job is pending.
- Keep the previous approved segment visible during regeneration.
- Show clear error if source scene image is missing.
- Show clear error if max segment/project duration is reached.
- Show clear error if provider key is missing.

## Tests Needed

Backend tests:

- real video blocked when `USE_REAL_VIDEO_PROVIDER=false`
- real video blocked when key is missing
- video status endpoint/readiness includes Luma provider fields
- real video blocked when selected provider is not allowlisted
- insufficient credits block before provider call
- missing scene image blocks image-to-video real call
- max segments per scene blocks expand
- max project seconds blocks generation
- successful mocked provider response saves `video_segment` asset metadata
- successful real generation updates segment `video_url`
- failed provider does not deduct credits
- timeout does not deduct credits
- user cancellation releases reservation if reservations are implemented
- Expand Next 5 Seconds uses parent segment/provider job context
- segment `duration` and `start_second` are correct after initial, expand, and
  reorder
- provider activity logs success/failure/blocked without secrets or raw video
- no real network calls in unit tests

Frontend checks:

- provider hint shows video provider/model and credits
- generation buttons show pending/failed state
- insufficient credits toast appears
- max segment warning appears
- previous video remains visible after failed regenerate

## Rollback Plan

Rollback must be one env change:

1. Set `USE_REAL_VIDEO_PROVIDER=false`.
2. Restart backend.
3. Verify `/api/providers/video/status` returns mock/blocked and
   `would_use_real_provider=false`.
4. Generate one video segment and confirm the mock video URL path works.

Rollback should not affect:

- real LLM behavior
- real image behavior
- Stripe test mode
- existing stored video assets

## Private Beta Test Plan

Start narrow:

1. One internal admin.
2. One test user.
3. One project.
4. One scene with one approved real image.
5. One initial 5-second video segment.
6. One Expand Next 5 Seconds call.
7. One regeneration.

Before increasing scope:

- Confirm provider activity success/failure rate.
- Confirm `credit_events` match generated assets.
- Confirm internal provider cost per successful 5-second segment.
- Confirm no bulk generation path exists.
- Confirm max segment and max project duration limits work.
- Confirm rollback to mock mode works.

## Non-Goals

- No real video provider class in this pass.
- No real video API calls.
- No voice, music, or export provider work.
- No frontend API key inputs.
- No Stripe changes.
- No real LLM or real image behavior changes.
