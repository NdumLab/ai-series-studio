# AI Episode Studio — PRD

## Problem Statement
Build a full-stack web MVP called AI Episode Studio that helps creators generate complete 1–3 minute AI story videos from characters, scenes, voice, music and short video clips. First version uses MOCK AI generation only (no real external APIs). Design the app so real providers can be added later for image, video, voice, music and FFmpeg export.

## Architecture
- Backend: FastAPI + MongoDB (relational-style schemas), all routes under `/api`
- Frontend: React (CRA + craco) + Tailwind + shadcn/ui, dark cinematic theme (Outfit + IBM Plex Sans), red accent #FF3B30
- No auth — single demo user `user-demo` seeded on startup
- Mock generators return curated static URLs (Unsplash + Google sample mp4s) and log every generation

## Data Models (MongoDB collections)
- users: id, name, email, role, credits, created_at
- projects: id, user_id, title, idea, rewritten_story, status, created_at, updated_at
- characters: id, project_id, name, description, voice_style, reference_image_url
- scenes: id, project_id, order, title, duration, location, characters[], visual_prompt, dialogue, music_mood, camera_direction, voice, image_url, status
- segments: id, scene_id, project_id, order, video_url, duration, status (pending/approved/rejected)
- generations: id, user_id, project_id, type, cost_credits, status, error, created_at

## Costs (credits)
rewrite 3 · split_scenes 4 · image 2 · video_segment 5 · voice 1

## Implemented (2026-02)
- Projects CRUD, rewrite, split-into-6-scenes
- Scene CRUD with full field set (incl. dialogue, music_mood, camera_direction, voice, characters tags)
- Character CRUD with placeholder portrait
- Mock image generation (curated URL pool, 5% mock failure to populate admin failed jobs)
- Mock 5s video segment generation, "Expand next 5s", approve/reject/regenerate
- Cost estimator (POST /api/cost-estimate + GET /api/projects/{id}/cost-estimate)
- Final Export page with stitched preview (mock final video URL)
- Admin console: stats + users/projects/generations/failed jobs tables
- 17/17 backend tests passing, frontend e2e flow validated

## Backlog (P1)
- Cascade-delete segments when project is deleted (orphan segments today)
- Real provider plug-ins: image (fal.ai / Gemini Nano Banana), video (Sora 2), voice (ElevenLabs / OpenAI TTS), music (Suno-style), FFmpeg export worker
- Per-character voice override on each scene
- Drag-and-drop reorder of scenes & segments
- Authentication (Emergent Google login or JWT)

## Backlog (P2)
- Public project sharing with watermark
- Credit purchase + Stripe metering
- Multi-tenant teams with role-based admin
- Versioned scene revisions / undo

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
- **Character drag handles** officially **backlogged** (P1) per user — no scope creep this iteration.
- Mock-only invariants preserved; no real provider wiring, no API key fields, no Stripe.

## Backlog (P1) — refreshed
- Character drag handles in Cast view (deferred from iteration 12; requires `order` field on Character model + `PUT /api/projects/{id}/characters/reorder`).
- **Safe delete / Undo delete** — replace hard cascade-delete with a recoverable flow:
  1. Soft-delete first: add `deleted_at`, `deleted_by`, `delete_expires_at` to projects (and propagate hiding for child resources).
  2. Hide soft-deleted projects from the dashboard list endpoint.
  3. Frontend shows a 5-second toast with an **Undo** action.
  4. Undo calls `POST /api/projects/{id}/restore` to revive the project + its scenes/characters/segments.
  5. If no Undo arrives, a background cleanup job (or `DELETE /api/projects/{id}/purge`) performs the permanent cascade after `delete_expires_at`.
  - Future endpoints: `DELETE /api/projects/{id}` → soft delete · `POST /api/projects/{id}/restore` → restore · `DELETE /api/projects/{id}/purge` → permanent delete.
  - Out of scope today: frontend-only restore would be misleading because the data is truly gone — explicitly NOT shipped in iteration 15.
- Real provider plug-ins behind feature flags: LLM, image, video, voice, music, export.
- API key inputs + storage (locked until real-provider mode is activated).

## Backlog (P2)
- Stripe metering + real credit purchases (replaces 250-credit mock wallet).
- Authentication (Emergent Google login or JWT).
- Public project sharing with watermark.
- Multi-tenant teams with role-based admin.
- Versioned scene revisions / undo.


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
