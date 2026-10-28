# Pilot command, restart and incident procedures

These are procedures for a **future authorized operator session**, not commands
executed during implementation. Phase 6 supersedes the old activation behavior. Public launch remains blocked by the evidence register
and the Phase 3/4 gates. Preserve explicit roles, ownership, status enforcement,
revocable website sessions, trusted linking metadata and admin-only tools.

## Preconditions

- Exactly one backend worker and one replica; no mixed-version rolling update.
- `APP_ENV=production`, `AUTH_MODE=session`, secure website cookies, reviewed
  secrets and trusted ingress. Local auth is never a production fallback.
- `AUTOSTART_ACTIVE_ACCOUNTS=false`. True/unknown values now fail startup before
  database/game I/O. A fresh per-account admin grant is required before Connect.
  Connecting sends login/allowlisted snapshots; it is NOT a local report read.
  Phase 6 blocks the 240-second collector, Conquest Guard and game-changing
  manual actions. No grant can bypass the unverified upstream-evidence gate.
- Confirm the intended commit and its native PostgreSQL CI. Phases 5–6 add no
  schema migration; required existing head is `0004_customer_identity`.
  Follow `PHASE3_MIGRATION.md` for stopped-worker migration, duplicate-owner
  reconciliation and restoration rehearsal. Never migrate an unverified target.
- Have an explicitly provisioned admin and an out-of-band recovery process.
  NULL/invalid roles are not recoverable through privilege fallback. Invitations
  remain member-only; recovery preserves valid roles. Do not use raw SQL or
  credential import to bypass recovery/relink policy.

## Operator activation (Phase 6)

Use the existing authenticated website session and matching `dashboard_csrf`
cookie / `x-csrf-token` header for writes. Through Next, prefix the API paths
below with `/api/backend`; do not put cookies or tokens into URLs, shell history
or incident records. The browser has no new activation control in this phase.
These are request shapes for a future authorized session, not instructions to
make game calls during development.

| Request | Authorization and result |
|---|---|
| `GET /accounts/{id}/pilot-activation` | Owner/admin; local report only. Returns off/observe, reason, process instance, issuing admin, issue/expiry times, actions=false, evidence=unverified, restart_policy=off. |
| `POST /accounts/{id}/pilot-activation` with `{"mode":"observe","minutes":15}` | Admin only; account/owner must be active, game thread fully stopped, no unresolved collect/search/gather observations. Duration 1–60 minutes. Writes an audit event then grants permission; sends nothing. |
| Same POST with `{"mode":"automatic"}` | Always 409 while evidence is unverified. No acknowledgement/force field is supported. Existing observation grant remains unchanged. |
| `POST /accounts/{id}/pilot-pause` | Owner/admin; revoke before stopping, including restricted accounts. Preserve tracker/reservations; no upstream cancellation claim. |

Before authorizing observation, review the command report, account/owner status,
limits and any incident record from a prior crash/restart. Record that old
outcomes may be unknown. A grant alone does not register/connect an account;
the owner/admin must separately request Connect. All such future game access
needs separate authorization. A website user may not activate their own game
account without an admin grant.

Only login, heartbeat, vehicle-list, power, skin inventory, group-list and
profile queries pass the socket allowlist. General Refresh requests those
snapshots and omits map view in observation mode. Farm/search, collection,
recall, scout, map scan/locate, army changes, mass-deploy execution and enabling
Conquest Guard are unavailable (409), even for admins. Mass-deploy preview and
cancel stay admin-only. Diagnostics retain their existing admin boundary;
starting a capture may request allowlisted snapshots and is not a local report
read. GET command-status is unchanged and always sends nothing.

Expiry uses monotonic time; no new writes are admitted after expiry. The next
heartbeat/connection processing closes the socket, so a short interval can
show activation off while connection status still shows connected. Pause
serializes with admitted writes, then closes; an already-started write can
complete before pause returns. Both HTTP lifecycle waits and a blocked socket
write can delay containment. This is not an independent emergency channel.

