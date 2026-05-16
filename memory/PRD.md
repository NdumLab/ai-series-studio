# AI Episode Studio — PRD

## Problem Statement
Build a full-stack web MVP called AI Episode Studio that helps creators generate complete 1–3 minute AI story videos from characters, scenes, voice, music and short video clips. The product remains mock-first for image/video/voice/music/export. Real LLM execution exists for story and prompt text operations only, gated by server-side feature flags and key/runtime availability, with deterministic mock fallback.

## Architecture
- Backend: FastAPI + MongoDB (relational-style schemas), all routes under `/api`
- Frontend: React (CRA + craco) + Tailwind + shadcn/ui, dark cinematic theme (Outfit + IBM Plex Sans), red accent #FF3B30
- MVP auth is implemented: email/password beta accounts, bearer sessions, and
  per-user project ownership. `AUTH_DEMO_MODE=true` preserves the seeded
  no-token `user-demo` workflow for local demos/tests.
- Provider architecture exists under `backend/providers/`; LLM is real-capable behind `USE_REAL_LLM_PROVIDER`, while image/video/voice/music/export remain mock-only by construction.
- Mock generators return curated static URLs (Unsplash + Google sample mp4s) and log every generation/provider activity.

## Data Models (MongoDB collections)
- users: id, name, email, role, credits, optional password hash/salt, created_at
- user_sessions: id, token, user_id, created_at
- projects: id, user_id, title, idea, rewritten_story, status, provider override fields, optional soft-delete fields (`deleted_at`, `deleted_by`, `delete_expires_at`, `previous_status`), quality_scores, created_at, updated_at
- characters: id, project_id, order, name, description, voice_style, voice_provider, voice_model, reference_image_url
- scenes: id, project_id, order, title, duration, location, characters[], visual_prompt, raw/enhanced prompts, dialogue, music_mood, camera_direction, tension fields, voice, image_url, status
- segments: id, scene_id, project_id, order, parent_segment_id, start_second, expand_mode, continuity_prompt, video_url, duration, status (pending/approved/rejected)
- generations: id, user_id, project_id, type, cost_credits, status, error, created_at
- provider_activity: safe provider metadata only (no prompts, outputs, or API keys)

## Costs (credits)
rewrite 3 · split_scenes 4 · image 2 · video_segment 12 · voice 1 · music 2 · export 5

## Implemented (2026-02)
- Projects CRUD, soft delete, restore, 24h purge scheduler, rewrite, split-into-6-scenes
- Scene CRUD with full field set (incl. dialogue, music_mood, camera_direction, voice, characters tags)
- Character CRUD with placeholder portrait, per-character voice override, `order` field, and drag handles in the Cast view.
- Mock image generation (curated URL pool, 5% mock failure to populate admin failed jobs)
- Mock 5s video segment generation, "Expand next 5s", approve/reject/regenerate
- Cost estimator (POST /api/cost-estimate + GET /api/projects/{id}/cost-estimate)
- Final Export page with stitched preview (mock final video URL)
- Admin console: stats + users/projects/generations/failed jobs/provider activity/provider health/recently deleted tables
- Provider settings + per-project provider overrides; real LLM is gated and available for text operations, non-LLM modalities remain mock-only.
- Scene reorder, segment reorder, and character reorder are implemented.
- MVP auth and project ownership are implemented with local demo compatibility.
- Per-user credit balances and insufficient-credit blocking are implemented for
  generation actions.
- Stripe test-mode readiness gate exists: `GET /api/billing/status`, a billing
  config helper, disabled env placeholders, and Settings-page status. Stripe
  SDK/network calls, checkout sessions, webhooks, live payments, and real
  credentials are not implemented or committed.
- Current backend suite has grown substantially since the MVP baseline; see later iteration notes for exact counts.

## P1 Completed
- Character drag handles in Cast view.
- Safe delete / Undo delete.
- Recently Deleted admin panel.
- Background purge scheduler.

## MVP Roadmap
- Canonical MVP completion plan: `docs/MVP_PLAN.md`.
- Current MVP status: mock-first workflow is mature; real LLM is gated and
  available for text operations; image/video/voice/music/export remain
  mock-only.
- 100% MVP still requires production auth/user ownership hardening, a real
  user-tied credit wallet with Stripe fulfillment, Stripe checkout/session
  creation and webhooks, real image generation, real video segments, real
  voice/music or upload fallback, real FFmpeg export, durable object storage,
  deployment, and end-to-end real media validation.
- Recommended build order:
  1. Production auth/user ownership hardening.
  2. Real credit wallet tied to users.
  3. Stripe checkout/session creation and webhook credit fulfillment.
  4. Real image provider.
  5. Real video provider.
  6. Real voice/music.
  7. Real export.
  8. Private beta.
- Launch-ready criteria include working auth, credits, real LLM, real image,
  real video, MP4 export, storage, cost limits, admin monitoring, full passing
  tests, three successful sample episodes, and understood internal cost per
  1-minute video.

## Backlog (P2)
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

Auth and user ownership must come before real Stripe checkout/webhook work
because billing and credit fulfillment need a reliable user owner.

## Iteration 25 (2026-05) — MVP auth and ownership
- Added local email/password auth endpoints:
  - POST /api/auth/register
  - POST /api/auth/login
  - POST /api/auth/logout
  - GET /api/me returns the current public user.
- Added bearer session tokens stored server-side in `user_sessions`.
- Project list/create/detail/update/delete/restore plus project-scoped
  character, scene, segment, provider, export, and generation routes are scoped
  to the authenticated user.
- Preserved local demo compatibility: when `AUTH_DEMO_MODE=true` and no bearer
  token is sent, requests use the seeded `user-demo` account.
- Frontend now has a private beta login/register page and stores the bearer
  token in local storage for API requests.
- No Stripe, paid provider calls, API key inputs, or real image/video/voice/
  music/export providers were added.

## Iteration 26 (2026-05) — Credit wallet guardrails
- Replaced the display-only wallet with per-user credit balances for generation
  actions.
- Story rewrite, story improvement, scene split, image generation, video
  segment generation, and video segment regeneration reserve/deduct credits
  before execution.
- Insufficient-credit requests return HTTP 402 with required and available
  credit details.
- Mock provider failures refund reserved credits before returning the failure.
- Project scene-cost and dashboard wallet summaries now use the current user's
  remaining credit balance.
- Stripe remains disabled and no paid provider calls or API key inputs were
  added.

## Iteration 27 (2026-05) — Stripe test-mode readiness gate
- Added `GET /api/billing/status`, a safe billing readiness endpoint that only
  reports whether Stripe test-mode env vars are configured.
- Added disabled-by-default billing env placeholders:
- `STRIPE_TEST_MODE=false`
- `STRIPE_SECRET_KEY=`
- `STRIPE_CREDIT_PRICE_ID=`
- `STRIPE_WEBHOOK_SECRET=`
- Added a side-effect-free billing config helper.
- Added Settings-page visibility for Stripe test metering status.
- Added side-effect-free billing config tests.
- No Stripe SDK/network calls, checkout sessions, webhooks, live payments,
  real charges, or real credentials were added.

## Iteration 2 (2026-02) — Workflow & Segment Model
- Added persistent "Mock Mode: No real AI APIs connected yet" badge in top nav.
- Project Studio split into 7 explicit stages: Story → Scenes → Characters → Images → Video Segments → Voice/Music → Export, with a clickable workflow progress strip.
- Story tab makes the rewritten draft editable before splitting (explicit hint).
- Scenes tab edits text/structure only; media generation moved to Images and Video Segments tabs.
- Backend segment model extended (additive, backward-compatible):
  - parent_segment_id, start_second, expand_mode ("initial" | "expand"), continuity_prompt
  - start_second auto-computed from prior siblings; expand chains link parent → child
- POST /api/scenes/{id}/segments and /expand now accept optional { continuity_prompt }
- Cascade-delete segments when project is deleted.
- Backend tests extended to 18 cases — added test_expand_chain_links_parents covering full expansion chain.

## Iteration 3 (2026-02) — Provider Settings page
- New `/settings` route + nav link "Settings" (gear icon).
- 6 modality cards: LLM (story rewrite) · Image · Video · Voice · Music · Export (FFmpeg). Each card has provider Select + model Select + Test connection button. Picking "Custom …" reveals custom provider ID and custom model ID inputs.
- API keys are intentionally NOT exposed yet — only provider/model selection is persisted.
- Two informational banners on the page: "Mock mode active — no real provider calls are made" and "API keys are intentionally disabled".
- Backend: new `provider_settings` MongoDB collection (single doc id="global"), endpoints:
  - GET /api/settings/providers/options — provider catalog (modalities + provider+model lists).
  - GET /api/settings/providers — current selections (forces mock_mode=true).
  - PUT /api/settings/providers — validates provider id against catalog; rejects unknown.
  - POST /api/settings/providers/test — always returns "Mock mode active — real provider call skipped."
