# Warpath HUB — Phase 2 handoff

> Historical baseline. Phase 3 continuation, exact validation and migration
> constraints are recorded in [PHASE3_HANDOFF.md](PHASE3_HANDOFF.md) and
> [PHASE3_MIGRATION.md](PHASE3_MIGRATION.md). Phase 2 findings below describe
> the pre-Phase-3 system.

Scope: strict authentication and tenant isolation only. Phase 1 audited
`c1061c68c232bbc61633691822cbfd7c3fafede1`; main matched that commit when
Phase 2 began. Branch: `codex/phase-2-auth-tenant-isolation`. This document
travels with the implementation commit; use the PR head as the next baseline.
No redesign, new motion, marketing, billing/signup, session migration,
worker split, Redis, protocol rewrite, deployment or merge.

## Changed behavior and entry points

| Area | Files | Contract |
|---|---|---|
| Authentication | `service/app/security/auth_config.py`, `deps.py`, `main.py`, `api/auth.py` | Production defaults to password sessions; zero password users still means 401. Explicit local mode requires development/test environment; production rejects it and insecure cookies. Validate startup config before DB/game I/O, including dotenv. No password-user enumeration to decide enforcement. |
| Roles/ownership | `deps.py`, `api/accounts.py`, `api/mass_deploy.py`, `scripts/bootstrap_dashboard_admins.py` | Only explicit member/admin roles log in. Missing/invalid cached session roles are denied and destroyed. Provisioning requires `--role`. Member account routes enforce ownership. Admin cross-owner access by ID remains an explicit operator capability; account lists remain owner-scoped for both roles. Manual import and all mass-deploy paths are admin-only. Existing diagnostics dependency now always enforces admin. |
| Linking | `core/link_challenge_store.py`, `api/link.py`, `schemas/link.py` | Every lookup, resend, attempt, verification and deletion is owner-bound, including for admins. Lock-protected send/verify claims precede Lilith calls. Busy operations return 409, foreign/expired IDs 410, cooldown/attempt limit 429. Only operator WARPATH env credentials authorize linking; no customer credential lookup. Missing config returns 503. |
| Secret handling | `api/link.py`, `main.py` | No verification code in store/events/logs. Generic upstream failure responses; leave upstream exception context before event persistence. Validation responses omit input fields. Successful verification consumes challenge before account persistence; DB failure requires a new challenge, never replay of successful verification. |
| Browser isolation | `AuthSessionProvider.tsx`, root layout, auth hook, AppShell, LogoutButton, API client, `useAccountActions.ts` | Auth state lives outside SWR. A non-authenticating per-session cache key plus user ID/role keys a fresh private cache and component tree. Logout/identity change/401 expiry discards auth, account state and toasts. Cross-tab notifications contain no identity/credentials. Late replies stay in a detached cache. Mutations invalidate the current provider. |
| Internal UI | AccountForm, MassDeployControl, DiagnosticsPanel | Hidden unless the role is explicitly admin. Backend remains the security boundary. |
| Documentation | root/service/dashboard READMEs, `service/.env.example`, Settings copy | New configuration/provisioning and exactly-one-worker/one-replica limitation. |

`/auth/me` adds `user_id` and `session_key`; this public random cache key is
not a session cookie or bearer credential. Members see their own active
website session count; admins retain the process-wide count. All authenticated
writes, including logout, require matching session CSRF cookie and header.

Resend accepts the original `challenge_id` with the email; deletion is
`DELETE /accounts/link/{challenge_id}`. Without a challenge ID, email lookup
is scoped to the current user. Two users can independently request the same
game email, but cannot use each other's challenges. Game-identity deduplication
is intentionally not solved here. Challenges do not survive a worker restart;
busy entries are not TTL-pruned mid-call. The existing Lilith client uses
bounded transport timeouts.

## Verification

Synthetic fixtures only: no live game actions, verification emails, production
DB writes, deployment or merge. Tests use fake sockets, mocked Lilith and the
in-memory repository. No production environment values were used.

- Targeted tenant/link suite: **95 passed, 1 DB-dependent test skipped**.
  Includes two members + admin, 33 account route variants, anonymous production,
  invalid roles, internal-route denial, challenge owner checks, concurrent API
  verification, bootstrap isolation, safe errors and persistence-failure replay.
- Full backend run: **333 passed, 15 DB-dependent skipped**, one legacy health
  expectation failed (`auth_required=False`). Updated that expectation to the
  production contract; affected health module rerun: **4 passed**. Thus all
  **334 runnable backend tests** passed across the full run and focused rerun.
