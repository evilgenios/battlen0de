# Warpath HUB — Phase 6 handoff

Scope: pilot activation and operational safeguards only. Branch:
`codex/phase-6-pilot-activation`, stacked on unmerged Phase 5 PR #4,
`codex/phase-5-pilot-operations`. Baseline:
`d81b85a8abdc649c44d40c907082722a9be25fb7`.

Review PR: https://github.com/MalexHUB/warpath-platform/pull/5 (draft).
Application commit: `79271bfd26032be984ccacb3b73b4eb36932e4bb`
(local snapshot `7fe495a`). The later handoff commit changes documentation only;
use the PR head as the next baseline. All 27 published changed files matched
the tested local blobs; unrelated remote blobs were unchanged.

Read the four requested handoff/runbook/evidence/migration documents and Phase 5
PR diff first. All 16 Phase 5 changed files matched the local baseline blobs.
Main had no intervening work (seven commits behind Phase 5). Local snapshot
commit IDs/older file formatting differ from GitHub; publication uses the real
remote base tree and parent and preserves unrelated files. No re-audit or
sub-agents. No frontend changes; dashboard AGENTS.md was read, and no Next API
or installed-documentation-dependent frontend implementation was undertaken.

The exact Phase 5 head passed **native PostgreSQL 16.15 CI before implementation**:
https://github.com/MalexHUB/warpath-platform/actions/runs/36330862975.
416 backend passed (0 skipped, 30.61s), 98 frontend passed in 17 files, Next
typegen → TypeScript → lint passed. No baseline migration/security repair needed.

## Decision and implementation

`PHASE6_ACTIVATION.md` was committed **before application changes**; remote design
commit `b0aae6bb6f93821f70e55e1be202140bc0c3bcec` (local `380bdef`).
No new authorized sanitized real evidence was supplied. The gate remains
**unverified**. Synthetic replies and admin acknowledgement cannot open it.

- Off by default. Admin-only observation grants last 1–60 minutes (default 15),
  bind one account and issuing admin to this process, and send no game traffic.
  A separate owner/admin Connect still checks status and owner/global capacity.
- Only explicit admins can POST `/accounts/{id}/pilot-activation`. Members can
  GET their own state and POST `/accounts/{id}/pilot-pause`. Normal durable auth,
  role/status checks, ownership, CSRF and no-store policy apply. No UI redesign
  or public activation/provisioning was added.
- `mode=automatic` returns 409. Manual game-changing commands and all automatic
  actions stay blocked even for admins. Mass-deploy execute is blocked; preview
  and cancellation remain admin-only. Diagnostics/manual import retain their
  existing admin boundary. Existing owner-bound linking/security is unchanged.
- The default AccountManager installs the policy on each managed connection.
  HTTP checks reject unavailable commands before dispatch. Socket checks allow
  exactly one known observation request; unknown/mixed/raw sends are denied
  before sequence registration/write. Allowed shapes: login, heartbeat, vehicle
  list, power, skin inventory, group list, profile. Refresh omits map-view traffic.
  Legacy standalone protocol classes are not a supported pilot entrypoint.
- The 240-second collector and Conquest Guard do not attempt actions. Managed
  connection loss disables automatic reconnect and retains the current tracker.
  Login failures still become restricted. No protocol correlation is loosened.
- Expiry uses monotonic time. Pause/revoke serialize with admitted writes, then
  stop the game session. Already-started writes may finish; none are represented
  as undone. Status/user-policy changes revoke even unconnected grants. Shutdown
  revokes all grants. No environment/test-auth setting enables real actions.
- Activation requires a fully stopped thread and refuses unresolved active
  collect/search/gather observations. It cannot clear reservations or mark an
  action successful. Audit persistence failure leaves activation off; failed
  pause-event persistence does not undo containment.
- GET command-status retains the Phase 5 schema, allowlist, no-store headers,
  unknown/incomplete history and no-send/no-reset behavior. No frontend/private
  cache changes. Website authentication still performs its existing idle touch.

