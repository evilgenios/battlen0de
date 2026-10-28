# Battlen0de Marketplace

The marketplace is part of the existing Next.js dashboard and FastAPI service.
This implementation covers the proposal's foundation, listing workflow,
buyer/seller workspaces, manual moderation and conditional private inquiries.
It defaults to a public **sample catalog**, with real listings kept private.

## Included

- `/marketplace`: searchable sample catalog, or real approved listings when explicitly enabled. Filters include server, strength, collector, airspace, commander level, VIP, research, military focus and price. Live results are paginated.
- `/marketplace/[slug]`: commander details, scoped verification results, saving, and conditional inquiries/reporting. No credentials or private evidence appear in public responses.
- `/marketplace/compare`: up to three listings, with attribute-by-attribute comparison. No fabricated account valuation.
- `/marketplace/favorites`: buyer shortlist. Synthetic favorites stay in browser storage; real favorites are bound to the signed-in user in PostgreSQL.
- `/marketplace/sell`: four-step private listing wizard, with seller-supplied statistics and private evidence notes.
- `/marketplace/dashboard` and `/marketplace/dashboard/listings`: seller profile, drafts, submission, pause/withdraw controls, review feedback and database notifications.
- `/marketplace/inbox`: participant-only conversations and replies. New communication requires the public release gates; existing history remains readable by its participants.
- `/marketplace/admin`: independent evidence review, reports, removal, action history and platform-admin permission controls.
- Marketplace links in the public landing-page navigation and the operational sidebar. The marketplace has its own layout and public discovery does not require login.

The three illustrative commanders and asking prices come from the supplied
proposal. They are never seeded into the database or treated as real inventory.

## Data and permissions

Migration `0007_marketplace` adds eight dedicated tables, prefixed
`marketplace_`: profiles, listings, favorites, conversations, messages,
reports, audit events and notifications. They share the existing PostgreSQL
connection pool. Their only foreign keys outside the marketplace are website
user IDs. They do not reference Warpath accounts, snapshots, credentials or sessions.

Important listing statistics use typed columns and indexes. Prices use integer
USD cents. The listing lifecycle is `draft -> pending_review -> active`, with
pause, withdrawal and rejection returning through explicit validated states.
Writes lock the listing row and require the current version. Editing invalidates
previous verification checks and requires review again. A commander/server
unique constraint prevents duplicate listings.

Existing website members can prepare private drafts. Submission requires
explicit seller access (platform admins retain operator access). Marketplace
moderators, administrators and owners can review; none of these marketplace
roles grants operational game privileges or platform administration. Only an
existing platform admin can change marketplace permissions. Reviewers cannot
review their own listings. Platform admins do not gain access to private chat
unless they are one of its participants.

All private endpoints use the existing session, CSRF, and durable product rate
limits. Private state uses the existing per-session SWR cache and component
tree. The same-origin `/api/backend` proxy and internal backend token continue
to protect service access. Public browsing is the only anonymous data surface.

## Deployment

1. Back up PostgreSQL and stop the worker using the existing deployment procedure.
2. From `service/`, with the deployment's `DATABASE_URL`, run `python -m alembic upgrade head`.
3. Deploy/restart the FastAPI worker and deploy the Next.js dashboard. Keep exactly one worker as required by the existing game-session system.
4. Leave the four `MARKETPLACE_*` variables in `.env.example` at `false` for preview.
5. Sign in with a provisioned website account. A platform admin can grant seller/reviewer access to another existing website user from `/marketplace/admin`.
6. Check draft creation, independent review, public non-disclosure, private conversation authorization, and rollback on a staging database before any production cutover.

The public catalog and new inquiries only enable when **all four** server-side
settings are exactly `true` (case-insensitive):

```env
MARKETPLACE_PUBLIC_ENABLED=false
MARKETPLACE_PUBLISHER_APPROVED=false
MARKETPLACE_LEGAL_APPROVED=false
MARKETPLACE_PROVIDER_APPROVED=false
```

These settings are operator attestations, not an approval workflow. Do not set
them merely to preview the UI. Sample discovery and private draft preparation
work without them. Even if all four are enabled, payments, transfers, offers
and uploads remain unimplemented and disabled.

The preview pages declare `noindex, nofollow` and are not added to the sitemap.
If the backend is unavailable, sample exploration is explicitly labeled and
private operations show an error. A live catalog error is never silently
replaced with synthetic inventory.

## Remaining proposal phases

Secure screenshot/evidence uploads need configured private object storage,
presigned upload limits, file validation/scanning and metadata stripping.
This release accepts private evidence notes only and exposes no upload route.
Manual verification records statistics review and control demonstration;
identity checks, evidence-file retention and staff-assignment workflows remain
future work. No check implies transferable rights or guaranteed safety.

Structured offers/counteroffers, transactions, provider webhooks, payouts,
refunds and disputes remain future phases. There is no wallet, checkout or
payment-provider integration. Following sellers, saved-search notifications,
historical view analytics, email/Discord notifications and valuation assistance
are also not included. Notifications in this release are database records shown
inside the seller workspace.

## Validation

`service/tests/test_marketplace.py` uses a real SQLAlchemy store and a disposable
SQLite database with foreign keys enabled. It covers persistence, public gates,
authentication/CSRF, owner isolation, duplicates, review state/version checks,
role restrictions, notifications, chat isolation, favorites and reports.
SQLite does not verify PostgreSQL row-lock behavior. Real PostgreSQL migration,
concurrency and schema drift checks must run against a disposable PostgreSQL
database before deployment; never point destructive tests at production.

`dashboard/src/components/marketplace/Marketplace.test.tsx` covers combined
filters, resets, browser-only demo saving, comparison, live error handling and
the complete draft wizard. Standard project tests, type checking, lint and
production build apply to this module as well.
