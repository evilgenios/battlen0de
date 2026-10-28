# Warpath HUB — Phase 3 handoff

Scope: customer identity and reliable linking. Branch:
`codex/phase-3-customer-identity`, stacked on Phase 2 PR #1
(`codex/phase-2-auth-tenant-isolation`). The Phase 2 head was and remains
`b0a7da67c684e6783128e93d41e68d9689e4c064`; main is still
`c1061c68c232bbc61633691822cbfd7c3fafede1`, one commit behind it.
The Phase 2 handoff/diff and relevant paths were inspected; no full re-audit.
Phase 3 PR: https://github.com/MalexHUB/warpath-platform/pull/2.
Application commit: `232af5a415393b8e025510e6b86de7ffe404d146`.
Use the Phase 3 PR head, including this document, as the next baseline.

No deployment, merge, real game commands, verification emails, production
DB writes, redesign, animation, marketing, billing/public signup, Redis,
worker split, protocol rewrite or farming/collection changes were performed.
All credentials, identities, SQL rows and game sockets used in testing are
synthetic. No sub-agents were used.

## Behavior and implementation map

| Area | Entry points | Implemented contract |
|---|---|---|
| Persistence | `service/migrations/versions/0004_customer_identity.py`, `app/db/models.py`, `app/security/identity.py` | Website sessions, pilot grants, throttle counters, user policy/version; generated global unique Lilith identity. Duplicate backfill aborts; malformed IDs quarantine; roles unchanged. |
| Website sessions | `app/db/identity_store.py`, `api/auth.py`, `deps.py`, `main.py` | Random opaque bearer stored as digest; current role/status/version checks; idle/absolute expiry; restart survival; own-session inventory and revocation. No memory fallback. Oldest session evicted on successful login at cap. |
| Pilot provision/recover | `identity_store.py`, `schemas/auth.py`, `api/auth.py`, `/activate`, `IdentitySettings.tsx` | Admin-issued member-only invitations and role-preserving recovery; expiring hashed grants; atomic single redemption; all browser sessions revoked on password change; manual private delivery, no emails/signup. |
| Owner-bound linking | `api/link.py`, `core/link_challenge_store.py`, `schemas/link.py`, `db/repository.py` | Original owner challenge claims preserved; trusted operator metadata captured before email; no customer bootstrap; globally unique canonical identity; explicit inactive owner-only relink preserves account ID/history and rejects identity substitution or restriction bypass. |
| Policy and capacity | `deps.py`, `api/accounts.py`, `api/sessions.py`, `api/mass_deploy.py`, `main.py`, `repository.py` | Per-user linked/browser/active-game caps; SQL user-row locks; one-worker lifecycle lock. Non-active game accounts cannot act/start. Admin account/user policy stops games; user policy revokes browsers. Late auth-failure events cannot weaken blocked states. Mass-deploy/cancel remain admin-only. |
| Throttles | `identity_store.py`, `api/auth.py`, `api/link.py` | Persistent fixed windows before password hashing/Lilith calls; peer plus email/token/user buckets; foreign challenges rejected before upstream; pending challenge cap; periodic retention cleanup. |
| Browser isolation | Existing `AuthSessionProvider.tsx` plus `IdentitySettings.tsx`, `AppShell.tsx`, linking wizard/relink page | Existing identity/session-keyed SWR provider retained. Current/all-session revocation clears private state. Public activation uses no token URL or browser storage. Admin provisioning hidden from members. |
| Verification | `test_customer_identity.py`, `test_identity_migration.py`, existing security/lifecycle suites, frontend tests, `.github/workflows/identity-tests.yml` | Synthetic database/API regressions; upgrade/backfill/duplicate rollback/downgrade/schema parity; native PostgreSQL 16 CI configured. |

## Migration and restart constraints

The persistence design was written in `PHASE3_MIGRATION.md` before schema
implementation. Read that document and `service/README.md` before any future
migration. Stop the only worker, back up and verify restoration, reconcile
duplicate canonical identities offline, then upgrade. No automatic merge,
owner selection or role backfill. A NULL/invalid legacy role never becomes
member/admin through migration, invitation, recovery or policy changes.

Old process-memory browser sessions cannot migrate and require one fresh
login. Later restarts preserve valid PostgreSQL website sessions. Game
sessions remain separate: restarting interrupts them; pending email
challenges are lost. Default autostart is false. Exactly **one worker and
one replica** remain mandatory. No mixed-version rolling upgrade.

Canonical identity is the positive ASCII decimal **Lilith app_uid**, ignoring
leading zeroes and ASCII edge spaces, independent of email/platform/gateway.
It does not establish a character/server identity model. New linking results
must fit the existing BIGINT profile storage. Invalid legacy IDs are
`needs_reauth`, except existing disabled/restricted states remain blocked.
Relink can repair such an invalid identity after proof; valid identities must
match and global uniqueness applies to every owner.

The lifecycle lock serializes account requests through their response,
including waits for game replies. Pilot throughput is deliberately limited;
this is not a scalable worker architecture. Website revocation/recovery does
not stop games; explicit user-policy updates do. Raw SQL policy/password
writes outside these APIs/CLI are not an operational workflow. Operator
recovery/identity verification and duplicate reconciliation need runbooks.