Disconnect/peer failure revokes the grant and the supervisor does not retry.
Pause before requesting a new grant; activation refuses a live/still-stopping
thread. Unresolved collect/search/gather records prevent reactivation. There
is no force-clear workflow; do not restart to bypass this check. A crash loses
this in-memory interlock, so the external incident/reconciliation record is
still mandatory. Status/user-policy changes revoke grants even for accounts
that never connected. Shutdown revokes all grants; a new process starts off.

Grant/revocation permission is process-local. A successful grant audit event
is not proof that a grant is currently active (or that a game connected).
Audit-write failure leaves activation off; pause remains effective even if
its event write fails. Use GET to verify current policy after an error.
Website logout/revocation alone still does not pause game observation. An
issuer's later website-session revocation does not retroactively revoke grants
for other accounts; use pilot-pause or account restriction for containment.

## Read the command report first

The existing account page's **Command confirmation** panel polls only
`GET /accounts/{account_id}/command-status`. The Update report button makes the
same GET. These reads send no game requests and do not clear or reconcile any
reservation. Members can read their own accounts, including restricted or
already disconnected accounts; explicit admins retain operator access. Expired
or revoked website sessions must re-authenticate. Cross-owner members are denied.
The route has `Cache-Control: no-store` and the browser uses the existing
per-website-session SWR provider.

Record the affected account ID, UTC incident time, application commit,
`observation_id`, operation IDs, entity IDs, age/status/reason, reservation,
tracking capacity and the persisted account status. These are sensitive
owner-scoped operational records: store them only in an authorized incident
record. Never attach cookies, tokens, raw payloads or unreviewed debug downloads.

`observation_id` identifies one process-local connection tracker; it is not a
game session secret, proof of game completion, or an idempotency key. A new ID,
null ID or empty report cannot establish what happened in an older connection.
`history_complete` is always false. The report retains up to 50 completed
search/collect/gather observations; `recent_dropped` counts evictions. Completed
vehicle-list requests (including rejections) are not retained as completed history. Pending list
requests remain visible and consume the 1,024-ticket tracking budget.

| Observation | Interpretation and next step |
|---|---|
| Awaiting reply | Still waiting under the Phase 4 contract. Do not duplicate the request. |
| Uncertain with a building/truck reservation | Command may have executed. Hold retries; look for a matching late reply in this read-only report. |
| Search uncertain | No dispatch was initiated by that farm orchestration; the search slot remains occupied pending its reply. |
| Gather confirmed, truck held | A matching travel/gather reply was observed. The truck is intentionally unavailable until a later eligible idle list. |
| Recent confirmed collection | A matching building reply was observed, possibly after the original HTTP response. This does not rewrite that historical response/event. |
| Idle observed | An eligible post-confirmation list released that truck under Phase 4 rules. The report itself did not send the list. |
| Rejected/not sent | Explicit correlated rejection or known pre-send failure. Assess cause before any deliberate new attempt. |
| Report unavailable | Treat displayed state as unavailable, not as empty or resolved. The UI hides stale rows on error. |
| Tracking capacity reached | New tracked sends are refused. Do not restart merely to clear the budget; use containment and reconcile actual game state. |

Read-only reporting uses the existing lifecycle lock and can wait behind a
manual game action. It is not an independent emergency-control channel. Counts
are a current observation, not a durable transaction history. Polling never
turns an uncertain action into success based only on elapsed time.

## Uncertain command / stalled reservation

1. Stop submitting more attempts for the affected command/entity. Preserve the
   report and persisted action events while the tracker still exists. A browser
   refresh or logout does not cancel a game request.
2. If containment is needed, an authorized admin can set the account to
   `restricted` with `POST /accounts/{id}/status` and body
   `{"status":"restricted"}` using the normal authenticated CSRF flow. This
   persists the restriction and stops its live game session. Owners can use the
   existing Disconnect control, but that alone does not persist a policy block.
   Both revoke the Phase 6 observation grant and can wait behind an in-flight lifecycle lock. Neither undoes a command
   already accepted by the game.