- Tests: 22/22 passing (added 4 cases: options shape, get/update round-trip + custom provider, unknown-provider 400, mocked test endpoint).
- No keys stored, no real APIs touched.

## Iteration 4 (2026-02) — Per-project provider override (mock-only)
- Backend `.env` gains 6 feature flags (all `false`): USE_REAL_LLM_PROVIDER, USE_REAL_IMAGE_PROVIDER, USE_REAL_VIDEO_PROVIDER, USE_REAL_VOICE_PROVIDER, USE_REAL_MUSIC_PROVIDER, USE_REAL_EXPORT_PROVIDER. Exposed via `GET /api/feature-flags`.
- Project documents gain 13 fields:
  - `provider_override_enabled` (bool, default false)
  - `llm_provider`, `llm_model`
  - `image_provider`, `image_model`
  - `video_provider`, `video_model`
  - `voice_provider`, `voice_model`
  - `music_provider`, `music_model`
  - `export_provider`, `export_mode` (note: export uses `export_mode`, not `export_model`)
- New endpoints:
  - `GET /api/projects/{id}/providers` — returns project view + merged effective config (override_on → project, otherwise global). Empty project field falls back to global ("global-fallback" source).
  - `PUT /api/projects/{id}/providers` — accepts any subset of the new fields; validates provider id against catalog (400 on unknown).
  - `POST /api/projects/{id}/providers/test` — always mocked: `"Mock mode active — no real provider call was made."`
- Frontend ProjectStudio:
  - 8th tab "Providers" appended to the tab row (with gear icon). Workflow strip stays Step N **of 7** (Providers is config, not creative).
  - Small "⚙ Providers" shortcut button placed beside the Cost badge in the project header.
  - Inside the Providers tab:
    - Header source badge — "Configured from global defaults" (gray) ⇄ "Project override active" (red).
    - Toggle: "Use global defaults" / "Override for this project".
    - Yellow flag chips for each USE_REAL_*_PROVIDER (all show "off").
    - Disabled "API key management" placeholder banner — "API key management will be enabled when real provider mode is activated."
    - When override OFF: read-only "Effective" cards showing what would be used from global, each with a mocked Test button.
    - When override ON: editable provider+model selects per modality with a "Test" button each, plus a Save button. Empty fields fall back to global at runtime.
- Tests: 29/29 passing. Added 7 cases — feature flags all false; new project includes all override fields; default get returns global; override round-trip incl. export_mode; unknown provider 400; mocked test endpoint; existing rewrite/split/scenes/segment/export pipeline still works with override enabled.
- No real APIs added; no API keys collected or stored.

## Iteration 5 (2026-02) — Inline provider visibility
- New `ProviderHint` UI atom shown above each generation tab:
  - Story → "This story rewrite would use: {effective_llm_provider}/{effective_llm_model}"
  - Images → "This image generation would use: {effective_image_provider}/{effective_image_model}"
  - Video Segments → "This video generation would use: {effective_video_provider}/{effective_video_model}"
  - Voice/Music → two hints, one for voice, one for music
  - Export → "This export would use: {effective_export_provider}/{export_mode}"
- Right-aligned badge per hint: "Using Global Default" (gray) ⇄ "Project Override Active" (red).
  Badge reads "Project Override Active" only when `provider_override_enabled=true` AND the modality's effective source is `"project"` (i.e. a project value is actually set). Empty fields under override correctly fall back to global ("global-fallback") and the badge stays "Using Global Default".
- Effective config is fetched once at the project level via `GET /api/projects/{id}/providers` and shared with all tabs; it auto-refreshes when ProvidersTab saves.
- All generation buttons remain mock-only; the inline text is informational.
- Backend: no new endpoints — reuses the existing `/projects/{id}/providers` resolver.
- Tests: 30/30 passing. Added `test_effective_resolution_per_modality` asserting full merge semantics for all six modalities (override OFF → all global; override ON + value → project; override ON + empty → global-fallback) plus `mock_mode=True` and all USE_REAL_*_PROVIDER flags `False` throughout.
- No real API calls; no API key fields added or stored.

## Iteration 6 (2026-02) — Credit reflection + per-character voice override
- Backend COSTS extended: `video_segment` bumped to 12, added `music: 2`, `export: 5`. Returned via `GET /api/meta/options.costs`.
- Character schema gains `voice_provider` and `voice_model` (validated against the catalog when set, "" means inherit).
- New endpoint `GET /api/projects/{id}/voice-resolution` resolves per-character voice with the priority **character → project → global** and returns `source` ∈ {"character","project","global"} for each.
- Frontend ProviderHint now accepts a `credits` prop; each tab passes a label sourced from `options.costs`:
  - Story → "~3 credits"
  - Images → "~2 credits per scene image"
  - Video Segments → "~12 credits per 5-second segment"
  - Voice/Music → "~1 credit per scene" / "~2 credits per scene"
  - Export → "~5 credits per final export"
- Voice/Music tab shows a "Per-character voices" list with a colored source badge (Character Override / Project Override / Global Default) per character. Clicking Edit jumps to the Characters tab.
- Characters dialog upgraded to support edit-in-place plus an optional voice override (provider select + model/voice id input). Card shows `↳ provider/model` chip when override is set.
- Tests: 35/35 backend cases passing. Added: `test_voice_resolution_priority`, `test_character_create_accepts_voice_fields`, `test_character_voice_provider_validated`, `test_cost_estimate_includes_music_and_export`, `test_meta_options_costs_complete`. Existing tests updated for new video_segment cost.
- Mock-only throughout; feature flags all false; no API keys collected or stored.

## Iteration 7 (2026-02) — Scene credit widget + character voice override chip
- New backend route `GET /api/projects/{id}/scene-costs` — returns per-scene total using formula `image + video_segment * max(1, segment_count) + voice`, includes breakdown, `planned_segments`, `estimate_unavailable` flag, `missing_costs` list, plus `grand_total_credits`. Mock-mode flag preserved.
- Frontend Scenes tab: every SceneEditor card now shows a yellow "Credits this scene · ~N" widget next to the Scene N label and status chip with an inline mini-breakdown ("img X · vid Y(2×) · voice Z") and a hover tooltip with the same breakdown. Falls back to "estimate unavailable" when any unit cost is missing.
- Frontend Scene editor "Characters in scene" tag list: characters with a voice override show a small yellow "Voice Override" chip next to their name. Hover/title tooltip reveals "Voice: {provider}/{model}" + "Source: Character Override / Project Override / Global Default" pulled from the existing voice-resolution endpoint.
- Tests: 38/38 backend cases pass. Added: `test_scene_costs_basic_and_multi_segment` (planned=max(1, n_segments); 0-segment scene → 15 credits; 2-segment scene → 27 credits), `test_scene_costs_matches_spec_example` (image=2, video=5, voice=1, n=2 → 13), `test_voice_resolution_remains_after_scene_cost_calls` (mock-mode preserved across endpoints; character override still wins).
- All generation remains mock; flags `USE_REAL_*_PROVIDER` still false; no API keys collected.

## Iteration 8 (2026-02) — Live cost badge + Scenes header grand total
- Frontend ProjectStudio now fetches `GET /api/projects/{id}/scene-costs` into a `sceneCosts` state with `{status: idle|loading|ok|error, data}`. Lifted into the parent so all tabs share the same source.
- New Project header **CostBadge** label is "Project scene cost"; renders one of:
  - "Calculating…" while loading (data-testid: `cost-badge-loading`)
  - "Estimate unavailable" on error (data-testid: `cost-badge-error`)
  - "~{grand_total_credits} credits" when ok (data-testid: `cost-badge-total`)
- Scenes tab header shows: `N scenes · ~X credits` using the same backend value (data-testid: `scenes-grand-total`).
- `reloadAll` now refetches project + voice-resolution + scene-costs and is wired into Scenes/Images/VideoSegments tabs so any mutation (add/delete scene, generate/expand/regenerate/delete segment) live-updates the badge and the Scenes header.
- Backend remains the source of truth — frontend never recomputes the project total locally, only displays/refetches.
- Tests: 40/40 backend cases passing. Added `test_scene_costs_grand_total_updates_after_expand` (verifies grand_total bumps by exactly `video_segment` cost on expand) and `test_scene_costs_404_for_unknown_project` (so the FE error fallback has a real failure mode).
- Mock-only invariants preserved.

