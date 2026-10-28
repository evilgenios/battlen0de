# BattleN0de

BattleN0de is a private-source Warpath account platform built as:

- **Next.js 16 dashboard** on Vercel
- **FastAPI persistent worker** for live game connections
- **PostgreSQL** for identity, account state, sessions, audit history and throttles
- **Caddy / HTTPS** in front of the backend host

## Public beta contract

The public beta is intentionally fail-closed.

Customers can link owned accounts, use Individual or Alliance workspaces, keep a durable read-only account connection, inspect production / movement / account telemetry, and review events. Read-only observation is enforced by a protobuf request allowlist.

Game-changing commands and automatic actions remain disabled while upstream command-confirmation evidence is unverified. The UI and marketing must not claim otherwise.

## Security boundary

- production session authentication with explicit member/admin roles
- owner-bound account isolation
- secure HttpOnly session cookies + CSRF validation
- encrypted Warpath credentials at rest
- hashed website-session and activation tokens
- server-only Next.js -> FastAPI internal proxy token
- production startup fails closed if the proxy token is missing/weak
- authenticated API rate limits backed by PostgreSQL
- admin MFA support and security audit history
- production API docs/source maps disabled
- FastAPI container bound to localhost behind the reverse proxy

## Launch configuration

For a customer-facing read-only beta, the backend must use:

```env
APP_ENV=production
AUTH_MODE=session
DASHBOARD_COOKIE_SECURE=true
AUTOSTART_ACTIVE_ACCOUNTS=false
OBSERVATION_ACCESS_MODE=customer
INTERNAL_PROXY_TOKEN=<32+ random characters>
```

Keep `OBSERVATION_ACCESS_MODE=pilot` for operator-only test sessions.

See [docs/PUBLIC_LAUNCH.md](docs/PUBLIC_LAUNCH.md) for the cutover and rollback checklist, and [docs/COMMAND_CONFIRMATION_EVIDENCE.md](docs/COMMAND_CONFIRMATION_EVIDENCE.md) for the gate that must be satisfied before game-changing actions are enabled.

## Development

The marketplace module is documented in [docs/MARKETPLACE.md](docs/MARKETPLACE.md).
It defaults to a clearly labeled sample catalog with private seller drafts and
moderation. Apply migration `0007_marketplace` before using its private API.

Backend:

```bash
cd service
python -m pytest -q
```

Dashboard:

```bash
cd dashboard
npm ci
npm test
npx next typegen
npx tsc --noEmit
npm run lint
npm run build
```

The GitHub Actions release gate runs backend tests, dependency audits, the backend Docker build, dashboard tests/typecheck/lint, and a production Next.js build.