- Full frontend run: **77 passed**, five legacy manual-import tests needed an
  explicit admin fixture. After that fixture update, affected module rerun:
  **5 passed**. All **82 frontend tests** passed across the full run and rerun.
- New frontend regressions cover cache clearing, identity/session rotation,
  cross-tab changes, late auth/SWR responses, stale-session 401 handling and
  internal-tool visibility. Targeted frontend tests passed before the full run.
- `npx next typegen` → `npx tsc --noEmit` → `npm run lint`: **passed**.
- `git diff --check`: passed.
- Non-blocking toolchain warnings: Starlette/httpx deprecation, Vite config
  loader warning, Node timer warning in provider tests, npm proxy-env warning.
- No Postgres migration/integration or live upstream validation was performed.
  Full suites were run once, followed only by affected-test fixture reruns.

Run commands from `service/` with the project's Python environment and from
`dashboard/` with installed npm dependencies. Never point `TEST_DATABASE_URL`
at production: existing DB tests recreate the schema. Generate Next route
types before standalone TypeScript checking. Follow `dashboard/AGENTS.md` and
installed `node_modules/next/dist/docs` guidance.

## Operational requirements and remaining gates

Production: `APP_ENV=production`, `AUTH_MODE=session`,
`DASHBOARD_COOKIE_SECURE=true`. Provision users with explicit member/admin
roles; a preexisting password user with NULL/invalid role cannot log in.
For local access only: `APP_ENV=development` (tests: `test`), `AUTH_MODE=local`,
`DEV_USER_EMAIL`, optional `DEV_USER_ROLE` (defaults member), HTTP cookies
allowed only there. Bind local bypass instances to loopback. `DEV_USER_EMAIL`
alone never bypasses session mode.

Exactly **one backend worker and one replica**. Website sessions, linking
challenges, AccountManager and the mass-deploy lock are all process-local.
Password/role changes do not revoke existing valid sessions; restart the
single worker when revocation is needed until Phase 3 implements it. No
claim of public-launch readiness.

Still deferred: durable/revocable sessions, rate limits/abuse controls,
identity uniqueness/relink, account-status enforcement, trusted deployment
configuration, diagnostic retention/redaction hardening, command correctness,
and deployment hardening. Operator bootstrap credentials must be maintained;
expired upstream sessions can still make linking unavailable. Account creation
after upstream success is not a durable transaction with Lilith.

Phase 4 defects remain unchanged:
- Gather replies leave `farm_vehicles` stale, permitting reuse of a truck.
- Collection captures reply baselines after sending, losing fast replies.
- Safe command correlation/serialization, durable jobs and automation opt-in
  remain later work. Mass-deploy/cancel stay admin-only pending owner-bound jobs.

## Phase 3 continuation prompt

Continue Warpath HUB PHASE 3 ONLY: customer identity and reliable linking.
Repository: MalexHUB/warpath-platform. Read docs/PHASE2_HANDOFF.md and the Phase 2
PR diff on codex/phase-2-auth-tenant-isolation; compare current HEAD with that
PR head. Do not re-audit the whole repository. Preserve Next.js, FastAPI,
PostgreSQL and AccountManager → AccountSession → WarpathConnection.

Implement PostgreSQL-backed revocable website sessions (separate from game
sessions), explicit invite-based pilot provisioning/recovery, canonical game
identity uniqueness and safe owner-bound relink, trusted linking metadata,
auth/link throttles and per-user limits. Define migration/backfill and safe
restart/re-auth behavior before changing persistence. Existing NULL/invalid
roles must not gain privileges. Keep owner-bound challenges, isolated operator
bootstrap credentials, CSRF, private session caches and admin-only internal/
mass-deploy/cancel boundaries. Account-status enforcement must be explicit.

Use synthetic fixtures and disposable test databases only. No live game
commands, verification emails, production DB writes, deployment or merge.
No redesign, motion, marketing, billing/public signup, Redis/worker splitting
or protocol rewrite. Leave farming/collection fixes to Phase 4. Follow AGENTS.md
and installed Next docs; no sub-agents. Work on an isolated branch preserving
unrelated work. Run targeted tests, then relevant suites once, with Next typegen
before tsc. Produce a reviewable PR and update this handoff with exact results,
migration constraints, remaining launch gates and the next phase.