3. Inspect late confirmation through GET while the same tracker exists. Do not
   click the general game **Refresh**, Reconnect, Farm or Collect controls under
   the assumption they are local reads. Refresh sends game requests.
4. If a **confirmed** gather awaits release, Phase 4 permits release only from a
   correlated list requested after confirmation, explicitly reporting idle with
   mine ID zero. An uncertain gather is not freed by an idle list. Additional
   game observations require separate authorization and valid account status;
   do not bypass a restriction to manufacture reconciliation.
5. If still unresolved, preserve the restriction and escalate to the operator
   for authorized external game-state verification and protocol-evidence review.
   No force-clear, mark-success, automatic retry, or reservation-delete API exists.
   Keep a manual reconciliation record if a restart becomes unavoidable.
6. Re-enable an account only through its admin status and fresh observation-grant workflows after
   recording what is known/unknown and authorizing the next action. A new
   connection starts with empty observations; it is not proof that old commands
   failed. Customer commands remain gated on upstream confirmation evidence.

## Planned restart or service interruption

1. Record commit/migration head and all affected reports/events before stopping.
   Coordinate a maintenance window and contain accounts that must not resume.
2. Verify autostart is false, keep one worker, and stop it cleanly. If migration
   or restore is required, stop first and follow the Phase 3 backup/duplicate
   procedure. Do not execute a downgrade as a service recovery shortcut.
3. A crash may erase the only in-memory report. Mark prior outcomes **unknown**;
   do not backfill successful/rejected states from an empty report or missing event.
4. After an authorized restart, verify website authentication, current
   role/status/revocation and owner isolation before issuing any observation grant.
   Valid PostgreSQL website sessions survive restart. Game sockets, pending
   linking challenges, activation grants, reservations and recent command observations do not.
5. Pending linking challenges require a fresh owner-bound request after restart;
   never reuse a lost challenge or verification code. No code is persisted/logged.
6. Confirm restricted accounts remain blocked and autostart did not connect any
   accounts. Verify new report observation IDs/history warnings. Do not replay
   actions from logs, browser toasts or memory. Recovery does not claim exactly-once
   processing or that the game stopped when this service stopped.

## Identity or credential incident

- An owner can revoke website sessions through Settings / `POST /auth/revoke-all`.
  This invalidates browser access; it does **not** stop game sessions.
- An authorized admin can disable a website user through
  `POST /auth/pilot/users/{user_id}/policy`. The request requires explicit
  `status`, `max_accounts`, `max_sessions`, `max_active_accounts`; preserve the
  reviewed limits rather than inventing new ones. The existing route revokes
  browser sessions and stops owned game sessions. Do not weaken roles/status
  to get a recovery token accepted.
- Restrict affected game accounts separately if credentials may be compromised.
  Website password recovery and game credential relinking are different flows.
  Relink remains owner-only, inactive-session-only, same canonical identity for
  valid existing identities, with trusted operator metadata and fresh proof.
- Rotate/revoke operator bootstrap or game credentials only via an explicitly
  authorized incident procedure. Do not import another customer's credentials,
  share an admin capture, log codes, or use manual import as a customer relink.

## Disposable rehearsal and release decision

Run the targeted command-status and tenant tests, PostgreSQL identity/migration
checks, then the relevant full suite. The CI workflow uses a disposable native
PostgreSQL 16 service and synthetic sockets. `TEST_DATABASE_URL` tests can
**drop tables**; never point them at production or a valuable development DB.
Use the documented CI workflow as the native rehearsal reference, not a
production connection string copied into a test command.

Release review must separately establish: authorized sequence/ordering evidence;
Phase 3 production-version restore/migration rehearsal; trusted ingress and
abuse controls; secrets/TLS/network/logging hardening; operational invitation/
recovery/rotation/retention; availability/monitoring; and an explicit pilot
scope. Unit tests and a green CI run do not satisfy those operational gates.
