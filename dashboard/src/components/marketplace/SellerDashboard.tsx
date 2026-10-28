"use client";

import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { ArrowRight, Bell, FileText, Plus, ShieldCheck } from "lucide-react";
import { marketplaceApi, type Listing } from "@/lib/api/marketplace";
import { money, statusLabel } from "@/lib/marketplace/demo";
import { MarketplaceError } from "./MarketplaceShell";

export function SellerDashboard({
  listingsOnly = false,
}: {
  listingsOnly?: boolean;
}) {
  const { data, error, isLoading, mutate } = useSWR(
    "marketplace-dashboard",
    marketplaceApi.dashboard,
  );
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState<unknown>();
  const [confirm, setConfirm] = useState("");
  const [savedProfile, setSavedProfile] = useState(false);
  async function action(
    listing: Listing,
    kind: "submit" | "pause" | "withdraw",
  ) {
    setBusy(listing.id);
    setActionError(undefined);
    try {
      await marketplaceApi.transition(listing, kind);
      await mutate();
      setConfirm("");
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy("");
    }
  }
  if (error)
    return <MarketplaceError error={error} retry={() => void mutate()} />;
  if (isLoading || !data)
    return (
      <div className="mp-empty" role="status">
        Loading your seller workspace…
      </div>
    );
  const metrics = [
    ["Active listings", data.counts.active],
    ["Awaiting review", data.counts.pending_review],
    ["Private drafts", data.counts.draft],
    ["Conversations", data.counts.conversations],
  ];
  return (
    <>
      <div className="mp-page-heading flex flex-wrap items-end justify-between gap-5">
        <div>
          <p className="mp-kicker">
            SELLER WORKSPACE / {data.profile.display_name}
          </p>
          <h1>
            {listingsOnly
              ? "Your commander listings."
              : "A home for every detail."}
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            {listingsOnly
              ? "Manage drafts, review status, and publication from one place."
              : "Prepare your listings, follow reviews, and keep the conversation moving."}
          </p>
        </div>
        <Link href="/marketplace/sell" className="mp-button mp-button-primary">
          <Plus size={16} /> Create listing
        </Link>
      </div>
      {data.profile.restricted && (
        <div className="mp-error mb-5">
          Your marketplace access is restricted. Contact your platform
          administrator.
        </div>
      )}
      {!data.profile.seller_enabled && (
        <div className="mp-notice mb-6 flex items-start gap-3">
          <ShieldCheck size={18} className="mt-1 shrink-0 text-accent" />
          <span>
            Draft creation is available. Seller approval is required before you
            can submit a listing to the review queue.
          </span>
        </div>
      )}
      {!listingsOnly && (
        <div className="mp-metrics">
          {metrics.map(([label, count]) => (
            <div className="mp-panel mp-metric" key={label}>
              <p className="mp-kicker">{label}</p>
              <strong>{count}</strong>
            </div>
          ))}
        </div>
      )}
      {actionError ? (
        <div className="mb-5">
          <MarketplaceError error={actionError} />
        </div>
      ) : null}
      <div className={listingsOnly ? "" : "mp-dashboard-grid"}>
        <section className="mp-panel overflow-hidden">
          <div className="flex items-center justify-between border-b border-border p-5">
            <h2 className="text-sm font-semibold">
              My listings{" "}
              <span className="ml-2 text-xs font-normal text-muted-foreground">
                {data.listings.length}
              </span>
            </h2>
            {!listingsOnly && (
              <Link
                href="/marketplace/dashboard/listings"
                className="mp-back-link"
              >
                View all <ArrowRight size={13} />
              </Link>
            )}
          </div>
          {data.listings.length ? (
            data.listings.map((listing) => (
              <div key={listing.id} className="mp-list-row">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <h3>{listing.title}</h3>
                    <span
                      className={`mp-status-tag mp-status-${listing.status}`}
                    >
                      {statusLabel(listing.status)}
                    </span>
                  </div>
                  <p>
                    Server {listing.server} · {money(listing.price_cents)} ·
                    Version {listing.version}
                  </p>
                  {listing.review_note && (
                    <p className="mp-copy mt-2">
                      Reviewer: {listing.review_note}
                    </p>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  {["draft", "paused"].includes(listing.status) && (
                    <Link
                      href={`/marketplace/dashboard/listings/${listing.id}/edit`}
                      className="mp-button !min-h-8 !px-3 !py-2 !text-[10px]"
                    >
                      Edit draft
                    </Link>
                  )}
                  {["draft", "paused"].includes(listing.status) &&
                    data.profile.seller_enabled && (
                      <button
                        disabled={!!busy}
                        type="button"
                        className="mp-button !min-h-8 !px-3 !py-2 !text-[10px]"
                        onClick={() => void action(listing, "submit")}
                      >
                        Submit for review
                      </button>
                    )}
                  {listing.status === "active" && (
                    <button
                      disabled={!!busy}
                      type="button"
                      className="mp-button !min-h-8 !px-3 !py-2 !text-[10px]"
                      onClick={() => void action(listing, "pause")}
                    >
                      Pause
                    </button>
                  )}
                  {listing.status !== "removed" &&
                    (confirm === listing.id ? (
                      <>
                        <button
                          type="button"
                          disabled={!!busy}
                          className="mp-button !min-h-8 !px-3 !py-2 !text-[10px] text-danger"
                          onClick={() => void action(listing, "withdraw")}
                        >
                          Confirm withdrawal
                        </button>
                        <button
                          type="button"
                          className="text-xs text-muted-foreground"
                          onClick={() => setConfirm("")}
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        disabled={!!busy}
                        className="mp-button !min-h-8 !px-3 !py-2 !text-[10px]"
                        onClick={() => setConfirm(listing.id)}
                      >
                        Withdraw
                      </button>
                    ))}
                </div>
              </div>
            ))
          ) : (
            <div className="mp-empty">
              <FileText size={28} className="text-accent" />
              <h2>Your first listing starts here.</h2>
              <p>Organize a commander’s statistics into a private draft.</p>
              <Link href="/marketplace/sell" className="mp-button mt-5">
                Create a draft <Plus size={14} />
              </Link>
            </div>
          )}
        </section>
        {!listingsOnly && (
          <aside className="space-y-5">
            <section className="mp-panel p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold">
                <ShieldCheck size={16} className="text-accent" /> Seller profile
              </h2>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const name = String(
                    new FormData(e.currentTarget).get("display_name"),
                  );
                  setBusy("profile");
                  setSavedProfile(false);
                  setActionError(undefined);
                  void marketplaceApi
                    .profile(name)
                    .then(async () => {
                      await mutate();
                      setSavedProfile(true);
                    })
                    .catch(setActionError)
                    .finally(() => setBusy(""));
                }}
              >
                <label className="mp-field">
                  Public display name
                  <input
                    name="display_name"
                    required
                    minLength={2}
                    maxLength={60}
                    defaultValue={data.profile.display_name}
                  />
                </label>
                <button
                  type="submit"
                  disabled={!!busy}
                  className="mp-button mt-4"
                >
                  Save profile
                </button>
                {savedProfile && (
                  <p role="status" className="mt-3 text-xs text-success">
                    Profile updated.
                  </p>
                )}
              </form>
            </section>
            <section className="mp-panel p-5">
              <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold">
                <Bell size={16} className="text-accent" /> Recent updates
              </h2>
              {data.notifications.length ? (
                data.notifications.map((note) => (
                  <div key={note.id} className="border-t border-border py-3">
                    <p className="mp-copy !text-xs">{note.text}</p>
                    <time className="mt-2 block text-[10px] text-muted-foreground">
                      {new Date(note.created_at).toLocaleDateString()}
                    </time>
                  </div>
                ))
              ) : (
                <p className="mp-copy !text-xs">
                  Review decisions and new inquiry notifications will appear
                  here.
                </p>
              )}
            </section>
            <div className="mp-notice">
              Approved listings remain private while the marketplace is in
              preview. Payments and account transfers are not enabled.
            </div>
          </aside>
        )}
      </div>
    </>
  );
}
