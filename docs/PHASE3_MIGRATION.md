# Phase 3 persistence contract (defined before implementation)

Base: Phase 2 PR #1, b0a7da67c684e6783128e93d41e68d9689e4c064.
Main has no later changes and is one commit behind. Phase 3 is stacked on
codex/phase-2-auth-tenant-isolation; neither phase is merged or deployed.

1. Stop the single backend worker before migration; take/verify a backup in
   the deployment session. This implementation session uses synthetic data only.
2. Add durable website sessions (hashed random tokens, absolute/idle expiry,
   user credential version), one-use invite/recovery grants (hashed tokens),
   persistent throttle buckets, user status and explicit per-user limits.
   Existing roles/passwords are preserved; NULL/invalid roles stay unable to
   authenticate. No in-memory website sessions are backfilled: everyone signs
   in once after upgrade. Later restarts preserve valid database sessions.
3. Define canonical identity as warpath:lilith:<positive ASCII decimal app_uid
   without leading zeroes>. This is the upstream identity actually returned
   by the current Lilith flow, not an invented character/server identity.
   Platform, gateway, email and caller-supplied profile_uid cannot create
   aliases. One Lilith identity occupies one account row globally. Supporting
   multiple characters under one Lilith identity is deliberately not implied.
4. Backfill canonical identity using a stored generated column. Duplicate
   canonical identities abort migration without selecting a winner; operators
   must reconcile ownership offline. Malformed legacy IDs are quarantined as
   needs_reauth (disabled/restricted rows remain blocked). No automatic merge,
   deletion or ownership transfer. Preserve raw app_uid and encrypted secrets.
5. Relink explicitly names an account belonging to the current website user,
   including when the caller is admin. It requires fresh Lilith verification
   and an inactive game session. Existing valid identity must match; legacy
   malformed identity can be replaced once after proof, subject to uniqueness.
   Disabled/restricted accounts cannot be reactivated by relinking. Persist
   credentials atomically and preserve row ID/owner/history. No game action is
   needed to link or relink. Capture validated operator metadata at challenge
   creation, never accept gateway/client metadata from members.
6. New invitations are member-only and operator-issued; no public signup.
   Recovery preserves an already valid role and cannot activate disabled users
   or grant roles to legacy NULL/invalid-role users. Grants expire, consume
   atomically once, and password changes revoke all website sessions. Tokens
   are delivered manually by the operator; this phase sends no email.
7. Serialize per-user account/session limits in PostgreSQL. Serialize live
   connect/reconnect/relink/status transitions in the single worker; retain
   AccountManager → AccountSession → WarpathConnection. Disallowed persisted
   account status blocks starts/actions. Disconnect, reads and deletion remain
   available to the owner; administrative status changes stop live sessions.
8. Login/redemption/link throttles persist across restarts and fail closed if
   storage is unavailable. Use the actual network peer, never untrusted
   X-Forwarded-For; behind Next, peer limits are shared and complemented by
   identifier/user buckets. Trusted ingress identity remains a deployment gate.
9. Keep one worker/replica: game sessions, linking challenges and lifecycle
   serialization remain process-local. Pending challenges expire on restart;
   game connections restart only under the documented startup policy. No Redis,
   worker split or protocol changes. Farming/collection remain Phase 4 work.
10. Downgrade requires stopping the service and invalidates website sessions
    and outstanding grants; it does not undo quarantined account statuses or
    recover tokens. Never run old and new application versions concurrently.

## Implemented details and operational constraints

- Canonical SQL and Python normalize ASCII space only and accept positive
  ASCII decimal identifiers up to 64 digits. The current linking path also
  requires the upstream profile value to fit signed PostgreSQL BIGINT.
- Website capacity evicts the oldest live session on successful password
  login; account capacity rejects creation. Policy changes revoke all
  website sessions and stop all owned games. Recovery alone leaves games
  connected; website credentials and game credentials are separate.
- Account-scoped routes share a single-worker lifecycle lock through the
  response. This intentionally favors correctness for the pilot and can
  delay other account requests while an operation waits for a game reply.
  Mass deployment holds it per account; cancellation remains independent.
- Website sessions have 24-hour absolute / 2-hour idle expiry. Invites have
  48-hour expiry; recovery grants one hour. Successful recovery invalidates
  every outstanding grant. Neither raw bearer nor grant token persists.
- Before future deployment, run the native PostgreSQL CI job, rehearse this
  migration against an authorized disposable copy, verify backups and
  document duplicate-owner reconciliation. Do not use migration/import
  scripts with `--force` as a customer relink mechanism.
- A stopped-worker downgrade drops website sessions/grants/throttles and
  per-user policy columns. Do not use downgrade to resume a public service:
  it removes these protections. Quarantined game rows remain quarantined.
