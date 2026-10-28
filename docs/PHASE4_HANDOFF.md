# Warpath HUB — Phase 4 handoff

Scope: farming/collection reply correctness only. Branch:
`codex/phase-4-farm-collection-correctness`, stacked on unmerged Phase 3 PR #2
(`codex/phase-3-customer-identity`). Baseline PR head:
`c7f33485cb8c5ad5983e0cf7d58724ff3737fb68`.

Review PR: https://github.com/MalexHUB/warpath-platform/pull/3 (draft).
Application commit: `acfa25e2e49a097e5a6b7b05286885a5520775a6`.
The subsequent handoff update changes documentation only; use the PR head
as the next baseline.

The Phase 3 handoff, migration contract and relevant PR changes were read
before protocol work. Current main remained
`c1061c68c232bbc61633691822cbfd7c3fafede1`, three commits behind the Phase 3
head, with no intervening main changes. The local working copy matched the
Phase 3 application files and had no unrelated edits. No full re-audit.
Phase 3's latest native PostgreSQL 16 CI was checked first and passed:
https://github.com/MalexHUB/warpath-platform/actions/runs/36311372033.
No failing Phase 3 security or migration test needed repair.

## Behavior and file map

| Files | Change |
|---|---|
| `service/app/core/warpath/reply_actions.py` | Per-connection correlation tickets; atomic truck/building reservations before send; condition-based waiting; late-reply handling; conservative reconciliation. |
| `service/app/core/warpath/connection.py` | Registers the allocated request sequence before `sendall`; routes real protobuf reply parsing into tickets; merges present fields of the matching gather vehicle into `farm_vehicles`; protects the cache from stale list replies. |
| `service/app/api/actions.py`, `service/app/schemas/actions.py` | Farm/collect return explicit result status. Collection counts only its own unique confirmed building replies. Existing auth/ownership/status dependencies retained. |
| `dashboard/src/lib/api/types.ts`, `dashboard/src/lib/hooks/useAccountActions.ts` | Partial/uncertain outcomes are informational, not success/empty claims; vehicle/activity/summary/production caches revalidate through the existing private SWR provider. No redesign. |
| `service/tests/test_reply_actions.py`, `service/tests/test_api_actions.py`, `service/tests/fakes.py` | Deterministic synthetic protobuf/socket regressions, including synchronous reply delivery inside `sendall`, replacing sleep-based farm/collection fixtures. |
| `dashboard/src/lib/hooks/useAccountActions.test.tsx` | Six outcome-display/cache tests. |
| `service/README.md`, this document | API result semantics, migration/restart constraints, verification evidence and continuation. |

Architecture remains Next.js + FastAPI + PostgreSQL and
AccountManager → AccountSession → WarpathConnection. No changes to Phase 2/3
authentication, revocation, explicit roles, ownership, status, limits, linking
challenges, trusted metadata, CSRF, session providers or admin boundaries.
Manual import, diagnostics, mass-deploy and cancellation stay admin-only.

## Confirmed versus uncertain

- **Collect confirmed:** every requested building supplied one matching reply.
  Duplicate, wrong-building, wrong-sequence and stale replies cannot contribute
  to its count. All tickets are installed before their respective socket sends;
  building reservations for the entire batch exist before the first send.
  Fast replies remain attached to their tickets instead of a single overwritten
  `last_*` payload. One eight-second batch wait replaces repeated baselines.
- **Collect partial:** some building replies are confirmed; others are rejected
  or unresolved. `unconfirmed_building_ids` identifies them. **Uncertain** means
  there is no confirmed result and at least one unresolved send. **Rejected**
  means all requests were explicitly rejected or failed before sending.
  `detail` is the wait completion reason, not another success indicator.
  `items_gained` retains its wire meaning: number of reward entries, not units.
  An uncertain zero is not evidence that buildings were empty.
- **Farm confirmed:** the request sequence, requested truck and mine match,
  state is traveling/gathering (2/3/9), and the reply does not require additional
  verification. The matching vehicle's present position/timing/state fields
  update the cache; absent fields do not erase existing telemetry.
  `dispatched=true` is used only for this result.
