# BattleN0de Security Audit — 2026-09-28

## Scope

Static review of the production-facing Next.js dashboard and FastAPI service, including:

- website session authentication and cookies
- CSRF protection
- login / grant throttling
- account ownership and admin authorization
- Warpath credential storage and redaction
- account linking flow
- action / Conquest Guard / diagnostics authorization
- browser-to-backend proxying
- production HTTP headers and source maps
- Docker runtime privileges
- API documentation exposure
- dependency vulnerability scanning
- repository secret hygiene

This is a code/configuration audit, not a penetration test of the deployed host, firewall, PostgreSQL provider, Vercel account, DNS, or upstream Warpath/Lilith services.

## Executive summary

No unauthenticated account-control bypass or cross-tenant account access was found in the reviewed routes.

Strong existing controls include:

- production rejects local authentication mode
- secure, HttpOnly session cookie
- per-session server-validated CSRF token on mutations
- opaque session tokens stored as SHA-256 digests
- scrypt password hashing with per-password salts
- login email + peer throttling and grant throttling
- account-scoped routes centralized through `get_owned_account`
- admin-only diagnostics and mass-deploy routes
- encrypted Warpath app tokens/device IDs at rest
- API schemas omit saved app tokens/device IDs
- exception and protocol-secret redaction
- no browser CORS access to the FastAPI service
- server-side Next.js API proxy
- explicit fail-closed production auth configuration
- account-link challenges are owner-bound, attempt-limited and expiring

## Hardening applied in this audit

### Browser / frontend

- disabled the `X-Powered-By` header
- explicitly disabled production browser source maps
- added:
  - `X-Frame-Options: DENY`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - a restrictive `Permissions-Policy`
  - `Cross-Origin-Opener-Policy: same-origin`
  - `Cross-Origin-Resource-Policy: same-origin`
  - HSTS
  - CSP directives blocking framing, plugins, foreign base URLs and foreign form targets
- moved the preferred backend origin setting to server-only `BACKEND_API_BASE_URL`
- browser traffic continues to use same-origin `/api/backend/*`

### Backend

- production FastAPI Swagger, ReDoc and OpenAPI schema endpoints are disabled
- the Docker image now drops root and runs Uvicorn as an unprivileged user
- dependency vulnerability gates were added to CI with `pip-audit` and `npm audit`

## Security-center additions in this phase

The admin/customer split now adds:

- a dedicated site-admin control center for customer policies, linked Bases, sessions, access grants and audit history
- a separate `admin_audit_events` table rather than overloading customer account events
- administrator TOTP MFA with encrypted secret storage
- MFA-aware login and forced session revocation when MFA policy changes
- a Vercel/Next.js -> FastAPI shared-secret trust boundary via `INTERNAL_PROXY_TOKEN`
- Fernet keyring support with safe credential/MFA key rotation
- a dry-run-first secret rotation script
- customer-facing activity views that omit raw Actor/Details columns
- a detailed site-admin audit surface with redacted metadata, request peer and user agent
- bounded detailed-audit retention (180 days by default)

## Findings still requiring operational or future work

### Medium / operational — finish backend network isolation

The application now supports a shared `INTERNAL_PROXY_TOKEN` between the Next.js BFF and FastAPI. It only becomes an active boundary once the same random token is configured in both environments.

After that cutover:

- expose FastAPI through HTTPS/reverse proxy only
- firewall direct public access to port 8000 where possible
- retain `/health` only where readiness monitoring needs it

Do not rely on hiding the backend hostname as an authentication control.

### Admin MFA status

TOTP MFA is now implemented for administrator identities and stored encrypted at rest. It remains an enrollment step rather than a forced migration so the existing production administrator cannot be locked out during deployment.

Recommended production step: enroll the administrator immediately after migration/cutover, verify recovery procedure, then consider enforcing admin MFA policy globally.

### Encryption key rotation status

The crypto layer now accepts `WARPATH_ENCRYPTION_KEYS=newest,older...` and encrypts under the primary key while decrypting with the configured keyring. A dry-run/apply rotation script is included.

Operational requirement: create a fresh database backup before rotating ciphertext and retain the previous key until the post-rotation verification is complete.

### Medium — Python dependency versions are ranges, not a reproducible lock

The Node app has a lock file; Python production dependencies are broad ranges.

Recommended: generate and review a hashed Python lock/constraints file and build production from pinned versions.

### Low / operational — peer login throttle may see reverse-proxy addresses

The login email throttle remains effective per identity. The additional peer throttle uses the backend request peer. Behind a proxy this may represent proxy egress rather than the original browser.

Recommended: only trust a client-IP forwarding header when it is injected by a trusted authenticated reverse proxy; never trust arbitrary public `X-Forwarded-For` directly.

### Low — public health endpoint reveals service readiness

`/health` intentionally works without dashboard authentication. It reports whether the database is reachable and that authentication is required.

This is useful for readiness monitoring but is minor service metadata. Restrict it at the reverse proxy if external health checks do not require public access.

### Defense-in-depth — full nonce-based CSP

The applied CSP prevents framing/plugins/base-tag/form-target attacks without risking the current Next.js application. A stricter `script-src` / `style-src` policy should be implemented with Next-compatible nonces rather than adding unsafe directives casually.

## Inspect Element / Network / reverse engineering

A website cannot prevent the user who received frontend code from inspecting it.

Users can always inspect, to varying degrees:

- rendered HTML and CSS
- JavaScript delivered to their browser
- requests their browser sends
- response payloads returned to them
- public static assets

Minification, renamed routes and JavaScript obfuscation only increase effort. They are not security boundaries and can make maintenance/debugging worse.

BattleN0de should therefore assume the frontend is public knowledge.

The correct boundary is:

1. secrets never enter frontend bundles
2. proprietary/security-sensitive logic stays server-side
3. every backend request is authenticated and authorized independently
4. object ownership is checked server-side
5. CSRF and session validity are checked server-side
6. action permissions and plan limits are server-side
7. API responses contain only data the current user is permitted to receive
8. production source maps and interactive API docs stay disabled
9. backend origin/network access is restricted where practical

If logic would be damaging if someone reads it in DevTools, that logic does not belong in client-side JavaScript.

## Result

Current code has a solid server-side trust boundary plus a dedicated administrator security center. The most important remaining work before a larger paid rollout is completing the production proxy-token/network cutover, enrolling administrator MFA, performing the first backed-up encryption-key rotation, and adopting reproducible Python dependency pinning.
