# MVP Auth And Ownership Plan

## Goal

AI Series Studio needs reliable user identity and project ownership before real
checkout, webhook credit fulfillment, paid provider calls, or private beta
usage. Billing, credits, provider usage, and generated assets all need a stable
owner.

The repo already has local MVP auth scaffolding: email/password beta accounts,
bearer sessions, per-user project scoping, and `AUTH_DEMO_MODE=true` for local
demo compatibility. This plan defines the production-ready path before paid MVP
work.

## Why Auth Comes Before Real Stripe Or Paid Providers

- Stripe checkout sessions must map to a real app user.
- Stripe webhooks must credit the correct user idempotently.
- Credit reservations and refunds must be tied to a user, not `user-demo`.
- Provider activity and failure monitoring must be attributable per user.
- Asset storage paths and permissions need a durable owner.
- A paid provider failure or webhook retry without ownership can create wrong
  credits, leaked projects, or unbillable usage.

Do not proceed with real Stripe checkout/webhooks or paid media providers until
ownership is enforced outside demo mode.

## Option 1: Emergent Google Login

Pros:

- Fastest user-facing login path if the deployment platform provides it.
- Removes password handling from the app.
- Lower security surface for MVP.
- Good fit for controlled beta access.

Cons:

- Platform-dependent.
- Local development still needs a fallback mode.
- Need to map provider identity to internal `users.id`.
- Future team membership still needs app-side ownership models.

Backend changes:

- Accept trusted identity from the platform/session layer.
- Upsert user by provider subject/email.
- Require auth for non-demo environments.
- Keep `AUTH_DEMO_MODE=true` only for local development.
- Ensure every project query is scoped by `user_id`.

Frontend changes:

- Add login entry point that redirects to the platform Google flow.
- Show current account in the app shell.
- Handle logout and expired sessions.
- Keep local demo path documented for developers.

User model changes:

- Add `auth_provider`, `provider_subject`, and `last_login_at`.
- Keep `email`, `name`, `role`, `credits`, and `created_at`.
- Avoid storing provider access tokens unless needed later.

Project ownership changes:

- Keep `projects.user_id` as the owner.
- Ensure child resources remain scoped through project ownership.
- Add migration for existing `user-demo` projects if beta testers need them.

Risks:

- Platform coupling.
- Local/test parity can drift if demo mode is too permissive.
- Need clear handling for changed Google emails.

## Option 2: Custom JWT Auth

Pros:

- Platform-independent.
- Works locally, in staging, and on future AWS deployment.
- Easy to test without external login providers.
- Current local auth scaffolding is already close to this model.

Cons:

- App owns password/session security.
- Requires password reset, email verification, token expiry, rotation, and
  account recovery for production readiness.
- Higher operational responsibility.

Backend changes:

- Replace long-lived bearer sessions with signed, expiring access tokens and
  refresh sessions.
- Add password reset and optional email verification.
- Add `AUTH_DEMO_MODE=false` production mode enforcement.
- Add rate limits for login/register.
- Add audit fields for login and failed attempts.
- Keep all project and generation routes ownership-scoped.

Frontend changes:

- Harden login/register UX.
- Add expired-session handling.
- Add account/logout state in the app shell.
- Add clear private-beta messaging.

User model changes:

- Add password version or session invalidation timestamp.
- Add `email_verified`, `last_login_at`, and optional `disabled_at`.
- Keep credits on the user until team billing exists.

Project ownership changes:

- Current `projects.user_id` remains valid.
- Add tests that user A cannot read or mutate user B projects, scenes,
  characters, segments, provider overrides, exports, deleted projects, or
  provider status views.

Risks:

- Password auth can become a distraction from media MVP work.
- Security features must not be half-finished if beta testers are invited.
- JWT revocation needs refresh-token/session tracking.

## Option 3: Future Multi-Tenant Team Support

Pros:

- Matches the long-term shape for studios, shared workspaces, and team billing.
- Cleaner future path for roles, project sharing, and centralized credits.
- Supports organization-level Stripe customers later.

Cons:

- Too much for MVP if implemented now.
- Requires membership roles, invitations, team billing, ownership migration,
  admin UI, and more authorization tests.
- Slows down the path to real image/video/export validation.

Backend changes:

- Add `teams`, `team_members`, and `projects.team_id`.
- Move credits from user-level to team-level or support both.
- Add role checks: owner, admin, editor, viewer.
- Add migration from `projects.user_id` to `projects.team_id`.

Frontend changes:

- Add workspace switcher.
- Add invite/member management.
- Add team billing views.
- Add role-aware UI states.

User model changes:

- Users become identities, not billing containers.
- Team membership records carry roles.
- Credits likely move to `teams`.

Project ownership changes:

- Projects are owned by teams.
- User access is resolved through membership.
- Existing user-owned projects need migration into single-user teams.

Risks:

- Scope is beyond MVP.
- Authorization matrix is much larger.
- Billing and credit logic becomes more complex before the media pipeline is
  proven.

## Recommendation

Use the current local email/password auth as the MVP development baseline, but
production hardening should prefer a controlled Google login if the deployment
platform provides it cleanly.

Recommended MVP path:

1. Keep `AUTH_DEMO_MODE=true` for local development only.
2. Require authenticated users in staging/private beta with
   `AUTH_DEMO_MODE=false`.
3. If platform Google login is available, use it for private beta identity and
   map it into the existing `users` collection.
4. If platform login is not available, harden the current custom auth with
   expiring tokens, refresh sessions, login rate limiting, and password reset
   before opening beta access.
5. Defer multi-tenant teams until after the first paid single-user MVP works.

This keeps the MVP focused: one user owns projects, credits, generations,
provider activity, and assets. Teams can be introduced later by migrating each
single user into a default personal team.

## Demo User Migration

Current local/demo mode uses `user-demo`.

Migration path:

- Keep `user-demo` only for local seed/demo flows.
- For private beta, require login and create real users.
- Existing `user-demo` projects can remain sample data or be reassigned with a
  one-time admin migration script.
- Never attach Stripe customers, real provider spend, or production assets to
  `user-demo`.

## Tests Needed

- Register/login/me/logout success and failure paths.
- Auth required when `AUTH_DEMO_MODE=false`.
- Demo fallback works when `AUTH_DEMO_MODE=true`.
- User A cannot list/read/update/delete/restore User B projects.
- User A cannot mutate User B scenes, characters, segments, provider settings,
  exports, or deleted projects.
- Credit reservation and refund are scoped to the authenticated user.
- Stripe checkout session creation, when added, uses the authenticated user.
- Stripe webhook fulfillment, when added, is idempotent and credits the correct
  user.
- No API keys, password hashes, session tokens, or provider secrets appear in
  public API responses or provider activity logs.

## Not In This Auth Planning Pass

- No new runtime features.
- No Stripe SDK calls.
- No checkout sessions.
- No webhooks.
- No real media providers.
- No multi-tenant team implementation.
