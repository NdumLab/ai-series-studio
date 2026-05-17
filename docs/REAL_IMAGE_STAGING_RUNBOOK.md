# Real Image Staging Runbook

## Purpose

This runbook describes how to enable and test the guarded OpenAI GPT Image
provider in a controlled staging or private-beta environment. Real image mode
must stay disabled by default and should only be enabled for a small, capped
test cohort.

## What Is Already Implemented

- `backend/providers/image_openai.py` implements the OpenAI GPT Image provider.
- Scene image generation can use `enhanced_image_prompt` or `visual_prompt`.
- Character image generation can use character name, description, and style.
- Real image calls are guarded by feature flag, provider selection, server-side
  secret presence, user credits, asset storage, and provider activity logging.
- Successful real images are saved through the asset storage layer and recorded
  in the `assets` collection.
- Failed real image calls do not deduct credits.
- Video, voice, music, and export providers remain mock-only.
- No frontend API key inputs exist.

## Required Environment

Set these on the backend runtime only:

```bash
SECRETS_BACKEND=ssm
AWS_REGION=us-east-1
SSM_PROVIDER_KEY_PREFIX=/ai-series-studio/providers
USE_REAL_IMAGE_PROVIDER=true
```

Required SSM SecureString path:

```text
/ai-series-studio/providers/image/openai/api-key
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

Use S3/R2 only after the production object-storage backend is implemented and
tested. Do not put OpenAI keys in `.env`, MongoDB, frontend code, browser
storage, or committed files.

## Enable Real Image Mode

1. Store the OpenAI image key in AWS SSM Parameter Store as a SecureString at
   `/ai-series-studio/providers/image/openai/api-key`.
2. Ensure the backend instance role can read that SSM path with decryption.
3. Set `SECRETS_BACKEND=ssm`.
4. Set `USE_REAL_IMAGE_PROVIDER=true`.
5. Restart the backend.
6. In Settings or project provider overrides, select `openai-image` and a GPT
   Image model such as `gpt-image-1`.

## Disable Real Image Mode Quickly

1. Set `USE_REAL_IMAGE_PROVIDER=false`.
2. Restart the backend.
3. Confirm provider status returns mock/blocked instead of real-ready.
4. Generate one image and verify the response uses a mock image URL again.

## Verify Secret Presence

Check provider status:

```bash
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/providers/image/status"
```

Expected staging signal when configured:

- `feature_flag_enabled=true`
- `key_present=true`
- `real_capable=true`
- `would_use_real_provider=true`
- `status=ready`

The response must not include the secret value.

## Staging Checklist

- [ ] Stripe remains in test mode.
- [ ] Auth is enabled if testing with real users.
- [ ] Test user has enough credits.
- [ ] Asset storage is local for development or S3/R2 when that backend is
      implemented for the environment.
- [ ] `/api/providers/image/status` shows `key_present=true`.
- [ ] Image provider status shows `real_capable=true`.
- [ ] Video, voice, music, and export statuses remain mock-only.
- [ ] No frontend API key inputs are visible.
- [ ] Provider activity and credit event admin pages are accessible to an admin
      tester.

## Test One Scene Image

1. Create or open a single test project.
2. Create or split scenes.
3. Pick one scene with a clear visual prompt.
4. Optionally run image prompt enhancement first.
5. Record current credits from `GET /api/credits/status`.
6. Generate one scene image from the Images tab or:

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/scenes/<scene_id>/generate-image"
```

Expected:

- Response keeps the existing shape with `image_url`, `cost`, and
  `remaining_credits`.
- `image_url` points to the configured asset storage URL.
- The scene has `status=image_ready`.
- Exactly one image generation cost is deducted.

## Test One Character Image

1. Create or open a test project.
2. Create one character with a useful name and description.
3. Record current credits from `GET /api/credits/status`.
4. Generate one character image:

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/characters/<character_id>/generate-image"
```

Expected:

- Response includes `image_url`, `reference_image_url`, `cost`, and
  `remaining_credits`.
- Character `reference_image_url` is updated to the stored asset URL.
- Exactly one image generation cost is deducted.

## Confirm Asset Storage Works

For local storage:

1. Confirm `image_url` begins with `ASSET_PUBLIC_BASE_URL`.
2. Open the returned `image_url` in a browser or with `curl`.
3. Confirm a matching `assets` record exists with:
   - `asset_type=scene_image` or `asset_type=character_image`
   - `storage_backend=local`
   - `provider_name=openai-image`
   - `provider_job_id` if OpenAI returned one
   - `size_bytes > 0`

Raw image bytes must be stored on disk or future object storage, not in
MongoDB.

## Confirm Credits Are Deducted Correctly

1. Call `GET /api/credits/status` before generation.
2. Generate exactly one scene or character image.
3. Call `GET /api/credits/status` after generation.
4. Confirm `credits_available` decreased by the configured image cost.
5. Confirm `credits_used` increased by the same amount.
6. Confirm a `credit_events` row exists with operation `image`.

## Confirm Failed Generations Do Not Deduct Credits

Use a staging-only failure check:

1. Temporarily set `USE_REAL_IMAGE_PROVIDER=true` with the provider selected,
   but remove or deny access to the SSM parameter.
2. Restart the backend.
3. Confirm `/api/providers/image/status` no longer reports real-ready.
4. Record credits.
5. Trigger one image generation.
6. Confirm credits do not decrease for blocked/failed real image execution.

Do not run this check against a broad test cohort.

## Confirm Provider Activity Logging

Open Admin Provider Activity or inspect the `provider_activity` collection.

Expected success row:

- `modality=image`
- `provider_name=openai-image`
- `mode=real`
- `status=success`
- `estimated_credits=2`
- `duration_ms` present
- `key_present=true`

Expected failure/blocked row:

- `modality=image`
- `mode=real` or `mock`
- `status=failed` or `blocked`
- no prompt text
- no raw image data
- no secret values

## Monitor Cost

- Start with one user.
- Start with one project.
- Start with one character image.
- Start with one scene image.
- Do not allow bulk generation yet.
- Watch `credit_events` and `provider_activity`.
- Record internal cost per successful image.
- Review failed/blocked rate before increasing test volume.
- Keep per-user credits capped during private beta.

## Rollback To Mock Mode

1. Set `USE_REAL_IMAGE_PROVIDER=false`.
2. Restart the backend.
3. Confirm `/api/providers/image/status` returns `mode=mock` and
   `would_use_real_provider=false`.
4. Generate one image and confirm the response uses a mock image URL again.
5. Keep the SSM secret in place if staging will resume later, or remove the
   secret if the provider should remain unavailable.

Rollback does not affect real LLM behavior, Stripe test mode, or existing
stored image assets.
