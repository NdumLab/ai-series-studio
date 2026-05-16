# AI Series Studio MVP Plan

## A. Product Vision

AI Series Studio is a story-to-episode platform that helps creators turn a
rough story idea into a captivating short AI episode. The product combines
story improvement, scene planning, character management, prompt enhancement,
media generation, export, and future publishing workflows into one guided
studio.

The near-term MVP should let a creator move from idea to finished short episode
with enough quality control, cost control, and provider observability to run a
private beta safely.

## B. Current MVP Status

Completed today:

- Story workflow: project creation, idea entry, story rewrite, editable draft,
  improve-story actions, and quality scoring.
- Scene workflow: scene splitting, scene editing, scene tension scoring, prompt
  enhancement, image/video prompt surfaces, and scene reorder.
- Character workflow: Cast view, character CRUD, per-character voice override,
  character `order`, and character drag handles/reorder.
- Auth and ownership: local email/password beta accounts, bearer sessions,
  per-user project scoping, and `AUTH_DEMO_MODE=true` compatibility for
  no-token local demos.
- Reorder workflows: scenes, segments, and characters all support persisted
  ordering with optimistic frontend updates.
- Creative Quality Engine: story scores, scene tension fields, improvement
  helpers, and prompt enhancement helpers.
- Provider architecture: provider catalog, global settings, per-project
  overrides, effective provider resolution, guard/status endpoints, provider
  activity logging, and provider health pulse.
- Real LLM gating: real LLM support exists for story/text operations behind
  `USE_REAL_LLM_PROVIDER`, with mock fallback.
- Mock non-LLM providers: Image, Video, Voice, Music, and Export remain
  mock-only.
- Cost tracking: operation costs, project/scene estimates, wallet ring,
  high-cost scene warnings, trend deltas, reduce-to-draft, per-user credit
  balances, and insufficient-credit blocking for generation actions.
- Admin monitoring: stats, users, projects, generations, failed jobs, provider
  activity, provider health, and Recently Deleted.
- Soft delete/restore: dashboard undo, restore endpoint, Admin Recently
  Deleted panel, and background purge scheduler.
- Developer setup: backend requirements, frontend lockfile, env examples,
  README setup, Makefile, dev-check script, frontend lint, and build commands.

## C. What "100% MVP Complete" Means

MVP complete means:

1. User can create an account or use a controlled beta login.
2. User can create a project.
3. User can enter a story idea.
4. App improves the story using real LLM.
5. App creates strong scenes.
6. User can edit story/scenes/characters/prompts.
7. User can generate real images.
8. User can generate real short video segments.
9. User can expand segments by 5 seconds.
10. User can generate or attach voice/music.
11. User can export a final MP4.
12. User can see cost before generation.
13. User cannot accidentally overspend credits.
14. Admin can monitor provider activity and failures.
15. The app has basic auth and project ownership.
16. The app is deployable and documented.

## D. MVP Completion Checklist

Completed:

- [x] Mock workflow.
- [x] Story/scene/character editing.
- [x] Creative Quality Engine.
- [x] Scene, segment, and character reorder.
- [x] Provider abstraction.
- [x] Real LLM gated behind `USE_REAL_LLM_PROVIDER`.
- [x] Soft delete / restore / purge.
- [x] Admin monitoring.
- [x] Local setup docs.
- [x] Basic auth and project ownership.
- [x] Basic credit wallet and generation guardrails.

Remaining:

- [ ] Real image provider.
- [ ] Real video provider.
- [ ] Real voice provider.
- [ ] Real music/SFX provider.
- [ ] Real FFmpeg export worker.
- [ ] S3/R2 storage.
- [ ] Stripe test metering.
- [ ] Production deployment.
- [ ] Basic rate limiting.
- [ ] End-to-end real media test.

## E. Recommended Build Order From Here

### Phase 1: Auth and ownership

- Completed: add login/register.
- Completed: support real beta users while preserving `user-demo` local mode.
- Completed: ensure projects belong to the authenticated user.

