"use client";

import { useState } from "react";
import useSWR from "swr";
import { Check, ClipboardCheck, ShieldCheck } from "lucide-react";
import { marketplaceApi, type Listing } from "@/lib/api/marketplace";
import { useAuthSession } from "@/lib/hooks/useAuthSession";
import { money, strengthLabel } from "@/lib/marketplace/demo";
import { MarketplaceError } from "./MarketplaceShell";

export function AdminReviewQueue() {
  const { user } = useAuthSession();
  const { data, error, isLoading, mutate } = useSWR(
    "marketplace-reviews",
    marketplaceApi.reviews,
  );
  const [actionError, setActionError] = useState<unknown>();
  const [busy, setBusy] = useState("");
  async function resolve(id: string) {
    setBusy(id);
    setActionError(undefined);
    try {
      await marketplaceApi.resolve(id);
      await mutate();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <div className="mp-page-heading">
        <p className="mp-kicker">MARKETPLACE / TRUST & REVIEW</p>
        <h1>A review that means something.</h1>
        <p>
          Review seller-supplied evidence, record specific checks, and leave a
          clear decision. Approval does not bypass the marketplace’s release
          gates.
        </p>
      </div>
      {error ? (
        <MarketplaceError error={error} retry={() => void mutate()} />
      ) : isLoading || !data ? (
        <div className="mp-empty" role="status">
          Loading the moderation queue…
        </div>
      ) : (
        <>
          <div className="mp-metrics">
            <div className="mp-panel mp-metric">
              <p className="mp-kicker">Awaiting review</p>
              <strong>{data.listings.length}</strong>
            </div>
            <div className="mp-panel mp-metric">
              <p className="mp-kicker">Open reports</p>
              <strong>{data.reports.length}</strong>
            </div>
            <div className="mp-panel mp-metric">
              <p className="mp-kicker">Checkout</p>
              <strong className="!text-xl">Disabled</strong>
            </div>
            <div className="mp-panel mp-metric">
              <p className="mp-kicker">Review policy</p>
              <strong className="!text-xl">Independent</strong>
            </div>
          </div>
          {actionError ? (
            <div className="mb-5">
              <MarketplaceError error={actionError} />
            </div>
          ) : null}
          <div className="mp-dashboard-grid">
            <div className="space-y-5">
              <h2 className="text-lg font-medium tracking-tight">
                Listing review queue
              </h2>
              {data.listings.length ? (
                data.listings.map((listing) => (
                  <ReviewItem
                    key={`${listing.id}:${listing.version}`}
                    listing={listing}
                    own={listing.seller_id === user?.user_id}
                    onDone={() => mutate()}
                  />
                ))
              ) : (
                <div className="mp-panel mp-empty">
                  <ClipboardCheck size={30} className="text-accent" />
                  <h2>The review queue is clear.</h2>
                  <p>
                    Submitted listings will appear here for an independent
                    evidence review.
                  </p>
                </div>
              )}
              <section className="mp-panel p-5">
                <h2 className="mb-5 text-sm font-semibold">Open reports</h2>
                {data.reports.length ? (
                  data.reports.map((report) => (
                    <div
                      key={report.id}
                      className="border-t border-border py-4"
                    >
                      <p className="text-sm font-medium">{report.title}</p>
                      <p className="mp-copy my-3">{report.reason}</p>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="mp-button"
                          disabled={!!busy}
                          onClick={() => void resolve(report.id)}
                        >
                          Mark resolved
                        </button>
                        <RemoveReportedListing
                          id={report.listing_id}
                          version={report.version}
                          onDone={() => mutate()}
                        />
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="mp-copy !text-xs">No unresolved reports.</p>
                )}
              </section>
            </div>
            <aside className="space-y-5">
              <section className="mp-panel p-5">
                <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold">
                  <ShieldCheck size={16} className="text-accent" /> Review
                  principles
                </h2>
                <p className="mp-copy !text-xs">
                  Statistics reviewed and control demonstrated are separate
                  checks. Neither establishes transferable rights. Reviewers
                  cannot approve their own listings.
                </p>
              </section>
              <section className="mp-panel p-5">
                <h2 className="mb-4 text-sm font-semibold">
                  Recent action history
                </h2>
                {data.events.map((event) => (
                  <div key={event.id} className="border-t border-border py-3">
                    <p className="text-xs capitalize">
                      {event.action.replaceAll("_", " ")}
                    </p>
                    <time
                      dateTime={event.created_at}
                      className="mt-2 block text-[10px] text-muted-foreground"
                    >
                      {new Date(event.created_at).toLocaleString()}
                    </time>
                  </div>
                ))}
                {!data.events.length && (
                  <p className="mp-copy !text-xs">
                    No marketplace actions yet.
                  </p>
                )}
              </section>
            </aside>
          </div>
          {user?.role === "admin" && <PermissionForm />}
        </>
      )}
    </>
  );
}

function ReviewItem({
  listing,
  own,
  onDone,
}: {
  listing: Listing;
  own: boolean;
  onDone: () => Promise<unknown>;
}) {
  const [note, setNote] = useState("");
  const [stats, setStats] = useState(false);
  const [control, setControl] = useState(false);
  const [decision, setDecision] = useState<"approve" | "reject">("approve");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <article className="mp-panel p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="mp-kicker">
            SERVER {listing.server} / VERSION {listing.version}
          </p>
          <h3 className="mt-2 text-lg font-medium">{listing.title}</h3>
          <p className="mt-2 text-xs text-muted-foreground">
            {listing.seller_name} · Commander {listing.commander_id} ·{" "}
            {strengthLabel(listing.strength)} · {money(listing.price_cents)}
          </p>
        </div>
        <span className="mp-status-tag mp-status-pending_review">
          Awaiting review
        </span>
      </div>
      <p className="mp-copy mt-5">{listing.description}</p>
      <details className="mt-5 rounded-lg border border-border bg-background p-4">
        <summary className="cursor-pointer text-xs font-medium">
          Supporting evidence & military statistics
        </summary>
        <p className="mp-copy mt-4">
          {listing.evidence || "No evidence notes provided."}
        </p>
        <p className="mt-4 text-xs text-muted-foreground">
          Collector {listing.collector_level} · Airspace {listing.airspace} ·
          VIP {listing.vip} · Research {listing.research}% ·{" "}
          {listing.composition}
        </p>
      </details>
      {own ? (
        <p className="mp-notice mt-5">
          A different reviewer must review your listing.
        </p>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            setBusy(true);
            setError(undefined);
            void marketplaceApi
              .decision(listing, decision, note, stats, control)
              .then(onDone)
              .catch(setError)
              .finally(() => setBusy(false));
          }}
        >
          <div className="mt-5 flex flex-wrap gap-5">
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={stats}
                onChange={(e) => setStats(e.target.checked)}
              />
              Statistics evidence reviewed
            </label>
            <label className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={control}
                onChange={(e) => setControl(e.target.checked)}
              />
              Control demonstrated
            </label>
          </div>
          <label className="mp-field">
            Decision
            <select
              value={decision}
              onChange={(e) =>
                setDecision(e.target.value as "approve" | "reject")
              }
            >
              <option value="approve">
                Approve for publication when enabled
              </option>
              <option value="reject">Return to draft for changes</option>
            </select>
          </label>
          <label className="mp-field">
            Review note (shared with seller)
            <textarea
              required
              minLength={5}
              maxLength={2000}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Explain your decision and the scope of evidence reviewed."
            />
          </label>
          {error ? (
            <div className="mt-4">
              <MarketplaceError error={error} />
            </div>
          ) : null}
          <button
            type="submit"
            disabled={busy}
            className="mp-button mp-button-primary mt-5"
          >
            <Check size={14} />
            {busy ? "Recording decision…" : "Record decision"}
          </button>
        </form>
      )}
    </article>
  );
}