## Files changed

| Files/systems | Purpose |
|---|---|
| `service/app/core/pilot_activation.py`, `service/app/api/pilot.py` | Default-off policy, expiring observation grants, packet allowlist, authenticated operator API and typed request/report schemas. |
| `service/app/core/account_manager.py`, `account_session.py`, `warpath/connection.py` | Install/check policy, block automatic actions/reconnect, serialize revocation with transmission, retain closed observations. |
| `service/app/main.py`, `deps.py` | Reject autostart before DB/game I/O, register API, enforce mutation policy after auth/owner/status checks, return clear 409 denials. |
| `service/app/api/accounts.py`, `auth.py`, `sessions.py`, `mass_deploy.py` | Invalidate grants on account/user policy changes, preserve 409 pilot errors, retain admin-only boundaries and block deploy execution. |
| `service/tests/test_pilot_activation.py`, `test_customer_identity.py` | New production-gate regressions with synthetic sockets, two members/admin and disposable PostgreSQL, including real lifespan restart wiring. |
| `service/tests/fakes.py`, `conftest.py`, manager/lifecycle/API test imports | Explicit synthetic policy injection for existing engine tests below the new gate; production default remains fail closed, with no environment bypass. |
| `service/.env.example`, `service/README.md`, `docs/PILOT_OPERATIONS.md`, `COMMAND_CONFIRMATION_EVIDENCE.md`, `PHASE6_ACTIVATION.md`, this file | Configuration, exact operator request shapes, containment/restart/incident constraints and evidence gate. |

## Migration, restart and operational limits

**No database/schema/dependency migration.** Alembic remains
`0004_customer_identity`. Follow `PHASE3_MIGRATION.md` for any later upgrade:
stopped single worker, verified backup/restore, duplicate-owner reconciliation,
no NULL/invalid-role elevation. One worker/one replica only; no mixed versions.

`AUTOSTART_ACTIVE_ACCOUNTS` must be false/unset (`0`/`no` also accepted).
True/unknown values now fail startup before DB/game access. Existing persisted
active accounts are registered, never connected. There is no activation
backfill. Valid PostgreSQL website sessions survive restart; game grants,
pending linking challenges, reservations and history do not. A new process
needs fresh operator review and grants; never replay lost commands or restart
to remove a reservation. Do not roll back to old code to bypass the gate.

No activation UI is added. The runbook documents the authenticated same-origin
API/CSRF workflow for a separately authorized operator. Neither these examples
nor an observation grant authorize a live game call in this implementation task.
Website logout/revocation still does not stop games; grants issued for other
accounts are not retroactively revoked by revoking the issuing admin's website
session. Use explicit pause, account restriction or user policy containment.

Activation state may become off before a live socket closes on its next
heartbeat; no subsequent send is admitted. In-flight socket writes and the
shared lifecycle lock can delay pause/report access. These controls are not an
independent emergency channel. An audit event is intent/history, not current
grant state or proof of upstream completion. A crash can still erase the only
uncertain-action record and its in-memory activation interlock. Preserve an
external incident record and reconcile under separate authorization.

## Verification

All sockets, users, replies and rows were synthetic. No game calls, emails,
production DB writes, deployment or merge. Local DB runs used disposable
in-memory PGlite 0.5.8 and the existing scratch-only psycopg ClientCursor shim;
it is not native PostgreSQL contention evidence. Production driver is unchanged. Native PostgreSQL 16.15 CI subsequently passed
with the normal psycopg driver at application commit `79271bfd26032be984ccacb3b73b4eb36932e4bb`:
https://github.com/MalexHUB/warpath-platform/actions/runs/36332200142.

