# Phase 6 activation contract — defined before implementation

Baseline: Phase 5 PR #4 head `d81b85a8abdc649c44d40c907082722a9be25fb7`.
The exact head's native PostgreSQL CI passed (run `36330862975`). All 16
Phase 5 changed files match the local snapshot. Older snapshot files have
formatting differences; publishing must preserve unrelated remote blobs.

## Decision

The upstream confirmation gate remains **unverified**. No real evidence was
supplied. An operator acknowledgement, configuration flag or synthetic test
cannot open it. Phase 6 permits only a time-bounded **observation pilot**;
manual game-changing commands and all automatic actions remain blocked.
This is implementation of safeguards, not authorization to use live accounts.

| State | Permitted behavior |
|---|---|
| Off (default) | Authenticated local reports and containment; no game connection or sends. |
| Observation grant | One account, explicit admin, maximum 60 minutes; owner may connect. Login, heartbeat and explicitly allowlisted snapshot requests only. |
| Automatic actions requested | Rejected with the unresolved evidence gate; no state change. There is no force/override setting. |
| Expired, paused, disconnected or restarted | No new sends; fresh admin review/grant needed before connecting again. No automatic reconnect or replay. |

Grants are process-local and tied to an account, issuing admin, UTC issue/expiry
times and process instance ID. Expiry enforcement uses monotonic time. Granting
does not connect, send, reset a tracker or modify account status. Activation
requires active persisted account and owner and a fully stopped session thread.
Existing owner/global capacity checks still run at connect. Members can inspect
their own activation and pause it, but only explicit admins can grant access.
No grant can change ownership, restore an invalid role or override restriction.

Pause revokes permission before stopping the session. Socket writes and policy
revocation serialize under a policy lock: an already-started write may complete,
but no subsequent write is admitted. It does not cancel an upstream command.
Read-only command reports remain unchanged, including restricted/off accounts.
Pause/expiry/close never release reservations or claim success. Regrant cannot
reconcile an uncertain action: preserve the old report and resolve externally
under separate authorization before any reconnect. History is still incomplete.

## Enforcement and restart

The service's AccountManager installs the policy on every managed connection.
Connection creation and sends check it, with a narrow protobuf allowlist and
raw-send denial as defense in depth. HTTP mutation checks reject unavailable
commands before work starts. The background collector and Conquest Guard do
not attempt actions while automation is blocked. Legacy standalone protocol
classes remain independently testable; they are not a supported pilot entrypoint.

There is no schema migration or persisted activation backfill. Website sessions
remain PostgreSQL-backed/revocable. A new process has no game grants, including
for previously active database rows. `AUTOSTART_ACTIVE_ACCOUNTS=true` is rejected
before database/game I/O; setting it false cannot activate accounts. One worker
and one replica are mandatory. A network close also revokes the account grant
and prevents supervisor retry, preserving the last tracker until a deliberate
new connection. Never roll back to an earlier build to bypass these controls.

The API is the operator interface for this phase; no redesign or new browser
state is needed. Runbook examples use the existing authenticated CSRF flow.
Activation/pause events are allowlisted metadata, not credentials or free text.
Failure to persist an activation audit event leaves the account off. This is
not a durable command journal, emergency independent control plane, deployment
approval, or resolution of the evidence/recovery/production hardening gates.

## Verification plan

Use synthetic sockets, two members and an admin, plus disposable PostgreSQL.
Test default deny, roles/ownership/CSRF/revocation/status, account isolation,
expiry/restart, grant without sends, blocked automatic/manual/raw/unknown
packets, revoke-versus-send ordering, no automatic reconnect, unchanged reports
and uncertainty/reservations. Existing protocol tests explicitly inject a
synthetic unrestricted policy where exercising the engine below this gate.
Run targeted checks, then relevant suites once; native PostgreSQL CI remains
required. Frontend code is unchanged unless a concrete defect requires it.