## Validation results

Local database tests used disposable **PGlite 0.5.8 PostgreSQL-WASM**, not native
multi-backend PostgreSQL. Its TCP adapter's extended-query error recovery
failed after a uniqueness violation; a scratch-only pytest plugin selected
psycopg `ClientCursor` (simple protocol). No production driver or application
fallback was changed. The engine multiplexes connections, so local concurrent
API/transaction tests do **not** establish native row-lock contention behavior.
Native PostgreSQL 16 CI subsequently passed with the normal psycopg driver,
including concurrent grant consumption, identity claims and capacity checks.
Run: https://github.com/MalexHUB/warpath-platform/actions/runs/36311174178.
The later handoff commit changes documentation only.

| Check | Result |
|---|---|
| Migration upgrade, duplicate preflight rollback, quarantine, unchanged roles, downgrade, re-upgrade, Alembic schema parity | Passed in disposable PGlite |
| Targeted identity/migration/repository/auth/link/tenant suite | 134 passed |
| Additional policy, capacity, normalization and mass-deploy checks | 42 passed |
| Backend full suite, once | 374 passed; 3 outdated fixtures failed; 0 skipped |
| Follow-up identity checks including late-event policy preservation | 30 passed before an outdated synthetic-UID assertion stopped the combined run |
| Corrected lifecycle/connection fixture rerun | 16 passed; all 380 backend tests covered successfully across full run and targeted reruns |
| Frontend full suite, once | 86 passed in 15 files |
| Next route types → standalone TypeScript → ESLint | Passed |
| Native PostgreSQL 16 CI, application commit `232af5a` | **380 backend passed**, 0 skipped (29.46s); **86 frontend passed**; Next typegen, TypeScript and lint passed |

The three full-suite fixture failures were: a previously skipped database
lifecycle fixture did not explicitly enable local test auth; two connection
fixtures corrected metadata but did not explicitly reactivate the account
following `auth_failed`. Fixtures now exercise that required admin action.
A follow-up synthetic numeric UID expectation was corrected as well.
Published verification: all 44 changed files match tested local blobs; no
unrelated remote files changed or were deleted.

Known test-tool warnings concern Vite config loading, npm proxy config, and
an existing TimeoutNaN warning; no frontend check failed.

## Remaining public-launch gates

- Production-version migration rehearsal, backup restoration and explicit
  duplicate-owner reconciliation. Native PostgreSQL 16 concurrency regressions
  passed; this does not constitute a production capacity or availability test.
- Farming: gather replies leave `farm_vehicles` stale and allow reselecting a
  truck. Collection: reply baseline captured after send can lose fast replies.
- Trusted ingress/peer identity, edge abuse controls, throttle tuning,
  deployment secrets/TLS/network hardening and request/response logging policy.
  Behind Next, the direct-peer throttle is shared; X-Forwarded-For is ignored.
- Operational invitation/recovery verification, credential rotation/revocation,
  incident handling, retention/monitoring and single-worker availability.
- Game identity semantics beyond one Lilith identity: no unsupported claim of
  multi-character/server identity deduplication. No live-link reliability test
  was performed; upstream failures consume successful challenges safely and
  require fresh linking if subsequent persistence fails.
- Owner-bound durable mass-deploy jobs and scaling remain deferred. The
  existing protocol's farming/collection behavior is not customer-safe yet.

This change is **not public-launch approval**.

## Exact Phase 4 continuation prompt

Continue Warpath HUB PHASE 4 ONLY: farming/collection reply correctness.
Repository: MalexHUB/warpath-platform. Read docs/PHASE3_HANDOFF.md and
PHASE3_MIGRATION.md; inspect the Phase 3 PR diff on
codex/phase-3-customer-identity and compare current HEAD with that PR head.
Do not re-audit. Preserve Next.js, FastAPI, PostgreSQL and
AccountManager → AccountSession → WarpathConnection.
First check native PostgreSQL CI and resolve any failing Phase 3 security or
migration tests before protocol work. Then fix gather replies leaving
farm_vehicles stale/reselectable and collection capturing reply baselines
after sends/losing fast replies. Use deterministic synthetic replies to test
fast/delayed/duplicate/out-of-order responses, timeout/cancellation and
concurrent attempts. Define confirmed vs uncertain results; prevent duplicate
truck assignment without claiming unconfirmed actions succeeded. Preserve
Phase 2/3 auth, revocation, explicit roles, ownership/status/limits, challenges,
trusted metadata, CSRF/private caches, and admin-only internal/mass-deploy/
cancel boundaries. No live game commands/emails, production DB writes,
deployment/merge, redesign/motion/marketing, billing/signup, Redis/worker
split or protocol rewrite. Use an isolated branch, follow AGENTS.md and
installed Next docs, no sub-agents. Run targeted tests then relevant suites
once, Next typegen before tsc if frontend changes. Produce a reviewable PR
and exact test/migration/remaining-gate handoff; do not claim launch readiness.
