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