- **Farm uncertain:** search or dispatch confirmation is missing, including
  timeout, connection loss, cancelled wait or an ambiguous partial socket write.
  A sent command may still execute. An uncertain dispatch keeps its truck
  reserved even if the previous cache row says idle. A search timeout does not
  send a truck. `not_dispatched` describes a known lack of target/idle truck or
  cancellation before dispatch; `rejected` describes a known rejection.
- Concurrent farm orchestration is refused. Direct concurrent gather calls
  reserve each idle truck once. Automatic collection uses the same reservation
  path as manual collection and does not block the receive loop. Conflicting
  collection requests return 409; neither path silently retries unresolved
  building actions. Other unreserved trucks may still be selected.
- Matching late replies can resolve pending tickets after an HTTP response has
  returned. That original response/event is historical and is not rewritten.
  No durable action-status endpoint or browser cancellation endpoint is added.
  A cancelled wait does not cancel a sent game command or free its reservation.

## Correlation contract and limitations

Confirmation requires `down.msg_seq_id` to echo the allocated request sequence
and, where supplied, the expected building/vehicle/mine identity. Protobuf has
the sequence field, but **this repository does not establish its live echo
semantics for these actions**. Synthetic fixtures explicitly model that
contract. No live game command or packet capture was performed to verify it.
Missing/non-echoed sequences are deliberately uncertain; no FIFO, counter or
"first reply wins" fallback can manufacture confirmation. Until authorized
protocol evidence establishes this behavior, customer farming/collection is
**still gated**, and actions may remain reserved on real upstream replies.

A confirmed truck reservation is released only by a correlated vehicle-list
request initiated after its dispatch confirmation that explicitly reports it
idle with mine ID zero. Older/out-of-order lists, duplicate gather replies,
missing identity fields and unsolicited lists cannot free that reservation.
An uncertain truck is not freed by an idle list: it may precede a delayed
upstream dispatch. Explicit correlated rejection can release a pending truck.
Initial uncorrelated lists may populate otherwise unreserved observation data;
after a correlated snapshot, unmatched lists cannot regress it.

Tracking is process-local and capped at 1,024 outstanding/retained request
tickets per connection. Hitting the cap refuses new tracked sends. Pending
vehicle-list requests without correlatable replies consume this budget too.
No TTL silently releases ambiguous commands. The pilot favors correctness
over availability; an unresolved action can require manual reconciliation.

## Migration, restart and recovery constraints

**No schema, persistence or environment migration in Phase 4.** Alembic stays
at Phase 3 revision `0004_customer_identity`. Follow `PHASE3_MIGRATION.md` for
any environment that has not already applied that migration. Roles are never
backfilled or elevated. No production DB was accessed or changed.

Exactly **one worker and one replica** remain mandatory. The Phase 3 lifecycle
lock still spans account requests and their reply waits; throughput remains
limited. Do not run mixed application versions or a rolling multi-worker
upgrade. Stop the sole worker for a future authorized code update.

Closing a game connection wakes its waiters as disconnected without claiming
failure or success upstream. Reset/reconnect creates a fresh tracker and clears
vehicle observations; fresh server observations are needed before assigning a
truck. Restart does not undo commands already accepted by the game. Never use
reconnect as an automatic retry of uncertain actions: reconcile actual game
state before any manual retry. This is not durable exactly-once execution.
Valid PostgreSQL website sessions continue to survive restart, subject to the
unchanged revocation/expiry checks. Game sessions and linking challenges retain
the Phase 3 restart behavior; no automatic action replay was introduced.

## Validation results

All fixtures, identities, credentials, sockets and database rows are synthetic.
Local database validation used disposable in-memory PGlite 0.5.8 with the same
scratch-only psycopg `ClientCursor` workaround documented in Phase 3. This is
not native PostgreSQL concurrency evidence; production code uses its unchanged
driver. Native PostgreSQL 16.15 CI subsequently passed with the normal
psycopg driver, including Phase 3 security/concurrency/migration tests. Run:
https://github.com/MalexHUB/warpath-platform/actions/runs/36328670037.
All 12 published changed files matched the local tested blobs; unrelated
remote files were preserved. The final handoff commit is documentation only.

