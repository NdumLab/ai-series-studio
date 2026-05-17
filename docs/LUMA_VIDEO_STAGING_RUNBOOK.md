# Luma Video Staging Runbook

## Purpose

This runbook describes how to safely test one controlled real Luma Ray /
Dream Machine 5-second video segment later in staging or private beta. Do not
enable real video mode until the checklist is complete. Do not run bulk video
generation during the first activation pass.

## What Is Already Implemented

- `backend/providers/video_luma.py` implements the guarded Luma video provider.
- The provider supports `provider_name=luma` and documented models such as `ray-2`.
- Scene video generation can use `scene.image_url` for image-to-video when it
  exists.
- If there is no scene image URL, the provider can fall back to text-to-video
  from `enhanced_video_prompt` or `visual_prompt`.
- Real video calls are guarded by feature flag, effective provider selection,
  server-side secret presence, user credits, segment/project duration caps,
  asset storage, and provider activity logging.
- Successful real videos are stored through the asset storage layer and
  recorded in the `assets` collection with `asset_type=video_segment`.
- Segment records are updated with the stored `video_url`.
- Failed real video calls do not deduct credits.
- Video provider status exposes selected provider/model, feature flag state,
  secrets backend, key presence, real capability, and ready/blocked/mock state.
- Voice, music, and export providers remain mock-only.
- No frontend API key inputs exist.
- Controlled real video activation has been validated for one initial
  5-second segment and one Expand Next 5 Seconds segment. Real video remains
  disabled by default after tests.

## Required Environment

Set these on the backend runtime only:

```bash
SECRETS_BACKEND=ssm
AWS_REGION=us-east-1
SSM_PROVIDER_KEY_PREFIX=/ai-series-studio/providers
USE_REAL_VIDEO_PROVIDER=true
VIDEO_REAL_PROVIDER=luma
VIDEO_REAL_MODEL=ray-2
VIDEO_SEGMENT_SECONDS=5
VIDEO_MAX_SEGMENTS_PER_SCENE=3
VIDEO_MAX_PROJECT_SECONDS=60
```

Required SSM SecureString path:

```text
/ai-series-studio/providers/video/luma/api-key
```

Recommended staging settings:

```bash
AUTH_ENABLED=true
AUTH_DEMO_MODE=false
STRIPE_TEST_MODE=true
ASSET_STORAGE_BACKEND=local
ASSET_LOCAL_DIR=./generated_assets
ASSET_PUBLIC_BASE_URL=http://localhost:8000/assets
```

Use S3/R2 only after production object storage is implemented and validated for
the environment. Do not put Luma keys in `.env`, MongoDB, frontend code,
browser storage, logs, or committed files.

## Enable Real Video Mode

1. Store the Luma API key in AWS SSM Parameter Store as a SecureString at
   `/ai-series-studio/providers/video/luma/api-key`.
2. Ensure the backend instance role can read that SSM path with decryption.
3. Set `SECRETS_BACKEND=ssm`.
4. Set `USE_REAL_VIDEO_PROVIDER=true`.
5. Set `VIDEO_REAL_PROVIDER=luma` and `VIDEO_REAL_MODEL=ray-2`.
6. Keep `VIDEO_SEGMENT_SECONDS=5`.
7. Restart the backend.
8. In Settings or project provider overrides, select `luma` and model `ray-2` for
   video.

## Disable Real Video Mode Quickly

1. Set `USE_REAL_VIDEO_PROVIDER=false`.
2. Restart the backend.
3. Confirm `/api/providers/video/status` returns mock or blocked instead of
   ready.
4. Generate one video segment and verify the response uses a mock video URL.

## Verify Provider Status

Check provider status:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/providers/video/status?project_id=<project_id>"
```

Expected staging signal when configured:

- `selected_provider=luma`
- `selected_model=ray-2`
- `feature_flag_enabled=true`
- `secrets_backend=ssm`
- `key_present=true`
- `real_capable=true`
- `would_use_real_provider=true`
- `status=ready`

The response must not include the secret value.

## Staging Checklist

- [ ] MongoDB is running.
- [ ] FastAPI is running.
- [ ] Test user has enough credits for one `video_segment`.
- [ ] Selected effective video provider is `luma`.
- [ ] `/api/providers/video/status` shows `key_present=true`.
- [ ] `/api/providers/video/status` shows `real_capable=true`.
- [ ] Scene has an `image_url` if image-to-video is used.
- [ ] Asset storage backend is available.
- [ ] Project video duration is below `VIDEO_MAX_PROJECT_SECONDS`.
- [ ] Scene segment count is below `VIDEO_MAX_SEGMENTS_PER_SCENE`.
- [ ] No bulk generation is enabled.
- [ ] Provider Activity and credit event views are available to an admin
      tester.
- [ ] Voice, music, and export remain mock-only.
- [ ] No frontend API key inputs are visible.

## Dry Readiness Pass Before Enabling

Run this pass while `USE_REAL_VIDEO_PROVIDER=false`. It should make no real
Luma calls and should not generate video.

1. Check video provider status:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/providers/video/status?project_id=<project_id>"
```

Expected dry signal:

