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