## Iteration 9 (2026-02) — Wallet ring + High-cost scene warning
- Backend: new `studio_config()` reads two tunables from env:
  - `WALLET_CREDITS` (default 250)
  - `HIGH_COST_SCENE_THRESHOLD_PERCENT` (default 25)
- New endpoint `GET /api/config` returns both + `mock_mode: true`.
- `GET /api/projects/{id}/scene-costs` extended with:
  - `wallet_credits`, `wallet_pct`, `wallet_state` ∈ {`normal` <41, `warning` 41–70, `high` 71–100, `insufficient` >100}
  - `high_cost_scene_threshold_percent` (echoed for UI display)
  - per-scene `share_pct` and `high_cost: bool`
  - Optional query overrides `?wallet_credits=`, `?high_cost_pct=` (lets dev tools/tests drive states without mutating server env).
- Frontend:
  - Project header CostBadge gains a **wallet ring** (SVG donut) showing % of seeded 250-credit demo wallet, color-coded by state (green/yellow/orange/red). Tooltip: "This episode would use about X% of your available 250 credits." Hidden gracefully when scene-costs is in error/loading.
  - Each SceneEditor card gains a calm orange **"High-cost scene · X%"** badge (lucide AlertCircle icon) when `costRow.high_cost === true`. Tooltip text includes share %, the breakdown line and the suggested action ("Consider reducing segments or using Draft mode") — phrased as guidance, not failure.
  - Threshold value flows via the backend response (`high_cost_scene_threshold_percent`) — never hard-coded in the UI; changing the env var updates everything.
- Tests: 45/45 backend pass. Added: `test_studio_config_endpoint`, `test_scene_costs_includes_wallet_pct_and_state`, `test_wallet_state_thresholds` (covers normal/warning/high/insufficient via query override incl. >100%), `test_high_cost_scene_flag_with_configurable_threshold` (default 25%, plus overrides 10% / 50%), `test_scene_costs_404_still_works_for_wallet`. Mock mode and feature flags still asserted False.
- Mock-only invariants preserved.

