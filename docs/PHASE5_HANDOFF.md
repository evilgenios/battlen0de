# Warpath HUB — Phase 5 handoff

Scope: command-confirmation evidence and pilot operational readiness only.
Branch: `codex/phase-5-pilot-operations`, stacked on unmerged Phase 4 PR #3
(`codex/phase-4-farm-collection-correctness`). Baseline:
`c45d1bfdac98c0dfe5591a1a514d27c145184c98`.

Review PR: https://github.com/MalexHUB/warpath-platform/pull/4 (draft).
Application commit: `ffbcebe06ceb9830f5eaba7c35e91c81a8ae52ec`.
The subsequent handoff update is documentation only; use the PR head as
the next baseline.

Read the Phase 4 handoff, Phase 3 migration contract and Phase 4 PR diff first.
All 12 Phase 4 changed files matched the local baseline byte-for-byte. Local
snapshot commit IDs differ from GitHub IDs; publishing preserves the remote
base tree and uses the real GitHub parent. Main remained
`c1061c68c232bbc61633691822cbfd7c3fafede1`, five commits behind Phase 4 with no
intervening changes. No unrelated edits or full repository re-audit.

The latest native PostgreSQL CI for the exact Phase 4 head passed before
implementation: https://github.com/MalexHUB/warpath-platform/actions/runs/36328889767.
No baseline security/migration failure required repair.

## Evidence decision

**UNVERIFIED; gate retained.** No tracked captures were present. Five existing
local capture files contained start/stop markers only, with zero packets.
Neither synthetic fixtures nor protobuf field presence establish Lilith's
`msg_seq_id` echo or vehicle-list ordering. Existing debug recording is
server-to-client only and can include raw bytes on decode failure; it is not
a source of automatically sanitized request/reply evidence.

`COMMAND_CONFIRMATION_EVIDENCE.md` records inspected sources, missing facts and
requirements for a future authorized sanitized evidence review. No live game request,
email, capture, production DB access, deployment or merge was performed.
No fallback correlation or reservation-release condition was weakened.

## Behavior and files

| Files | Result |
|---|---|
| `service/app/core/warpath/reply_actions.py` | Add per-tracker observation ID and per-request operation ID/times/wait reason, plus a 50-entry completed history. Project allowlisted operational state under the existing condition lock. Keep all Phase 4 send/match/reserve/release rules. Busy messages direct users to reconciliation rather than reconnect-to-retry. |
| `service/app/api/actions.py`, `service/app/schemas/actions.py` | Add `GET /accounts/{id}/command-status`, protected by the existing authentication/owner/admin dependency. `Cache-Control: no-store`; no socket sends, command-state writes, retries or force-clear behavior. Reads remain available for restricted/disconnected accounts. |
| `dashboard/src/components/accounts/CommandStatusPanel.tsx`, `AccountDetailsClient.tsx` | Small read-only panel using existing components/styles: unresolved observations/reservations, late confirmation, recent completions, capacity and explicit history/evidence warnings. Polls GET only, including while disconnected. No redesign. |
| `dashboard/src/lib/api/actions.ts`, `types.ts`, `hooks/useAccountActions.ts` | Typed report client and private-provider cache revalidation. No global cache, identity storage or session-provider changes. |
| `service/tests/test_command_status.py`, `test_customer_identity.py`, `test_tenant_isolation.py` | Synthetic operational regressions and owner/admin, cross-owner, anonymous, invalid-role and durable-revocation coverage. |
| `dashboard/src/components/accounts/CommandStatusPanel.test.tsx` | Read-only updates, late confirmation, disconnected/reset history warnings, failed-report handling, capacity and late responses across website identity changes. |
| `docs/COMMAND_CONFIRMATION_EVIDENCE.md`, `docs/PILOT_OPERATIONS.md`, `service/README.md`, this handoff | Evidence register; read-only triage, reconciliation, containment, restart/crash and identity-incident procedures; exact verification and remaining gates. |

The architecture remains Next.js + FastAPI + PostgreSQL and
AccountManager → AccountSession → WarpathConnection. Phase 2/3 authentication,
revocation, explicit roles, ownership/status/limits, linking challenges, trusted
metadata, CSRF, private caches and all admin-only internal/mass-deploy/cancel
boundaries remain in force. No workers, Redis, protocol rewrite, signup/billing,
marketing or motion work. No sub-agents.

## Operational contract

- `history_scope=current_connection_only`, `history_complete=false`, and
  `upstream_evidence=unverified` are explicit response fields. These defaults do
  not imply that an empty account/connection has no older unresolved actions.
- Current requests expose operation kind, confirmation status/reason, safe
  building/truck/mine IDs, creation time, age and held reservation type.
  No wire sequence, reply payload, server error text, credentials or socket
  metadata is exported. Operation IDs are local observation identifiers,
  not upstream idempotency keys.
- A manual wait ending in timeout/cancellation/disconnect records its reason
  without releasing requests. Automatic collection has no HTTP waiter, so its
  still-pending observations become visibly uncertain after eight seconds.
  This is a presentation threshold; it neither expires nor retries the action.
- A matching late collect reply moves its row to recent confirmed history once.
  A matching late gather reply remains an active **confirmed but held** truck
  until the unchanged Phase 4 post-confirmation idle-list rule releases it.
  Historical HTTP responses/events are not rewritten.
- Recent history is capped at 50 completed search/collect/gather observations;
  `recent_dropped` reports eviction. Completed vehicle-list requests are omitted;
  outstanding ones remain visible and consume the unchanged 1,024-ticket budget.
  There is no cross-process journal or durable automatic-action audit log.