- `selected_provider=luma`
- `selected_model=ray-2`
- `feature_flag_enabled=false`
- `would_use_real_provider=false`
- `real_capable=true`
- `mode=mock`
- `status=mock` or `blocked`
- `secret_ref=/ai-series-studio/providers/video/luma/api-key`

2. Confirm the dry test project has exactly one prepared scene with:
   - `image_url` if testing image-to-video later
   - `enhanced_video_prompt`
   - zero or few existing video segments
   - project video duration below `VIDEO_MAX_PROJECT_SECONDS`
   - scene segment count below `VIDEO_MAX_SEGMENTS_PER_SCENE`
3. Confirm the scene image URL is publicly served from `ASSET_PUBLIC_BASE_URL`.
4. Confirm `GET /api/credits/status` shows at least one `video_segment` cost
   available.
5. Confirm `backend/generated_assets/` is ignored by git.
6. Confirm no bulk generation or Expand Next 5 Seconds test is planned for the
   first real activation.

## Test One 5-Second Video Segment

1. Create or open a single test project.
2. Create or split scenes.
3. Generate or assign one scene image first if testing image-to-video.
4. Pick one scene only.
5. Record current credits from `GET /api/credits/status`.
6. Confirm the scene has no existing video segments.
7. Generate one initial 5-second segment from the Video Segments tab or:

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/scenes/<scene_id>/segments"
```

Expected:

- Response keeps the existing segment shape.
- `duration=5`.
- `generation_mode=real`.
- `provider_name=luma`.
- `provider_job_id` is present if Luma returned one.
- `video_url` points to configured asset storage.
- Scene status becomes `video_ready`.
- Exactly one video segment cost is deducted.

Do not use Expand Next 5 Seconds during the first real test.

## Test One Expand Next 5 Seconds Segment

Run this only after one initial real 5-second segment exists and real video
mode is deliberately enabled for the controlled test.

1. Record current credits from `GET /api/credits/status`.
2. Confirm the scene has exactly one previous segment to extend.
3. Confirm the previous segment has:
   - `provider_name=luma`
   - `provider_job_id` present
   - `video_url` pointing to a served MP4 asset
4. Generate exactly one expansion:

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"continuity_prompt":"Continue the shot for the next five seconds."}' \
  "http://localhost:8000/api/scenes/<scene_id>/expand"
```

Expected:

- `duration=5`.
- `generation_mode=real`.
- `provider_name=luma`.
- `provider_job_id` is present.
- `parent_segment_id` points to the previous segment.
- `start_second` equals the previous segment end time.
- `expand_mode=expand`.
- `video_url` points to configured asset storage.
- Exactly one video segment cost is deducted after the expanded MP4 is stored.

After the test, immediately roll back `USE_REAL_VIDEO_PROVIDER=false`, restart
the backend, and verify `/api/providers/video/status` reports mock mode.

## Verify Asset Storage

For local storage:

1. Confirm returned `video_url` begins with `ASSET_PUBLIC_BASE_URL`.
2. Open the returned `video_url` in a browser or with `curl`.
3. Confirm a matching `assets` record exists with:
   - `asset_type=video_segment`
   - `storage_backend=local`
   - `provider_name=luma`
   - `provider_job_id` if Luma returned one
   - `mime_type=video/mp4`
   - `size_bytes > 0`

Raw video bytes must be stored on disk or future object storage, not in
MongoDB.

## Verify Credit Deduction

1. Call `GET /api/credits/status` before generation.
2. Generate exactly one 5-second segment.
3. Call `GET /api/credits/status` after generation.
4. Confirm `credits_available` decreased by `COSTS["video_segment"]`.
5. Confirm `credits_used` increased by the same amount.
6. Confirm a `credit_events` row exists with operation `video_segment`.
7. Confirm no credits are deducted if the provider fails before asset storage.

## Verify Provider Activity Logging

Open Admin Provider Activity or inspect the `provider_activity` collection.

Expected success row:

- `modality=video`
- `provider_name=luma`
- `model_name=ray-2`
- `mode=real`
- `status=success`
- `estimated_credits=12`
- `provider_job_id` present if Luma returned one
- `duration_ms` present
- `key_present=true`

Expected failure/blocked row:

- `modality=video`
- `provider_name=luma`
- `status=failed` or `blocked`
- no secret value
- no raw video bytes
- no raw provider payload

## Cost Safety Notes

- Start with only one 5-second segment.
- Do not use Expand Next 5 Seconds during the first real test.
- Do not bulk generate scenes.
- Watch `provider_activity`.
- Watch `credit_events`.
- Record actual provider cost externally if Luma exposes it.
- Stop immediately if latency or cost is unexpected.
- Keep the test cohort to one internal admin and one test user until cost and
  failure behavior are reviewed.

## Rollback To Mock Mode

1. Set `USE_REAL_VIDEO_PROVIDER=false`.
2. Restart the backend.
3. Confirm:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/providers/video/status?project_id=<project_id>"
```

Expected rollback signal:

- `feature_flag_enabled=false`
- `would_use_real_provider=false`
- `mode=mock`
- `status=mock` or `blocked`

4. Generate one mock segment and confirm `video_url` uses one of the mock video
   URLs.
5. Confirm no new real Luma provider activity rows are created after rollback.

Rollback should not affect real LLM behavior, real image behavior, Stripe test
mode, existing stored video assets, or mock voice/music/export behavior.