| Check | Result |
|---|---|
| Exact Phase 5 native PostgreSQL 16.15 CI | Passed, run `36330862975` |
| Pilot gate + reply correctness + command report + tenant isolation | 127 passed, 4.70s |
| Disposable PostgreSQL identity/migration + pilot gate | 69 passed, 10.08s |
| Local full backend suite, once | **450 passed, 0 skipped**, 26.14s |
| Phase 6 native PostgreSQL 16.15 CI | **450 backend passed, 0 skipped**, 34.49s; run `36332200142` |
| Frontend, unchanged (native CI) | **98 passed in 17 files**; Next typegen → TypeScript → ESLint passed |
| Diff whitespace validation | Passed |

Initial targeted iterations corrected test-only socket scoping, mass-deploy
group_type, synthetic EOF behavior and the existing user-policy route's 204
response expectation. They also exposed a real PilotBlocked→503 mapping in
Reconnect; it now remains 409. An intermediate test command ran before the
intended edits because of a wrong working directory and repeated the original
failures. The final targeted and full results above are from corrected files.
Only the existing Starlette/httpx deprecation warning remains locally. CI also
reports existing npm proxy/deprecated-package, Vite config and TimeoutNaN
warnings; no test/type/lint failure. The final handoff/README update is
documentation only; CI results above identify the exact tested application commit.

## Remaining gates and next phase

1. Reviewed, authorized, sanitized real upstream sequence/entity/vehicle-list
   ordering evidence. All automatic/manual game-changing actions remain closed.
2. Durable owner-bound command uncertainty/history and restart recovery. Current
   reservations are process-local; no exactly-once, replay, force-clear or
   complete-history claim. Broader recall/scout/army correctness is unresolved.
3. Production-version migration/backup/restore rehearsal, duplicate-owner
   reconciliation, trusted ingress/peer identity, abuse controls and deployment
   hardening (secrets, TLS, network, logs, monitoring, retention, availability).
4. Operator invite/recovery/rotation and incident rehearsal; a separately
   authorized, constrained pilot acceptance session. Linking reliability and
   multi-character/server identity semantics still need evidence.
5. Durable owner-bound mass-deploy jobs and scaling remain deferred. No Redis,
   worker split, public signup, billing, marketing, motion or redesign.

Planning estimate: **2–3 more focused phases after Phase 6 for a controlled
pilot**, depending on evidence: durable recovery/evidence review, operational
hardening/rehearsal, then authorized pilot acceptance. A polished commercial
product/redesign is additional work; this is not a launch-date guarantee.
The product is **not public-launch-ready** and nothing has been deployed.

## Next-session prompt

Continue Warpath HUB PHASE 7 ONLY: durable command uncertainty and restart
recovery. Read docs/PHASE6_HANDOFF.md, docs/PHASE6_ACTIVATION.md,
docs/PILOT_OPERATIONS.md, docs/COMMAND_CONFIRMATION_EVIDENCE.md and
docs/PHASE3_MIGRATION.md; inspect the Phase 6 PR diff on
codex/phase-6-pilot-activation and compare current HEAD with its PR head.
Check native PostgreSQL CI first. No re-audit. Review authorized sanitized real
evidence only if supplied; otherwise retain the unverified gate and all Phase 6
default-off/observation-only constraints. Define owner-bound durable command
history, pre-send persistence/failure semantics, migration/backfill and restart
behavior before implementation. Preserve Phase 2–6 auth, revocation, explicit
roles/status/limits, owner challenges, trusted metadata, CSRF/private caches,
reservations and read-only reports. No force-success/force-clear or automatic
replay of uncertain commands. Preserve Next.js, FastAPI, PostgreSQL and
AccountManager → AccountSession → WarpathConnection. Synthetic sockets and
disposable databases only; no game calls/emails, production writes, deployment,
merge, redesign, signup/billing, Redis, worker split or protocol rewrite. Use
an isolated branch, no sub-agents, follow AGENTS.md/installed Next docs, run
targeted then relevant suites once (Next typegen before tsc if needed), and
produce a reviewable PR plus exact migration/test/remaining-gate handoff.
