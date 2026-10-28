# BattleN0de public launch checklist

This checklist is for the **invite-access public beta**. It does not authorize game-changing automation.

## 1. Release gate

- Merge only a commit whose GitHub Actions workflow is green.
- Confirm `npm audit --omit=dev --audit-level=high` and `pip-audit` pass.
- Confirm the dashboard production build uses Next.js 16.3.6 or newer.
- Do not merge the diverged Daily/Assist feature PRs into the launch release unless they are rebased, revalidated and their backend dependency is deployed.

## 2. Database and backup

- Take a fresh PostgreSQL backup before backend deployment.
- Verify the dump is readable before applying migrations.
- Run Alembic upgrade to the release head.
- Recheck duplicate canonical game identities and account ownership constraints.
- Keep the pre-deploy backup until the release has completed its smoke window.

## 3. Backend production configuration

Required:

```env
APP_ENV=production
AUTH_MODE=session
DASHBOARD_COOKIE_SECURE=true
AUTOSTART_ACTIVE_ACCOUNTS=false
OBSERVATION_ACCESS_MODE=customer
INTERNAL_PROXY_TOKEN=<same 32+ character random value used by Vercel>
WARPATH_ENCRYPTION_KEYS=<current key first, previous key retained during rotation>
```

Run one backend worker/replica. The live AccountManager, sockets and some observation state are process-local.

The Docker port must remain bound to `127.0.0.1:8000`; expose the service through the HTTPS reverse proxy only.

## 4. Vercel configuration

- `BACKEND_API_BASE_URL` points to the HTTPS backend origin.
- `INTERNAL_PROXY_TOKEN` exactly matches the backend value and is server-only.
- `NEXT_PUBLIC_SITE_URL` points to the canonical BattleN0de domain.
- Production deployment is built from the same release commit as this checklist.
- Preview deployments must not be treated as production.

## 5. Administrator security

- Enroll TOTP MFA for every administrator before accepting customer accounts.
- Verify an admin can recover access using the documented operator process.
- Revoke old browser sessions after the cutover.
- Perform a backed-up encryption-key rotation rehearsal and retain the previous key until verification completes.

## 6. Smoke test

From an invited non-admin member:

1. Activate/login over HTTPS.
2. Link an owned test account.
3. Confirm the account can connect in `customer_mode` without an admin pilot grant.
4. Confirm read-only telemetry loads.
5. Confirm disconnect/reconnect works.
6. Confirm another member cannot read the account.
7. Confirm Collect/Farm/Recall/Scout/Scan/Conquest Guard game-changing execution returns the unverified-evidence block.
8. Confirm direct FastAPI access without the internal proxy token returns 403.
9. Confirm `/docs`, `/redoc` and `/openapi.json` are unavailable in production.
10. Confirm rate-limit responses return 429 when intentionally exercised against a test identity.

## 7. Monitoring

At minimum monitor:

- public website availability
- backend `/health`
- database connectivity
- 5xx rate
- 401/403/429 spikes
- backend process/container restarts
- account authentication/restriction events
- disk usage and backup success

Do not log request bodies containing credentials, activation tokens, verification codes or cookies.

## 8. Launch scope

The public beta may advertise:

- secure account linking
- Individual and Alliance account views
- production, movement and account telemetry
- read-only live cloud connections
- account/session/event management
- Player Scout entitlement may be provisioned, but live locate/refresh execution stays safety-gated until that read-only request path is explicitly promoted into the public observation allowlist

The public beta must not advertise unverified game-changing commands as generally available. Daily Assist, Battle Report Analyzer, Army Preset Manager and Supply/Campaign Resupply remain coming-soon until their branches are reconciled and deployed.

## 9. Rollback

If the release fails:

1. Stop/contain affected game sessions.
2. Roll the backend image/code back to the last known-good release.
3. Restore the database only when a schema/data rollback actually requires it; do not restore merely to clear process-local command uncertainty.
4. Keep `AUTOSTART_ACTIVE_ACCOUNTS=false`.
5. Record any in-flight command result as unknown rather than inventing success/failure.
6. Re-run health/auth/tenant smoke tests before reopening access.