function RemoveReportedListing({
  id,
  version,
  onDone,
}: {
  id: string;
  version: number;
  onDone: () => Promise<unknown>;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  if (!open)
    return (
      <button
        type="button"
        className="mp-button text-danger"
        onClick={() => setOpen(true)}
      >
        Remove listing
      </button>
    );
  return (
    <form
      className="w-full"
      onSubmit={(e) => {
        e.preventDefault();
        setBusy(true);
        setError(undefined);
        void marketplaceApi
          .decision({ id, version } as Listing, "remove", note)
          .then(onDone)
          .catch(setError)
          .finally(() => setBusy(false));
      }}
    >
      <label className="mp-field">
        Reason for removal
        <textarea
          required
          minLength={5}
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </label>
      {error ? <MarketplaceError error={error} /> : null}
      <button
        disabled={busy}
        type="submit"
        className="mp-button mt-3 text-danger"
      >
        Confirm removal
      </button>
      <button
        type="button"
        className="mp-button ml-2"
        onClick={() => setOpen(false)}
      >
        Cancel
      </button>
    </form>
  );
}

function PermissionForm() {
  const [id, setId] = useState("");
  const [seller, setSeller] = useState(true);
  const [role, setRole] = useState("user");
  const [restricted, setRestricted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [done, setDone] = useState(false);
  return (
    <section className="mp-panel mt-7 p-6">
      <h2 className="text-lg font-medium">Marketplace access</h2>
      <p className="mp-copy mt-2">
        Platform administrators can grant seller and moderation access to an
        existing user. These permissions do not grant game account access.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          setBusy(true);
          setError(undefined);
          setDone(false);
          void marketplaceApi
            .permissions(id, seller, role, restricted)
            .then(() => setDone(true))
            .catch(setError)
            .finally(() => setBusy(false));
        }}
      >
        <div className="mp-form-grid">
          <label className="mp-field">
            Existing website user ID
            <input
              required
              pattern="[0-9a-fA-F-]{36}"
              value={id}
              onChange={(e) => setId(e.target.value)}
              placeholder="User UUID from Site Admin"
            />
          </label>
          <label className="mp-field">
            Marketplace role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="user">User</option>
              <option value="moderator">Moderator</option>
              <option value="marketplace_admin">
                Marketplace administrator
              </option>
              <option value="owner">Platform owner</option>
            </select>
          </label>
        </div>
        <div className="my-5 flex flex-wrap gap-5">
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={seller}
              onChange={(e) => setSeller(e.target.checked)}
            />
            Seller approval
          </label>
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={restricted}
              onChange={(e) => setRestricted(e.target.checked)}
            />
            Restrict marketplace access
          </label>
        </div>
        {error ? <MarketplaceError error={error} /> : null}
        {done && (
          <p role="status" className="mb-4 text-xs text-success">
            Marketplace permissions updated.
          </p>
        )}
        <button type="submit" className="mp-button" disabled={busy}>
          Update marketplace access
        </button>
      </form>
    </section>
  );
}