## Iteration 10 (2026-02) — Dashboard wallet rings + Cost-badge trend arrow
- Backend `GET /api/projects` now embeds a `cost_summary` per project: `{grand_total_credits, wallet_credits, wallet_pct, wallet_state, estimate_unavailable}`. Helper `_project_cost_summary` reuses the same formula as `/scene-costs`.
- Dashboard project cards show a small `MiniWalletRing` with the line `~N credits · X% of wallet`, color-coded by state, and an `AlertCircle` icon when `wallet_state === "insufficient"`. Falls back to "Estimate unavailable" when the summary is missing/incomplete. Tooltip mirrors the spec: _"This draft would use about X% of your available 250 credits."_
- ProjectStudio Cost badge gains a temporary trend chip:
  - On any cost-changing mutation, `loadSceneCosts({trackDelta:true})` compares old vs new `grand_total_credits` and pushes `{value, key}` into a `costDelta` state.
  - The badge renders `↑ +N` (orange) or `↓ -N` (green) next to the total, animated by a 1.5s CSS pulse (`@keyframes es-trend-pulse`), then auto-clears.
  - Triggered by every mutation already wired to `reloadAll`: add/delete/update scene, generate/expand/regenerate/**delete** segment.
- Added a small trash button on each `SegmentCard` so segment deletion is reachable from the UI (matching the new spec trigger). Reuses the existing `DELETE /api/segments/{id}` route.
- Tests: 51/51 backend cases pass. Added 6 new cases:
  - `test_list_projects_includes_cost_summary` (default 6-scene 90-credit project ⇒ 36% normal)
  - `test_dashboard_summary_handles_insufficient_state` (drives total > 250 via expansions)
  - `test_trend_increase_on_expand` (delta exactly +12 = video_segment cost)
  - `test_trend_decrease_on_segment_delete` (delta exactly −12)
  - `test_trend_decrease_on_scene_delete` (delta exactly −15 = full default scene cost)
  - `test_dashboard_estimate_unavailable_when_costs_missing` (schema contract for the field)
- Mock-only invariants preserved.

## Iteration 11 (2026-02) — Reduce-to-Draft + sortable Dashboard
- Backend: new endpoint `POST /api/scenes/{id}/reduce-to-draft` deletes every video segment under the scene except the earliest one (idempotent — 0 or 1 segment is a no-op). Returns `{deleted_segments, saved_credits, segments[], mock_mode:true}`. Saved credits = `deleted_segments × COSTS["video_segment"]`.
- Frontend: the orange "High-cost scene · X%" badge now contains an inline **"Reduce to Draft"** button (only visible when the scene has more than one segment). Clicking it calls the new endpoint, toasts `"Saved -N credits"`, and triggers `reloadAll()` which makes the existing trend chip flash `↓ -N` on the Cost badge.
- Dashboard: new **Sort by** chip-row above the projects grid — `Newest` (default), `Title A→Z`, `Cost ↓`, `Cost ↑`. Sort is client-side using the existing `cost_summary.grand_total_credits`; no backend change required.
- Tests: 53/53 backend cases pass. Added: `test_reduce_to_draft_basic_and_idempotent` (4 segments → 1 segment, saves 36 credits, second call deletes 0) and `test_reduce_to_draft_404_unknown_scene`.
- Mock-only invariants preserved.

## Iteration 12 (2026-02) — Continuity prompt editor + scene/segment reorder
- Backend additions:
  - `PUT /api/segments/{id}` — generic partial update accepting `continuity_prompt`, `expand_mode`, `duration`, `status`. The dedicated `/status` route still works.
  - `PUT /api/projects/{id}/scenes/reorder` — payload `{scene_ids:[...]}`. Validates the list is exactly the project's scenes (no foreign IDs, no missing IDs); rewrites each scene's `order`. Returns the reordered list.
  - `PUT /api/scenes/{id}/segments/reorder` — payload `{segment_ids:[...]}`. Same validation against the scene's segments; rewrites `order` AND recomputes `start_second` cumulatively from each segment's `duration`.
- Frontend additions:
  - New `<SortableList>` wrapper (`@dnd-kit/core` + `@dnd-kit/sortable`) with a small `GripVertical` drag handle. Drag is restricted to the handle so form inputs and buttons inside cards continue to work normally.
  - Scenes tab now renders SceneEditors inside a vertical SortableList; drag end → `Scenes.reorder(projectId, ids)` → `reloadAll()`.
  - Each `SceneSegmentBlock` now renders SegmentCards in a grid SortableList; drag end → `Scenes.reorderSegments(sceneId, ids)` → `reloadAll()` (cost badge + scene-costs auto-refresh).
  - Per-segment **Continuity prompt** editor on each SegmentCard with save-on-blur and a tiny status indicator: idle → `Saving…` → `Saved` (auto-fade after 1.5s) → `Failed to save` on error. Persists via the new generic `PUT /api/segments/{id}`.
- Tests: **59/59 backend cases pass.** Added 6 cases:
  - `test_segment_continuity_prompt_update` (round-trips + trims, `/status` route still works, empty body 400, bad duration 400)
  - `test_scene_reorder_success` (reverse 6 scenes, `order` rewritten, persisted)
  - `test_scene_reorder_rejects_foreign_or_partial` (foreign-project scene 400, missing scene 400)
  - `test_segment_reorder_success_recomputes_start_second` (3 segments reversed → start_seconds = 0/5/10, orders 0/1/2)
  - `test_segment_reorder_rejects_foreign` (foreign-scene segment 400, empty list 400)
  - `test_existing_expand_and_costs_still_work_after_reorder` (post-reorder, expand chains parent_segment_id correctly + scene-costs reflects 2 segments → 27 credits)
- Mock-only invariants preserved; all 6 `USE_REAL_*_PROVIDER` flags still false; no API key fields.


## Iteration 13 (2026-02) — Optimistic drag verification + ProjectStudio refactor
- **Optimistic drag-and-drop verified end-to-end** (testing agent iteration_2):
  - Scene drag: DOM updates immediately on drop, persists across reload, no snap-back.
  - Segment drag: optimistic reorder recomputes `start_second` cumulatively before the API resolves; matches backend formula; persists after reload.
  - Failure path: server rejection restores previous snapshot + shows `Reorder failed — restored` toast.
- **Bug fix**: `SceneSegmentBlock` previously did not destructure `setData` from props, silently neutering the segment optimistic update. Fixed during refactor in `VideoSegmentsTab.jsx`.
- **Refactor — `ProjectStudio.jsx` split** (behavior unchanged):
  - Before: monolithic ~2285-line file containing all 7 tabs + 14 helper components.
  - After: ~225-line orchestrator that owns shared state (`data`, `providers`, `voiceRes`, `sceneCosts`, `options`, `tab`) and delegates each tab.
  - New files under `/app/frontend/src/pages/tabs/`: `StoryTab.jsx`, `ScenesTab.jsx`, `CharactersTab.jsx`, `ImagesTab.jsx`, `VideoSegmentsTab.jsx`, `VoiceMusicTab.jsx`, `ExportTab.jsx`, `ProvidersTab.jsx`.
  - New shared components under `/app/frontend/src/components/studio/`: `StageProgress.jsx`, `WalletRing.jsx`, `CostBadge.jsx`, `ProviderHintChip.jsx`, `SceneCard.jsx`, `SegmentCard.jsx`, `SceneCostWidget.jsx`, `FieldInput.jsx`, `InfoCallout.jsx`, `EmptyState.jsx`, `constants.js`.
- **Verification**:
  - Backend: 59/59 pytest cases pass (unchanged).
  - Frontend: production build OK (178.62 kB gzip), ESLint clean, all 8 tabs render with zero console errors (testing agent iteration_2).
- **Character drag handles** were backlogged at this point; superseded by Iteration 24, where Cast drag handles shipped.
- Mock-only invariants preserved; no real provider wiring, no API key fields, no Stripe.

## Backlog (P1) — refreshed
- Character drag handles in Cast view are implemented as of Iteration 24:
  Character documents now carry `order`, the Cast view has drag handles, and
  `PUT /api/projects/{id}/characters/reorder` persists ordering.
- Safe delete / Undo / Restore / 24h purge is now implemented:
  `DELETE /api/projects/{id}` soft-deletes, `POST /api/projects/{id}/restore`
  restores, `POST /api/admin/purge-deleted-projects` purges expired records,
  and Admin has a **Recently Deleted** panel.
- Provider architecture is now implemented, including provider resolution,
  provider activity logs, guard/status endpoints, and LLM-only real execution.
  Remaining provider backlog is limited to real non-LLM plug-ins.
- P1 completed: character drag handles, safe delete / Undo delete, Recently
  Deleted admin panel, background purge scheduler.

## Backlog (P2)
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


## Iteration 14 (2026-02) — Project cascade-delete with counts
- `DELETE /api/projects/{project_id}` now returns deletion counts and is fully cascaded across the four collections:
  ```json
  { "ok": true, "deleted": { "projects": 1, "scenes": 6, "characters": 3, "segments": 12 } }
  ```
- Deletes by `project_id` on `scenes`, `characters`, and `segments` (segments already carry `project_id` so the cleanup is one-shot — no need to fan-out via scene IDs).
- Deleting a non-existent project remains a safe `200 ok` with all counts at `0`, preserving the existing API DELETE convention.
- Tests: **62/62 backend cases pass.** Added 3 cases:
  - `test_delete_project_cascades_scenes_characters_segments` (6 scenes + 2 chars + 2 segments fully removed; subsequent GET → 404; export → 404)
  - `test_delete_project_does_not_touch_other_projects` (deleting project A leaves project B's scenes / characters / segments intact)
  - `test_delete_unknown_project_is_safe` (unknown project → `{ok: true, deleted: all zeros}`)
- Mock-only invariants preserved; no real provider wiring, no API key fields, no Stripe.


## Iteration 15 (2026-02) — Dashboard delete with toast + confirm
- Each project card on the Dashboard now exposes a small **trash button** in the top-right that appears on hover (`opacity-0 group-hover:opacity-100`). Click stops the card-link navigation and opens an `AlertDialog` confirmation ("Delete "X"? — This permanently removes the project, its scenes, characters, and video segments").
- On confirm, `Projects.remove(id)` is called; the card is **optimistically removed** from local state (and restored on failure), the top-bar "Projects" / "In progress" stats auto-recompute from `projects.length`.
- Toast format (uses counts returned by the cascade endpoint, characters only included if > 0):
  - Full delete → `Deleted "Test Ep" · 6 scenes · 3 characters · 12 segments removed`
  - Without characters → `Deleted "Test Ep" · 6 scenes · 12 segments removed`
  - All zeros (already gone) → `Project already removed or not found.`
- "Saved credits" intentionally **not surfaced** — the backend does not yet compute that and we did not invent the number.
- Frontend-only; no backend / API key / Stripe changes. Lint clean and prod build OK (179 kB gzip).


## Iteration 16 (2026-02) — Phase 2A: provider service-layer foundation
**Goal**: prepare the architecture for real providers — without enabling, calling, or storing any real credentials.

### New backend package — `/app/backend/providers/`
- `base.py` — `ProviderResult` dataclass (`modality`, `provider_name`, `model_name`, `mode` (mock|real), `status` (success|blocked|failed|skipped), `estimated_credits`, `provider_job_id`, `output`, `error`, `message`, `meta`), `BaseProvider`, `MockProviderMixin`, `MODALITIES`.
- `mocks.py` — `MockLLM/Image/Video/Voice/Music/Export` plus `MOCK_PROVIDER_BY_MODALITY` dispatch.
- `resolver.py` — pure-logic resolver. Priority: **character → project (when override on) → global → hard-fallback mock**. `resolve_voice_for_character()` adds the character layer on top.
- `keys.py` — `key_present(provider)` always returns `False`; `key_status() = "not_configured"`. This is the deliberate Phase 2A seam — no key storage, no env reads.
- `executor.py` — `execute_provider(...)` resolves → checks flag → checks key → dispatches. **Real path is unreachable today**: if a flag is mistakenly flipped on, the executor still runs the mock and tags `status="blocked"`. `provider_status(...)` returns a diagnostic snapshot. `run_modality_test(...)` powers the unified dry-run endpoint.

### New backend endpoints (additive, no behavior change to existing routes)
- `POST /api/providers/test` — body `{modality, project_id?}` → `{ok: true, mode: "mock", status: "skipped", provider, model, source, feature_flag_enabled, key_status, key_present, message}`.
- `GET /api/providers/{modality}/status` — diagnostic snapshot for a modality (optional `?project_id=`).

### Executor guard wired into existing generators (non-behavior-changing)
- `POST /projects/{id}/rewrite`, `POST /scenes/{id}/generate-image`, `_create_scene_segment` (used by `POST /scenes/{id}/segments` and `POST /scenes/{id}/expand`) now call `execute_provider(...)` before the existing mock work. The guard always resolves to the mock today, logs `mode/status/provider/model`, and the response shape stays byte-for-byte identical.

### Frontend
- `ProvidersTab.jsx` effective-global view gains two informational rows per modality card: **Mode → "Mock"** (data-testid `eff-mode-<modality>`) and **Key status → "not configured"** (data-testid `eff-key-status-<modality>`). No input fields added.

### Tests — **83/83 passing** (was 62, +21)
- `/app/backend/tests/test_provider_layer.py` (15 unit tests): global fallback, project override beats global, override-on-empty falls back to global, hard-fallback when no config, unknown modality rejected, character voice override beats project/global, project voice override beats global, global voice fallback, executor runs mock when flag off, executor blocks (mock + `status=blocked`) when flag on but no key, estimated_credits respected, voice modality routes through character resolver, dry-run returns mock response, status snapshot, status rejects unknown modality.
- 6 e2e cases appended to `backend_test.py`: unified `/providers/test` mock response, with project override, 404 for missing project, `/providers/{modality}/status` global, 400 for unknown modality, existing image generation still works through the guard.

### Hard guarantees (verified)
- `grep -rn "requests.|httpx.|aiohttp|openai.|anthropic.|fal_client|elevenlabs." /app/backend/providers/` → empty. **No real network code exists in the provider layer.**
- All `USE_REAL_*_PROVIDER` flags remain `false`. Even if one is flipped on, `key_present()` returns `False` and the executor refuses the real path.
- No API key inputs added on the UI. No Stripe. No auth.

### Files added (8)
- `backend/providers/__init__.py`, `base.py`, `mocks.py`, `resolver.py`, `keys.py`, `executor.py`
- `backend/tests/test_provider_layer.py`
- (1 modified) `backend/server.py` — imports + 2 new endpoints + 3 guard insertions
- (1 modified) `frontend/src/pages/tabs/ProvidersTab.jsx` — 2 new info rows per modality card
- (1 modified) `backend/tests/backend_test.py` — 6 e2e cases appended


## Iteration 17 (2026-02) — Phase 2A.5: guard state on project view + Admin Provider Activity
**Goal**: make every provider call observable (Admin view) and surface the guard state on the per-project Providers tab — still no real APIs, no key inputs, no Stripe, no auth.

### Backend
- New `_record_provider_activity(record)` coroutine in `server.py` is registered via `providers.set_activity_recorder(...)`. Each `execute_provider()` call now:
  1. Times the mock with `time.perf_counter()` → `duration_ms`.
  2. Pushes a **strictly allowlisted** metadata dict into the new `provider_activity` Mongo collection.
- Allowlist (no prompts, no outputs, no keys, no secrets): `modality, provider_name, model_name, source, mode, status, estimated_credits, provider_job_id, message, error, duration_ms, project_id, scene_id, segment_id, feature_flag_enabled, key_present` + auto-added `id` + `created_at`.
- New endpoint: `GET /api/admin/provider-activity?limit=50` → `{limit, count, items[]}` (clamped to ≤ 200).
- `execute_provider(...)` now accepts `project_id`, `scene_id`, `segment_id` scope kwargs. The three existing wired call sites (rewrite, generate-image, segment create) pass them through.

### Frontend
- `Admin.jsx` gains a new tab **Provider activity** showing: When · Modality · Provider/Model · Source · Mode · Status · Credits · Job id · Duration · Message. Includes a manual **Refresh** button. Banner reminds: "safe metadata only · no prompts, outputs or API keys are stored."
- `ProvidersTab.jsx`: new shared `GuardStateRows` component used both on the global view AND on each per-project override card. Rows show: Source · Mode (Mock) · Feature flag (disabled) · Key status (not configured) · Real call (blocked · mock-only).

### Tests — **87/87 passing** (was 83, +4)
- `test_provider_activity_endpoint_shape` — endpoint returns `{limit, count, items}`.
- `test_provider_activity_records_created_for_rewrite_image_video` — runs the three generators on a fresh project, asserts an `llm`, `image`, and `video` record exist, all `mode=mock`, all carry sane `duration_ms`, `estimated_credits`, and correct `scene_id` scope where applicable.
- `test_provider_activity_no_api_keys_anywhere` — scans the latest 200 rows. Asserts allowlist-only fields, no `api_key|secret|token|password` field names, no `sk-`/`Bearer `/`api_key=`/`api-key=` substrings in any string value, every row has `mode=mock` and `key_present=false`.
- `test_provider_activity_limit_capping` — `?limit=5000` is clamped to ≤ 200.

### Hard guarantees (re-verified this iteration)
- `grep -rn "requests.|httpx.|aiohttp|openai.|anthropic.|fal_client|elevenlabs." /app/backend/providers/` → empty.
- Every record in `provider_activity` today has `mode="mock"` and `key_present=false`.
- All `USE_REAL_*_PROVIDER` flags remain `false`. `key_present()` always `False`.
- No API key input fields anywhere on the UI.

### Files changed/added
**Modified** (6):
- `backend/server.py` — recorder registration + admin endpoint + 3 guard call sites pass scope ids.
- `backend/providers/__init__.py` — export `set_activity_recorder`.
- `backend/providers/executor.py` — `set_activity_recorder()` setter + `duration_ms` timing + scoped kwargs + safe-metadata write.
- `frontend/src/pages/tabs/ProvidersTab.jsx` — new `GuardStateRows` used on both global + project views.
- `frontend/src/pages/Admin.jsx` — new "Provider activity" tab + table.
- `frontend/src/lib/api.js` — `Admin.providerActivity(limit)` helper.
- `backend/tests/backend_test.py` — 4 new e2e cases appended.


## Iteration 18 (2026-02) — Provider Health Pulse (Admin → Provider Activity)
**Goal**: a lightweight rollup that turns the safe-metadata log from iteration 17 into an at-a-glance health view per modality. Still mock-only.

### Backend
- New endpoint `GET /api/admin/provider-health?window_minutes=60` (clamped 1–1440).
- Aggregates `provider_activity` over the window per modality. Status rules:
  - **no_activity** → `total_calls == 0`
  - **failing** → `failed/total ≥ 0.25`
  - **slow** → `avg_duration_ms > 3000`
  - **healthy** → otherwise
- Response is the exact shape the user specified:
  ```json
  { "window_minutes": 60, "modalities": [
      {"modality":"llm","total_calls":8,"success_calls":8,"failed_calls":0,"avg_duration_ms":12,"status":"healthy"}, …
  ]}
  ```

### Frontend
- New compact `ProviderHealthPulse` strip rendered above the Provider Activity table on the Admin page. 6 chips in a responsive 2/3/6 grid: modality name, colored dot, status label (Healthy / Slow / Failing / No activity), `avg ms · N calls` line, red `· N failed` callout when applicable. `Refresh` button refreshes both pulse + activity together.
- `Admin.providerHealth(windowMinutes=60)` helper added to `lib/api.js`.

### Tests — **93/93 passing** (was 87, +6)
Used pymongo directly to seed deterministic `provider_activity` rows tagged with `test-health-seed-*` ids, with a `clean_seed` fixture that purges them before and after each test. New tests:
- `test_provider_health_all_modalities_listed` — all six modalities appear in the response in order.
- `test_provider_health_no_activity_status` — modality with no calls in a 1-minute window → `no_activity`.
- `test_provider_health_healthy_status` — 5 success @ 20 ms → `healthy`.
- `test_provider_health_slow_status` — 4 success @ 5000 ms → `slow`.
- `test_provider_health_failing_status` — 2 of 4 failed (50%) → `failing`.
- `test_provider_health_no_secrets_in_response` — no `api_key|secret|bearer|sk-|password|token` substrings in JSON; per-modality entry keys are exactly the documented allowlist.

### Mock-only invariants — re-verified
- No new real-network code. `providers/` package still has zero http imports.
- All `USE_REAL_*_PROVIDER` flags `false`. `key_present()` always `False`.
- The pulse aggregates 100% mock-mode rows (every row has `mode="mock"`).

### Files changed (4)
- `backend/server.py` — `timedelta` import + `GET /api/admin/provider-health`.
- `frontend/src/pages/Admin.jsx` — `ProviderHealthPulse` component + state + render above table.
- `frontend/src/lib/api.js` — `Admin.providerHealth()` helper.
- `backend/tests/backend_test.py` — `json` import + `_direct_db`, `_seed_activity`, `_purge_seed`, `clean_seed` fixture + 6 new test cases.

### Decision deferred to next milestone
- **Phase 2B real provider implementation is intentionally NOT started.** The next milestone is the **secrets storage design** (per the user's instruction). Options to evaluate before implementation:
  1. Server-side encrypted secrets store with per-modality scoping (e.g. age/sops/sealed-box on disk, read-only at runtime).
  2. Server-side LLM runtime key for LLM modality only (no additional infra).
  3. Per-tenant KMS once auth/multi-tenant is added (P2 backlog).


## Iteration 19 (2026-02) — Creative Quality Engine (mock-only)
**Goal**: stop optimizing for "calling providers" and start optimizing for "great episodes." All scoring + enhancement is deterministic and rule-based today. Phase 2B will swap the rule-based mocks for real LLM-driven analysis behind feature flags.

### Secrets storage decision
Per user: **option (b)** for the near term. Use a **server-side LLM runtime key for LLM modality only** when Phase 2B starts. Image / Video / Voice / Music / Export remain blocked until a proper at-rest-encrypted secrets store exists. No generic key storage will be implemented yet. Per-tenant KMS deferred until auth + multi-tenant lands.

### Backend — new module `/app/backend/creative_quality.py`
Pure-logic, zero-network. Deterministic scoring + enhancement helpers:
- `QUALITY_KEYS` = `(hook_strength, conflict_strength, emotional_tension, visual_potential, cliffhanger_strength, dialogue_strength, overall_story_score)`.
- `compute_quality_scores(idea, rewritten)` — base from word count + per-trait keyword scoring + dialogue heuristic, clipped to 20–98, overall = mean of the six dimensions.
- `apply_improvement(rewritten, kind)` for the 7 mock improvement kinds — each prepends a flavoured snippet to paragraph 1 and returns `(new_story, improvement_note)`.
- `compute_scene_tension(scene, index)` — seeded by `sha256(id+title+index)` so results are stable; `tension_level`, `cliffhanger_value`, and three narrative dimensions (`emotional_goal`, `conflict_point`, `reveal_or_turning_point`) picked from curated pools.
- `enhance_image_prompt` / `enhance_video_prompt` / `improve_scene_drama` / `improve_scene_dialogue` — folder of mock transforms.

### Backend — new endpoints
- `POST /api/projects/{id}/quality-score` — recompute scores on demand.
- `POST /api/projects/{id}/improve-story` body `{kind}` (7 allowed kinds) — applies a mock improvement, refreshes scores, pushes an entry into `improvement_history`.
- `POST /api/scenes/{id}/enhance-prompt` body `{kind}` (4 allowed kinds: image-prompt, video-prompt, scene-drama, dialogue).
- `GET /api/creative/enhancement-hints` — static traits/hints/kinds catalog for the UI.

### Backend — auto-population
- `rewrite_story` now auto-computes `quality_scores` and returns them inline.
- `split_scenes` now auto-populates `raw_visual_prompt` + `enhanced_image_prompt/video_prompt` + 5 tension fields on every new scene.
- **Startup backfill** `_backfill_creative_quality()` runs once on app boot to attach the new fields to any project/scene created before this release. Idempotent.

### Frontend
- New `Creative` namespace in `lib/api.js` (hints / recomputeScore / improveStory / enhanceScene).
- New shared components: `QualityScorePanel.jsx` (6 bars + big overall number with color thresholds), `ImproveStoryMenu.jsx` (DropdownMenu with the 7 mock kinds), `SceneTensionMeter.jsx` (tension bar + 4 narrative rows + Improve drama / Improve dialogue actions).
- `StoryTab.jsx` — Improve story button beside Save in the Episode draft header; QualityScorePanel below the two main cards.
- `SceneCard.jsx` — `SceneTensionMeter` at the bottom of every scene card; updates instantly when drama/dialogue is improved.
- `ImagesTab.jsx` — quality hint banner ("This image prompt is enhanced for: realism, lighting, character consistency, camera framing"), per-card **Enhance** button + green "enhanced" chip; image card now shows the enhanced prompt when present.
- `VideoSegmentsTab.jsx` — quality hint banner ("This video prompt is enhanced for: motion, continuity, emotion, camera movement"), per-scene-block **Enhance prompt** button + "enhanced" chip beside the scene number.

### Tests — **102/102 passing** (was 93, +9)
- `test_story_quality_scores_populated_after_rewrite` — all 7 keys present, each 1–100, persisted on project document.
- `test_improve_story_endpoint_updates_story_and_scores` — story changes, cliffhanger_strength rises after a `cliffhanger` improvement (deterministic), `improvement_history` grows by one entry tagged with the kind.
- `test_improve_story_unknown_kind_rejected` — pydantic Literal rejects unknown kinds (422).
- `test_scenes_have_tension_fields_after_split` — every scene has tension/goal/conflict/turning/cliffhanger + prompt fields.
- `test_enhance_image_and_video_prompt` — each kind populates the right field and leaves others alone.
- `test_improve_scene_drama_and_dialogue` — drama bumps tension_level + heightens dialogue; dialogue-only updates only dialogue.
- `test_creative_hints_endpoint` — catalog shape.
- `test_existing_rewrite_split_generate_expand_export_still_work` — full pipeline regression.
- `test_provider_activity_remains_mock_after_quality_work` — 200/200 activity rows still `mode=mock`, `key_present=false` after running Creative Quality flows.

### Mock-only invariants — re-verified
- No new real-network code. `providers/` package still empty of http imports. `creative_quality.py` is pure-Python (hashlib, random, re).
- All `USE_REAL_*_PROVIDER` flags `false`. `key_present()` always `False`.
- Every existing `provider_activity` row remains `mode=mock`.
- No API key inputs added. No Stripe. No auth.

### Files changed (10)
**Added** (4): `backend/creative_quality.py` · `frontend/src/components/studio/QualityScorePanel.jsx` · `frontend/src/components/studio/ImproveStoryMenu.jsx` · `frontend/src/components/studio/SceneTensionMeter.jsx`
**Modified** (6): `backend/server.py` (imports, auto-score in rewrite, auto-tension in split, 4 new endpoints, startup backfill) · `backend/tests/backend_test.py` (9 new cases) · `frontend/src/lib/api.js` (Creative namespace) · `frontend/src/pages/tabs/StoryTab.jsx` · `frontend/src/pages/tabs/ImagesTab.jsx` · `frontend/src/pages/tabs/VideoSegmentsTab.jsx` · `frontend/src/components/studio/SceneCard.jsx`

### Frontend status
- ESLint clean across `/pages/` and `/components/`.
- Production build OK (24.95s).
- Testing agent iteration_4: 100% backend, 100% frontend, 0 issues, retest_needed=false.

## Iteration 20 (2026-02) — Episode Arc Visualizer (frontend-only)
**Goal**: turn "I have a feeling Act 2 is flat" into a glance.

### Frontend
- New `EpisodeArcStrip.jsx` at the top of the Scenes tab. One bar per scene, bar height = `tension_level / 100`, bar color tracks the same green→yellow→orange→red threshold as the tension meter on each card.
- Native `title` tooltip on each bar surfaces: scene title, tension level, emotional goal, conflict point, cliffhanger value.
- Interpretation label (rule-based, deterministic):
  - `Flat tension curve` — max − min < 15.
  - `Strong climax build` — last third is highest AND the last value ≥ 75.
  - `Middle sag detected` — middle third avg is ≥ 5 below both ends.
  - `Rising tension arc` — last third ≥ first third + 8.
  - `Falling tension arc` — first third ≥ last third + 8.
  - `Steady tension` — none of the above.
- Reuses the existing `scenes[*].tension_level` data — **zero new endpoints, zero new DB fields, zero new backend code**.
- Frontend-light: ~95 lines of inline JSX/CSS, no SVG library.

### Mock-only invariants — preserved
- No real-network code anywhere. `providers/` package still empty of http imports. `creative_quality.py` unchanged.
- All `USE_REAL_*_PROVIDER` flags `false`. `key_present()` always `False`.
- No API key inputs, no Stripe, no auth, no real LLM wiring.

### Checks
- Backend pytest: **102/102 passing** (unchanged from iteration 19 — this iteration is frontend-only).
- ESLint: clean across `/pages/` and `/components/`.
- Production build: OK (26.11s, ~180 kB gzip).
- Defensive grep for network imports in `providers/` + `creative_quality.py`: clean.

### Files changed (2)
**Added** (1): `frontend/src/components/studio/EpisodeArcStrip.jsx`
**Modified** (1): `frontend/src/pages/tabs/ScenesTab.jsx` — imports + renders `<EpisodeArcStrip scenes={scenes} />` right under the InfoCallout.

### Hold
Stopped before Phase 2B real-LLM wiring per user. The next milestone is the **Emergent universal LLM key → real LLM provider** wiring (LLM modality only).


## Iteration 22 (2026-02) — Safe delete + Undo + 24h purge
**Goal**: replace the hard cascade-delete with a recoverable soft-delete flow so accidental clicks are undoable.

### Backend
- **`DELETE /api/projects/{id}` is now a soft-delete.** Sets `deleted_at`, `deleted_by="user-demo"`, `delete_expires_at = now + 24h`, `previous_status`, and flips `status="deleted"`. Child scenes/characters/segments are intentionally untouched so restore is a true round-trip. Response:
  ```json
  { "ok": true, "soft_deleted": true, "project_id": "...",
    "deleted_at": "...", "delete_expires_at": "...", "previous_status": "draft" }
  ```
  Idempotent: a second DELETE returns `already_deleted: true`. Unknown id returns `{ok:true, soft_deleted:false, exists:false}` (no 404 churn for the frontend).
- **`POST /api/projects/{id}/restore`** — clears `deleted_at/deleted_by/delete_expires_at/previous_status` via `$unset`, restores `status` from `previous_status` (default `"draft"`). Returns the restored project. 404 only when the id is truly unknown; restoring an already-active project is a safe no-op that returns the project as-is.
- **`POST /api/admin/purge-deleted-projects`** — permanently removes only projects whose `delete_expires_at <= now`. Cascades to scenes/characters/segments AND drops `provider_activity` rows scoped to those `project_id`s (health-only rows without project scope are not swept). Returns `{ok, purged: {projects, scenes, characters, segments}}`.
- **List/get hidden by default**: new `_active_project_filter()` helper hides any project with a non-null `deleted_at`. `GET /api/projects` excludes them; `GET /api/projects/{id}` returns 404 unless `?include_deleted=true`. `PUT /api/projects/{id}` also runs through the same filter so soft-deleted projects cannot be silently updated.

### Frontend
- `lib/api.js` — `Projects.restore(id)` helper added.
- `Dashboard.jsx` — `onDelete` no longer opens an AlertDialog. Click → optimistic remove from grid → `Projects.remove()` → sonner toast `Deleted "<title>"` with `action: { label: "Undo" }` and `duration: 5000`. Undo calls `Projects.restore(id)` then `Projects.list()` to refresh `cost_summary` and re-inserts the card. On delete failure, the optimistic removal is rolled back and an error toast fires.
- ProjectCard simplified — the AlertDialog and its imports are gone; the trash button is the single source of the delete action.

### Tests — **116/116 backend** (was 111, +8 new, −3 obsolete hard-cascade cases)
- `test_delete_project_is_soft_delete` — response shape; list excludes; GET 404; child data preserved in Mongo (6 scenes, 2 chars, 2 segments).
- `test_restore_project_brings_it_back` — round-trip; status returns to an active value; card visible again.
- `test_restore_unknown_project_returns_404`.
- `test_delete_unknown_project_is_safe` — `{ok:true, soft_deleted:false, exists:false}`.
- `test_delete_does_not_touch_other_projects` — B still has its scenes/segments after A is soft-deleted.
- `test_purge_removes_expired_projects_and_their_children` — force-expire via Mongo → purge endpoint cascades scenes/chars/segments away.
- `test_purge_does_not_touch_active_or_non_expired_projects` — newly soft-deleted (24h-fresh) and active projects are left alone.
- `test_delete_then_restore_is_idempotent` — second DELETE has `already_deleted:true`; second restore on an active project returns the project (no 404).

### Testing agent (iteration_5)
- Backend 116/116. 11/11 curl-smoke endpoint contracts verified on the live preview URL.
- Frontend end-to-end: trash hover → click → toast with Undo → Undo restores → expiry path stays hidden after refresh → stats recompute 3/2 → 4/3 → 3/2 → 4/3 → 3/2 across the flow. Zero console errors. 0 bugs found, 0 action items.

### Mock-only invariants — re-verified
- `providers/` package still contains zero http imports outside `llm_real.py`.
- All five non-LLM `USE_REAL_*_PROVIDER` flags remain `false` and `key_present_for_modality()` returns `False` for them regardless.
- No API key input fields. No Stripe. No auth.

### Files changed (3)
**Modified**: `backend/server.py` (delete/restore/purge endpoints + `_active_project_filter` + listing/get/update filters), `backend/tests/backend_test.py` (8 new tests, replaced the 3 old hard-cascade tests), `frontend/src/pages/Dashboard.jsx` (undo toast flow, AlertDialog removed), `frontend/src/lib/api.js` (Projects.restore added).

### Backlog (P1) — refreshed
- Character drag handles in Cast view (completed later in Iteration 24).
- Background scheduler for the 24h purge (currently manual `POST /api/admin/purge-deleted-projects`).
- Real provider plug-ins for non-LLM modalities behind feature flags + at-rest secrets store.


## Iteration 23 (2026-02) — Background purge scheduler + Admin "Recently Deleted" panel
**Goal**: close out the safe-delete feature with automatic cleanup + an ops view that lets admins restore mistakes that slip past the 5-second toast.

### Backend
- **Shared helper** `_purge_expired_projects_now()` extracted from the admin endpoint. Cascades projects/scenes/characters/segments + scoped `provider_activity` rows for any project where `deleted_at != null` and `delete_expires_at <= now`. Returns counts dict (no `ok` wrapper).
- **Background scheduler** wired into FastAPI startup:
  - Initial purge runs once on boot.
  - Then sleeps for `DELETED_PROJECT_PURGE_INTERVAL_MINUTES` (default `60`, env-tunable) and repeats.
  - Setting the env var to `0` disables the scheduler (useful for tests).
  - Implemented as a single `asyncio.create_task(_loop())`; exception in either the initial purge or the loop is caught + logged so a transient Mongo blip cannot crash the app.
  - Shutdown handler cancels the task and awaits its `CancelledError`.
  - Log lines never emit project ids, only counts — keeps logs safe-metadata only.
- **New endpoint** `GET /api/admin/deleted-projects` — returns soft-deleted projects still inside their restore window (`delete_expires_at > now`), sorted by `deleted_at` desc, with child counts (`scenes_count`, `characters_count`, `segments_count`) and the prior status for context.

### Frontend
- `lib/api.js` — added `Admin.deletedProjects()`.
- `Admin.jsx`:
  - New tab **Recently Deleted** with a count badge (red pill) when the panel has items.
  - Columns: Title · Deleted at · Restore until · Scenes · Characters · Segments · Restore button.
  - Restore button calls `Projects.restore(id)`, removes the row optimistically, decrements the count badge, and shows a `Restored "X"` toast (`data-testid="admin-project-restore-toast"`).
  - Empty state: friendly card when nothing is in the window.
  - Refresh button to re-pull the list on demand.

### Tests — **119/119 backend** (was 116, +3 new)
- `test_admin_deleted_projects_lists_unexpired_only` — seeds two soft-deleted projects, force-expires one, asserts only the fresh one is in `/admin/deleted-projects` and the row carries the correct counts (6 scenes / 2 characters / 2 segments) plus a `delete_expires_at > deleted_at` invariant.
- `test_admin_deleted_projects_restore_round_trip` — soft-delete → endpoint shows it → POST /restore → endpoint excludes it → main `/api/projects` listing includes it again.
- `test_purge_helper_only_purges_expired_deleted_projects` — three projects (active, fresh-soft, expired-soft). After purge: active intact (visible via API), fresh-soft intact in Mongo (still within 24h), expired-soft fully cascaded (project + 6 scenes + 2 chars + 2 segments all gone, restore returns 404).

### Config
- New env var `DELETED_PROJECT_PURGE_INTERVAL_MINUTES=60` added to `backend/.env`. Read via `_int_env` so misconfigurations don't crash startup.

### Mock-only invariants — re-verified
- No real-network code touched. `providers/` package unchanged.
- All five non-LLM `USE_REAL_*_PROVIDER` flags remain `false`. No API key inputs. No Stripe. No auth.

### Files changed (4)
**Modified**:
- `backend/server.py` — `asyncio` import, `_purge_expired_projects_now()` helper, `admin_purge_deleted_projects` simplified to call it, new `admin_deleted_projects` endpoint, `_start_purge_scheduler()` + `_purge_task` globals, startup/shutdown wiring.
- `backend/.env` — `DELETED_PROJECT_PURGE_INTERVAL_MINUTES=60`.
- `backend/tests/backend_test.py` — 3 new tests (admin listing, restore round-trip, purge helper scoping).
- `frontend/src/pages/Admin.jsx` — new tab, panel state, restore handler, count badge.
- `frontend/src/lib/api.js` — `Admin.deletedProjects` added.

### Status checks
- Backend pytest: **119/119** in 32s.
- Backend lint: clean.
- Frontend ESLint: clean.
- Production build: OK (~191 kB gzip).
- Admin "Recently Deleted" tab smoke-tested live (renders pre-existing 133 entries from prior test runs, count badge visible, columns + Restore buttons present, no console errors).


## Iteration 24 (2026-05) — Character drag handles in Cast view
**Goal**: close the remaining P1 reorder gap by matching scene and segment
drag behavior for characters.

### Backend
- Character documents now support `order`.
- Existing/legacy characters without `order` are backfilled based on current
  chronological order (`created_at`, then id) whenever project characters are
  read.
- New endpoint:
  ```http
  PUT /api/projects/{project_id}/characters/reorder
  ```
  Payload:
  ```json
  { "character_ids": ["char1", "char2", "char3"] }
  ```
- The endpoint validates that the list includes every character for the
  project exactly once, rejects foreign/partial lists, updates `order` from
  list position, and returns characters sorted by `order`.

### Frontend
- CharactersTab / Cast view now renders character cards inside the shared
  `SortableList`.
- Each character card has a drag handle.
- Reorder is optimistic: the UI updates immediately, calls the reorder API,
  keeps the order on success, and restores the previous order with a toast on
  failure.
- Edit and delete actions remain independent of the drag handle.

### Current reorder status
- Scene reorder: implemented.
- Segment reorder: implemented.
- Character reorder: implemented.

### Current delete/provider status
- Soft delete / restore / Recently Deleted / purge are implemented.
- Real LLM is gated behind `USE_REAL_LLM_PROVIDER`.
- Image / Video / Voice / Music / Export providers remain mock-only.

### Backlog after Iteration 24
- P1 completed: Character drag handles in Cast view; Safe delete / Undo delete;
  Recently Deleted admin panel; Background purge scheduler.
- P2 remaining has since moved on: production auth/user ownership hardening,
  real credit wallet tied to users and Stripe fulfillment, Stripe checkout/
  webhook work, real Image/Video/Voice/Music providers, Real Export/FFmpeg
  worker, asset storage, Public sharing, Multi-tenant teams, and Versioned
  scene revisions.


## Iteration 21 (2026-02) — Phase 2B: Real LLM provider (LLM modality only)
**Goal**: ship the first real provider for AI Episode Studio. Strictly LLM-only. All other modalities remain permanently mock-pinned.

### What's real now
- `story rewrite`, `improve story`, `enhance scene prompt (image-prompt | video-prompt | scene-drama | dialogue)` can now call the **real LLM** via a configured server-side LLM runtime when `USE_REAL_LLM_PROVIDER=true`. Default flag is `false`.
- Default model: `openai/gpt-5.2` (configurable via `LLM_REAL_PROVIDER` / `LLM_REAL_MODEL` env, falls back to whatever's resolved in global/project settings).
- Real call timeout: 25s (`DEFAULT_TIMEOUT_S`). On timeout / exception / empty output → deterministic mock fallback runs and a second activity row is logged with `status="fallback"`.
- Verified live: a real `openai/gpt-5.2` call returned `mode=real, status=success, duration_ms=108300` end-to-end (then flag flipped back to `false`).

### What's still locked
- `USE_REAL_IMAGE_PROVIDER`, `USE_REAL_VIDEO_PROVIDER`, `USE_REAL_VOICE_PROVIDER`, `USE_REAL_MUSIC_PROVIDER`, `USE_REAL_EXPORT_PROVIDER` — all `false` AND hard-pinned to mock in code: `key_present_for_modality()` returns `False` for them unconditionally. Flipping the flag does nothing — the executor still runs the mock.
- No API key input fields on the UI. No Stripe. No auth. No per-user API key storage.

### Backend
- **New** `/app/backend/providers/llm_real.py`:
  - `RealLLMProvider(BaseProvider)` — `is_mock=False`, `requires_api_key=True`. `async run(prompt, system=None, max_tokens=600, timeout=25.0) → ProviderResult` using `emergentintegrations.llm.chat.LlmChat`. Captures `duration_ms` + `provider_job_id` (uuid4) + error message. Caps error text at 500 chars.
  - `real_llm_available()` — True only when `EMERGENT_LLM_KEY` is set AND `emergentintegrations` is importable.
- **Rewrote** `/app/backend/providers/keys.py`:
  - `key_present_for_modality(modality, provider)` — returns True only for `"llm"`, gated by `real_llm_available()`. **Always False for every other modality.**
  - `key_present(provider)` — legacy single-arg signature kept; treats provider as LLM-eligible only if its id is in `_LLM_PROVIDER_IDS = {openai, anthropic, gemini, mock-llm}`.
- **Updated** `/app/backend/providers/executor.py`:
  - `execute_provider()` now uses `key_present_for_modality()` (modality-aware) instead of provider-name-only `key_present()`. Image/video/voice/music/export always run mock — even with flag on, they end up with `status="blocked"` because `key_present=False`.
  - **New** `execute_llm(prompt, system?, project, global_settings, ...)`. Dispatches to `RealLLMProvider` on flag+key, falls back to mock on failure. Writes one activity row for the real attempt + one for the mock fallback (when applicable). Records carry the `real`/`mock`/`fallback` status correctly.
  - `provider_status()` now exposes `real_capable: bool` (True only for `llm`).
- **Updated** `server.py`:
  - `rewrite_story` — runs the deterministic mock baseline + calls `execute_llm(prompt=...)` with the idea + baseline. If real returns non-empty text → use it. Response now includes `llm_mode: "mock"|"real"|"fallback"`.
  - `improve_story` — same pattern; the improvement-history entry now carries `llm_mode`.
  - `enhance_scene_prompt` — same pattern for all 4 kinds (image-prompt / video-prompt / scene-drama / dialogue). Real LLM output replaces the deterministic baseline when available.
- **New env keys** (in `/app/backend/.env`): `EMERGENT_LLM_KEY=sk-emergent-...`, `LLM_REAL_MODEL=gpt-5.2`, `LLM_REAL_PROVIDER=openai`. **All 6 USE_REAL_*_PROVIDER flags remain `false`.**

### Frontend
- **New** `LLMModeBanner` on the Providers tab (top of the page):
  - When `feature_flags.llm = true` → green "Real LLM enabled" banner with explanation.
  - Otherwise → grey "Mock LLM active" banner. Reminds the user that other modalities are mock-only regardless.
- **Updated** `GuardStateRows`: for LLM specifically, the "Key status" row now reads `configured` and "Real call" reads `real-capable · flag off` (instead of the universal `blocked · mock-only` shown for other modalities).

### Tests — **111/111 passing** (was 102, +9 Phase 2B + 1 renamed)
**New file** `tests/test_phase2b_llm.py` (8 cases):
- `test_real_llm_blocked_when_flag_off` — flag off → mock runs cleanly (status=success).
- `test_real_llm_blocked_when_key_missing` — flag on, key removed → mock runs, status=blocked.
- `test_real_llm_fallback_when_real_raises` — flag on, real LLM patched to return `status=failed` → caller receives mock-mode `ProviderResult` with `status="fallback"`; activity log contains both `"failed"` and `"fallback"` rows.
- `test_non_llm_modalities_never_run_real_even_with_flag_on` (parametrized × 5: image/video/voice/music/export) — flag flipped on for each, `key_present` remains `False`, mock runs with `status="blocked"`, `provider_status.real_capable=False`.
- `test_provider_status_llm_is_real_capable` — `real_capable=True` only for LLM.

**Updated** existing assertions to reflect Phase 2B (LLM `key_present=True` is now allowed; non-LLM still must be `False`):
- `_assert_record_is_safe` no longer enforces `mode=mock` globally; that invariant is asserted only inside the scoped test.
- `test_provider_activity_remains_mock_when_flag_off_after_quality_work` (renamed) — scoped to rows owned by the test's `project_id` so legacy real-mode rows from other test runs / manual flag flips don't pollute it.

### Hard guarantees (verified)
- `grep -rn "emergentintegrations\|openai\.\|requests\.\|httpx\.|aiohttp" /app/backend/providers/ /app/backend/creative_quality.py /app/backend/server.py` → only matches inside `providers/llm_real.py` and `providers/keys.py` (the latter is a *lazy import* to ask `real_llm_available()`).
- `creative_quality.py`, `server.py`, and all other modality endpoints contain **zero** real-network code.
- Image / Video / Voice / Music / Export remain **mock-only by construction** — not by flag — because `key_present_for_modality()` returns False for them regardless of env.

### Files changed (8)
**Added** (2): `backend/providers/llm_real.py`, `backend/tests/test_phase2b_llm.py`
**Modified** (5): `backend/providers/__init__.py` (export `execute_llm`), `backend/providers/keys.py` (rewritten — modality-aware), `backend/providers/executor.py` (modality-aware guard + `execute_llm` + `_record` helper + `real_capable`), `backend/server.py` (rewrite / improve / enhance now call `execute_llm`), `backend/tests/backend_test.py` (loosened `_assert_record_is_safe` + renamed/scoped one test)
**Modified frontend** (1): `frontend/src/pages/tabs/ProvidersTab.jsx` (LLMModeBanner + LLM-aware GuardStateRows copy)
**Env** (1): `backend/.env` — added `EMERGENT_LLM_KEY`, `LLM_REAL_MODEL=gpt-5.2`, `LLM_REAL_PROVIDER=openai`. All 6 `USE_REAL_*_PROVIDER` remain `false`.

### Status checks
- Backend pytest: **111/111**.
- ESLint: clean.
- Production build: OK (27.59s).
- Real LLM end-to-end test: ✅ verified live (gpt-5.2 round-trip with `mode=real, status=success`).
- Defensive grep: only `llm_real.py` carries real-network code; no other modality has any http imports.