| Check | Result |
|---|---|
| Phase 3 baseline native PostgreSQL 16 CI | Passed, run `36311372033`, exact baseline head above |
| Initial targeted reply/action tests | 35 passed |
| Expanded reply/action/activity tests | 54 passed after correcting a vehicle-list parser variable introduced during development |
| Frontend outcome tests | 6 passed |
| Local backend full suite, once | 405 passed, 0 skipped, 22.75s |
| Final targeted reply/action/activity regression after small correlation tightening | 54 passed, 1.65s |
| Frontend full suite, once | 92 passed in 16 files |
| Next typegen → standalone TypeScript → ESLint | Passed |
| Phase 4 native PostgreSQL 16 CI, application commit `acfa25e` | **405 backend passed**, 0 skipped, 30.90s; **92 frontend passed** in 16 files; Next typegen, TypeScript and lint passed |

A development targeted run had five failures (one introduced list-parser
variable error and its downstream fixtures, plus a timing-sensitive legacy
recall fixture); correcting the parser produced 54/54 passing. The full suite
then passed. Existing tool warnings concern Starlette/httpx, Vite config
loading, npm proxy configuration and TimeoutNaN; no frontend check failed.

Coverage includes fast/delayed/duplicate/out-of-order replies, wrong sequence
or identity, multiple wrappers/trucks, partial collection, late completion,
timeout, cancellation before/after send, disconnect/reset, partial-write
ambiguity, rejection, simultaneous attempts, and stale reconciliation lists.
No live game actions/emails, deployment, merge, production DB writes,
protocol rewrite, Redis, worker splitting or sub-agents were used.

## Remaining launch gates and next phase

1. Obtain authorized, sanitized existing protocol captures or an explicitly
   authorized later validation session to establish sequence echo semantics
   and idle-list ordering. If the game cannot supply reliable correlation,
   keep conservative uncertainty and design a separately reviewed recovery
   contract. Do not quietly relax matching or claim exactly-once execution.
2. Rehearse Phase 3 migrations/backups/restoration and duplicate-owner
   reconciliation against an authorized disposable production-version copy.
3. Trusted ingress/peer identity, edge abuse controls, throttle tuning,
   secrets/TLS/network/logging hardening and operational recovery/rotation,
   retention, monitoring and single-worker availability remain launch gates.
4. Durable owner-bound mass-deploy jobs, scalable workers and broader command
   correlation (recall/scout/army operations) are deferred. Their existing
   reply-counter behavior was not rewritten in this phase.
5. Multi-character/server identity semantics and live linking reliability
   retain the limitations in the Phase 3 handoff.

This is a reviewable correctness change, **not public-launch approval**.

## Exact next-session prompt

Continue Warpath HUB PHASE 5 ONLY: command confirmation evidence and pilot
operational readiness. Repository: MalexHUB/warpath-platform. Read
`docs/PHASE4_HANDOFF.md`, `docs/PHASE3_MIGRATION.md` and the Phase 4 PR diff on
`codex/phase-4-farm-collection-correctness`; compare current HEAD with its PR
head. Do not re-audit or redesign. Check native PostgreSQL CI first. Preserve
Phase 2/3 security and Phase 4 reservations/uncertainty semantics. First
inspect authorized existing sanitized captures for `msg_seq_id` echo and
vehicle-list ordering for search/gather/collect. Synthetic fixtures are not
upstream evidence. If captures are unavailable, explicitly retain this gate;
do not make game calls or weaken confirmation. Then implement only concrete
pilot operational safeguards/runbooks that can be verified with synthetic
fixtures and disposable databases, prioritizing uncertain-action visibility,
reconciliation and restart/incident procedures. No real game commands/emails,
production writes, deployment/merge, public signup/billing, Redis/worker split,
protocol rewrite or design work. Use an isolated branch, follow AGENTS.md and
installed Next docs, no sub-agents. Run targeted tests then relevant suites
once; Next typegen before tsc if needed. Produce a reviewable PR and exact
handoff, retaining all unresolved launch gates.
