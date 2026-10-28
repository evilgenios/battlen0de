# Warpath Control — dashboard (Stage 4)

Next.js control panel for the Warpath account-management backend
(`../service`, Stages 1–3). Talks to that FastAPI service exclusively
through its existing, unmodified API — see `../service/README.md` for the
backend itself.

## Architecture note: why there's a proxy route

The backend has no CORS configured, and this stage's brief was to treat its
API as a fixed contract rather than modify it. So the browser never calls
FastAPI directly: every request goes to this app's own
`src/app/api/backend/[...path]/route.ts`, a thin same-origin proxy that
forwards to `NEXT_PUBLIC_API_BASE_URL` server-side (server-to-server calls
aren't subject to CORS). `src/lib/api/client.ts` is the only place that
knows this — everything else just calls typed functions in `src/lib/api/`.

```
Browser  ──same-origin──>  Next.js route handler (proxy)  ──server-to-server──>  FastAPI
```

## Setup

```bash
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_BASE_URL to your backend
```

## Local development

Run the backend first (see `../service/README.md` — needs `DATABASE_URL`,
`WARPATH_ENCRYPTION_KEY` and explicit authentication configuration), then:

```bash
npm run dev
```

Open http://localhost:3000 (or whatever port you pass — this repo's own
`.claude/launch.json` runs it on 3000, alongside the backend on 8000, which
is what `.env.local`'s default points at).

## Tests

```bash
npm test          # run once
npm run test:watch
```

Uses Vitest + React Testing Library with the API layer mocked (`vi.mock`)
— no backend or network required. Every test render gets a fresh SWR cache
(`src/test/test-utils.tsx`) so tests can't leak state into each other.

## Production build

```bash
npm run build
npm start
```

## Deploying to Vercel

1. Import this repo into Vercel, set the project root to `dashboard/`.
2. Set `NEXT_PUBLIC_API_BASE_URL` in the Vercel project's environment
   variables to wherever the FastAPI worker is deployed — it must be
   reachable **from Vercel's servers**, not from end users' browsers, since
   only this app's own proxy route ever calls it.
3. Deploy. No other configuration is required — there's no database, no
   secrets, and no server-side state in this app; all of that lives in the
   backend.

## Authentication

Production requires login even before the first password user is provisioned.
See `../service/README.md` for explicit member/admin provisioning and the
isolated local/test mode. The browser cannot disable authentication through
health metadata; FastAPI checks every protected route independently.

`AuthSessionProvider` owns the website identity outside SWR. `/auth/me`
returns `user_id`, role and a non-authenticating `session_key`. Each website
session gets a fresh private SWR provider and component tree. Logout,
identity/session changes and 401 expiry clear private auth/account state;
other tabs receive a credential-free storage event and refresh identity.
Late responses cannot populate a different user's cache. Account action
invalidation uses the current provider's `mutate`, never global mutate.
Manual import, diagnostics and mass-deploy tools render only for admins;
the API enforces the same restriction. No redesign was included.

Validation: run `npm test`, then `npx next typegen && npx tsc --noEmit`,
and `npm run lint`. Read installed Next docs before changing App Router code.

## What's intentionally not here yet

- **A global events endpoint.** The backend only exposes
  `GET /accounts/{id}/events`. The `/events` page and the dashboard's
  "recent events" widget aggregate this client-side across every account
  (`src/lib/hooks/useAllEvents.ts`) — events belonging to an
  already-deleted account are not visible this way, since there's no
  account left to query events for. Documented in that hook's own comment.
- **WebSockets.** The backend doesn't have any; live status uses SWR
  polling (4s for an open account's live status, 15s for the account list
  and health, 8s for the accounts overview) per this stage's instructions.

### Phase 3 pilot flows

`/activate` is a public token-redemption form for operator-issued invitations
and recovery. Tokens stay in form memory, never URL parameters or browser
storage. Redemption sets the password and requires a fresh login. Settings
lists/revokes website sessions and shows provisioning only to explicit admins.
Revoking the current/all sessions calls the existing private-cache clear path.
Account detail links to `/accounts/[id]/relink` for the owner of an eligible
account; the backend requires it to be inactive and verifies the original
identity. These additions reuse the existing interface; no redesign was made.

The service now persists website sessions in PostgreSQL; game sessions and
pending linking challenges still require exactly one worker. See
[Phase 3 handoff](../docs/PHASE3_HANDOFF.md) and
[migration contract](../docs/PHASE3_MIGRATION.md).