### Phase 2: Credit wallet and cost guardrails

- Completed: replace display-only wallet with per-user credit balances.
- Completed: add credit deduction/reservation for generation actions.
- Completed: add insufficient-credit blocking.
- Remaining: Stripe test metering belongs to Phase 3 after wallet logic is
  stable.

### Phase 3: Stripe test metering

- Add Stripe test integration.
- Keep test mode only.
- Do not enable live payments.

### Phase 4: Real image provider

- Add one real image provider first.
- Generate character images.
- Generate scene images.
- Keep video mocked.

### Phase 5: Real video provider

- Add one real video provider.
- Start with 5-second segments.
- Keep Expand Next 5 Seconds gated and cost-controlled.

### Phase 6: Real voice/music

- Add voice provider.
- Add music/SFX provider.
- Keep optional upload fallback.

### Phase 7: Real export

- Add FFmpeg worker.
- Merge approved clips.
- Add voice/music/subtitles.
- Store final MP4 in S3/R2.

### Phase 8: Private beta

- Invite limited testers.
- Cap credits.
- Monitor provider activity.
- Collect feedback.

## F. Cost Control Plan

Do not allow unlimited generation. Every generation must estimate credits
before execution, and expensive jobs must be constrained by wallet and project
budget state.

Video is the most expensive provider and should be introduced with low test
budgets, per-scene warnings, and project-wide budget warnings. Before expensive
generation, either charge credits up front or reserve credits before job
execution. Refund credits on provider failure where appropriate.

Required guardrails:

- Show estimated credits before generation.
- Block insufficient-credit actions.
- Cap private beta credits per user.
- Track credits at user, project, scene, and provider-job levels.
- Log provider failures so refunds and provider reliability can be audited.

## G. Provider Strategy

- LLM is already the first real provider.
- Image comes next.
- Video comes after image quality is proven.
- Voice/music/export come after core visual generation works.
- Image/video/voice/music/export remain blocked until secrets storage is
  designed.

This order limits spend and debugging complexity: prove story quality first,
then still-image quality, then the more expensive video pipeline.

## H. Secrets Strategy

- Do not store provider keys in MongoDB.
- Do not store real provider keys in frontend code or browser storage.
- Do not commit keys.
- Short-term: Emergent universal key for LLM only.
- Future AWS deployment: use AWS SSM Parameter Store `SecureString` or AWS
  Secrets Manager.
- Store only secret references in the database.

The application should resolve provider credentials server-side at execution
time. UI provider settings should store provider/model selections, not secrets.

## I. Testing Strategy

Agents and developers should run:

- Backend provider/unit tests.
- Full backend HTTP tests when FastAPI + MongoDB are available.
- Frontend lint.
- Frontend production build.
- Smoke tests where possible.

Backend provider/unit tests:

```bash
backend/.venv/bin/python -m pytest backend/tests/test_provider_layer.py backend/tests/test_phase2b_llm.py
```

Full backend HTTP tests:

```bash
REACT_APP_BACKEND_URL=http://localhost:8000 backend/.venv/bin/python -m pytest backend/tests/backend_test.py
```

Frontend checks:

```bash
cd frontend
node_modules/.bin/eslint src --max-warnings=0
node_modules/.bin/craco build
```

## J. Launch Criteria

MVP is launch-ready when:

- Auth works.
- Credit system works.
- Real LLM works.
- Real image generation works.
- Real video segment generation works.
- Export produces final MP4.
- Storage works.
- Cost limits work.
- Admin monitoring works.
- Full tests pass.
- At least 3 sample episodes are generated successfully.
- Internal cost per 1-minute video is understood.

## K. What is Not MVP

Post-MVP:

- Social media auto-posting.
- Public sharing.
- Multi-tenant teams.
- Versioned scene revisions.
- Advanced collaboration.
- Mobile app.
- Multiple provider marketplace.
- Full timeline editor.
- Advanced lip-sync.
- Automatic weekly publishing calendar.