- Report reads never send a refresh or release a reservation. No manual
  mark-success, force-clear or replay endpoint was introduced. General Refresh,
  Connect and Reconnect still send game requests and must not be confused with
  Update report. Reconnect also enables the existing automatic collection loop.
- The browser report uses the existing private session SWR provider, hides stale
  rows on fetch error and does not retain old-identity replies. A connection reset
  replaces its observation ID and empties history; the UI explicitly says that
  this cannot establish older command outcomes. No history is called complete.
- Normal PostgreSQL website-session authentication still refreshes session idle
  activity; read-only here describes game/command state, not a bypass of session
  validation or its existing activity bookkeeping.

## Migration and restart constraints

**No schema, persistence, environment or dependency migration in Phase 5.**
Alembic stays at `0004_customer_identity`. Follow `PHASE3_MIGRATION.md` before
any future migration. NULL/invalid roles are never backfilled or elevated.
One worker/one replica remains mandatory. The existing global lifecycle lock
can delay report reads behind command waits; this is not an independent
emergency-control channel or a scaling change.

Website sessions remain PostgreSQL-backed and revocable across restart. Game
connections, reservations, observations and pending linking challenges remain
in memory. Stop the worker for a future authorized update; keep autostart false,
record/contain uncertain work first, and never infer cancellation or failure
from a lost tracker. A crash can erase the only automatic-action record.
Reconcile externally under separate authorization; do not replay on startup.

The runbook identifies existing supported containment routes: owner Disconnect,
admin account restriction, owner website-session revocation, admin user policy.
Website revocation alone does not stop game sessions. Those procedures were
verified against source/tests but were not exercised against production.

## Verification

All identities, game sockets, replies and database rows used for tests are
synthetic. Local database runs used a disposable in-memory PGlite 0.5.8 instance
with the existing scratch-only psycopg `ClientCursor` workaround. Production
code/driver is unchanged; local PGlite is not native contention evidence.
Native PostgreSQL 16.15 CI subsequently passed with the normal psycopg driver:
https://github.com/MalexHUB/warpath-platform/actions/runs/36330486507.
All 16 published changed files matched the tested local blobs byte-for-byte;
unrelated remote files were preserved. The final handoff update changes only
documentation.

| Check | Result |
|---|---|
| Exact Phase 4 baseline native PostgreSQL CI | Passed, run `36328889767` |
| Command report + Phase 4 replies + tenant isolation | 97 passed |
| PostgreSQL identity/migration + command report targeted checks | 41 passed in disposable PGlite |
| Frontend report/account/session-cache/action-hook targeted checks | 22 passed |
| Local full backend suite, once | 416 passed, 0 skipped, 24.21s |
| Local full frontend suite, once | 98 passed in 17 files |
| Next typegen → standalone TypeScript → ESLint | Passed |
| Phase 5 native PostgreSQL 16.15 CI, application commit `ffbcebe` | **416 backend passed**, 0 skipped, 23.49s; **98 frontend passed** in 17 files; Next typegen, TypeScript and lint passed |

The initial targeted backend run had 96 passes and one test-fixture failure:
it called a nonexistent `update_account_status` helper. Correcting the fixture
to the actual `update_account(..., status=...)` API produced 97/97; no application
fallback was added. Existing warnings concern Starlette/httpx, Vite config
loading, npm proxy settings and TimeoutNaN. React review guidance and installed
Next client-component documentation were followed for the small UI addition.

## Remaining gates

1. Actual authorized sequence-echo and vehicle-list ordering evidence, with
   reviewed sanitization and provenance. Never replace this with green synthetic
   tests or restore counter/FIFO confirmation.
2. Durable uncertain-action history/recovery and a reviewed pilot activation /
   automatic-action policy. The existing connected loop can collect every 240s;
   this phase does not make a game connection observation-only or disable that
   behavior. No claim of exactly-once execution or restart-safe replay.
3. Production-version Phase 3 migration/backup/restore rehearsal, duplicate-owner
   reconciliation, trusted ingress/peer identity and edge abuse controls.
4. Secrets/TLS/network/logging hardening; operator invitation/recovery verification,
   credential rotation, incident ownership, retention, monitoring and availability.
5. Durable owner-bound mass-deploy jobs and scaling; broader recall/scout/army
   reply correctness; multi-character/server identity semantics and live linking
   reliability. Admin boundaries remain until those scopes are addressed.

The new report/runbooks support investigation; **they do not make the product
public-launch-ready or authorize a pilot deployment**.

## Next-session prompt

Continue Warpath HUB PHASE 6 ONLY: pilot activation and operational safeguards.
Read `docs/PHASE5_HANDOFF.md`, `docs/PILOT_OPERATIONS.md`,
`docs/COMMAND_CONFIRMATION_EVIDENCE.md`, `docs/PHASE3_MIGRATION.md` and the Phase 5
PR diff on `codex/phase-5-pilot-operations`; compare current HEAD with its PR head.
Check native PostgreSQL CI first. Do not re-audit. Retain the unverified upstream
confirmation gate unless authorized, reviewed, sanitized real evidence is
supplied. Design explicit operator-controlled pilot/automatic-action activation
and restart behavior before implementation; preserve all Phase 2–5 security,
uncertainty, reservations and read-only report contracts. Keep owner/admin
boundaries and current architecture. Do not add force-success/force-clear or
silently retry uncertain actions. Use synthetic sockets and disposable DBs only;
no game calls/emails, production writes, deployment/merge, redesign, public
signup/billing, Redis or worker split. Use an isolated branch, no sub-agents,
follow AGENTS.md/installed Next docs, targeted then relevant suites once, Next
typegen before tsc. Produce a reviewable PR and exact handoff with remaining gates.
