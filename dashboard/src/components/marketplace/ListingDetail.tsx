"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import useSWR from "swr";
import {
  ArrowLeft,
  ArrowRight,
  GitCompareArrows,
  Heart,
  LockKeyhole,
  ShieldCheck,
} from "lucide-react";
import { marketplaceApi } from "@/lib/api/marketplace";
import { DEMO_LISTINGS, money, strengthLabel } from "@/lib/marketplace/demo";
import { useAuthSession } from "@/lib/hooks/useAuthSession";
import { CommanderArtwork } from "./ListingCard";
import { useMarketplace } from "./MarketplaceProvider";
import { MarketplaceError } from "./MarketplaceShell";

export function ListingDetail({ id }: { id: string }) {
  const example = DEMO_LISTINGS.find((row) => row.id === id);
  const { data, error, isLoading, mutate } = useSWR(
    !example && !id.startsWith("demo-") ? ["marketplace-listing", id] : null,
    ([, key]) => marketplaceApi.listing(key),
  );
  const listing = example ?? data;
  const { config, isSaved, toggleSaved, comparison, toggleCompare } =
    useMarketplace();
  const { isAuthenticated } = useAuthSession();
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState(false);
  const [inquiry, setInquiry] = useState("");
  const [reason, setReason] = useState("");
  const [reporting, setReporting] = useState(false);
  const [reported, setReported] = useState(false);
  const router = useRouter();
  async function action(run: () => Promise<unknown>) {
    setBusy(true);
    setActionError("");
    try {
      await run();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  if (error)
    return <MarketplaceError error={error} retry={() => void mutate()} />;
  if (isLoading)
    return (
      <div className="mp-empty" role="status">
        Loading commander details…
      </div>
    );
  if (!listing)
    return (
      <div className="mp-empty">
        <h1>Commander not found.</h1>
        <Link href="/marketplace" className="mp-button mt-5">
          Explore the catalog
        </Link>
      </div>
    );
  const selected = comparison.some((row) => row.id === listing.id);
  const stats = [
    ["Strength", strengthLabel(listing.strength)],
    ["Collector level", listing.collector_level],
    ["Airspace", listing.airspace.toLocaleString()],
    ["Commander level", listing.commander_level],
    ["VIP level", listing.vip],
    ["Research progress", `${listing.research}%`],
  ];
  return (
    <>
      <Link href="/marketplace" className="mp-back-link mb-7">
        <ArrowLeft size={14} /> Back to commanders
      </Link>
      <div className="mp-page-heading">
        <p className="mp-kicker">
          SERVER {listing.server} / {listing.composition} /{" "}
          {listing.is_demo ? "SAMPLE COMMANDER" : "COMMANDER PROFILE"}
        </p>
        <h1>{listing.title}</h1>
        <p>
          {listing.commander_name} · A closer look at the development behind the
          headline.
        </p>
      </div>
      {listing.is_demo && (
        <div className="mp-preview-banner">
          <span className="mp-tag">DEMO</span>
          <p>
            This is a synthetic listing. Statistics, seller identity, and price
            are examples. It cannot be purchased or contacted.
          </p>
        </div>
      )}
      <div className="mp-detail-layout">
        <div>
          <CommanderArtwork listing={listing} large />
          <dl className="mp-stat-grid">
            {stats.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
          <section className="mp-panel mp-content-block">
            <h2>Commander overview</h2>
            <p className="mp-copy">{listing.description}</p>
          </section>
          <section className="mp-panel mp-content-block">
            <h2>Evidence & verification</h2>
            <p className="mp-copy">
              {listing.is_demo
                ? "Sample profiles have no verification evidence. In a live listing, each badge describes a specific review and its scope."
                : "Statistics are seller-submitted unless a review is explicitly shown below. Review results do not establish transferable account rights."}
            </p>
            <div className="mt-5">
              <div className="mp-verification-row">
                <span>Statistics reviewed</span>
                <span>
                  {listing.stats_reviewed
                    ? "Evidence reviewed"
                    : "Not reviewed"}
                </span>
              </div>
              <div className="mp-verification-row">
                <span>Control demonstrated</span>
                <span>
                  {listing.control_demonstrated
                    ? "Demonstrated at review"
                    : "Not demonstrated"}
                </span>
              </div>
              <div className="mp-verification-row">
                <span>Transaction eligibility</span>
                <span>Not enabled</span>
              </div>
            </div>
          </section>
          <div className="mp-notice mt-5 flex items-start gap-3">
            <LockKeyhole size={18} className="mt-1 shrink-0 text-accent" />
            <span>
              Marketplace profiles do not expose linked game sessions. Never
              share passwords, recovery codes, device identifiers, or session
              credentials in a listing or message.
            </span>
          </div>
        </div>
        <aside className="mp-panel mp-detail-sidebar">
          <p className="mp-kicker">
            {listing.is_demo
              ? "ILLUSTRATIVE ASKING PRICE"
              : "ASKING PRICE · USD"}
          </p>
          <p className="mt-3 text-4xl font-medium tracking-[-0.07em]">
            {money(listing.price_cents)}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            {listing.is_demo
              ? "Example only · no live offer"
              : "Listing price · no checkout available"}
          </p>
          <div className="my-6 border-y border-border py-5">
            <p className="flex items-center gap-2 text-sm">
              <ShieldCheck size={17} className="text-accent" />
              {listing.seller_name}
            </p>
            <p className="mt-2 text-xs text-muted-foreground">
              {listing.is_demo
                ? "Sample seller profile"
                : "BattleN0de marketplace seller"}
            </p>
          </div>
          <button
            type="button"
            className="mp-button"
            disabled={busy}
            aria-pressed={isSaved(listing)}
            onClick={() => void action(() => toggleSaved(listing))}
          >
            <Heart
              size={15}
              fill={isSaved(listing) ? "currentColor" : "none"}
            />
            {isSaved(listing) ? "Saved to your list" : "Save listing"}
          </button>
          <button
            type="button"
            className="mp-button"
            aria-pressed={selected}
            disabled={!selected && comparison.length >= 3}
            onClick={() => toggleCompare(listing)}
          >
            <GitCompareArrows size={16} />
            {selected ? "Remove from comparison" : "Add to comparison"}
          </button>
          {!listing.is_demo &&
            config?.messaging_enabled &&
            (isAuthenticated ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  void action(async () => {
                    const thread = await marketplaceApi.startConversation(
                      listing.id,
                      inquiry,
                    );
                    router.push(`/marketplace/inbox?conversation=${thread.id}`);
                  });
                }}
              >
                <label className="mp-field">
                  Ask the seller
                  <textarea
                    required
                    minLength={1}
                    maxLength={3000}
                    value={inquiry}
                    onChange={(e) => setInquiry(e.target.value)}
                    placeholder="Ask about the listed statistics…"
                  />
                </label>
                <button
                  type="submit"
                  className="mp-button mp-button-primary"
                  disabled={busy}
                >
                  Send inquiry <ArrowRight size={14} />
                </button>
              </form>
            ) : (
              <Link href="/login" className="mp-button mp-button-primary">
                Sign in to inquire
              </Link>
            ))}
          <button
            type="button"
            className="mp-button mp-button-primary"
            disabled
          >
            <LockKeyhole size={14} /> Checkout not enabled
          </button>
          <p className="mt-4 text-[10px] leading-5 text-muted-foreground">
            Offers, payments, and account transfers are unavailable in this
            release.
          </p>
          {!listing.is_demo && isAuthenticated && (
            <button
              type="button"
              className="mt-5 text-xs text-muted-foreground underline"
              onClick={() => setReporting(!reporting)}
            >
              Report this listing
            </button>
          )}
          {reporting && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void action(async () => {
                  await marketplaceApi.report(listing.id, reason);
                  setReported(true);
                  setReporting(false);
                });
              }}
            >
              <label className="mp-field">
                Reason for report
                <textarea
                  required
                  minLength={10}
                  maxLength={2000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
              </label>
              <button type="submit" disabled={busy} className="mp-button">
                Submit report
              </button>
            </form>
          )}
          {reported && (
            <p role="status" className="mt-4 text-xs text-success">
              Report sent to the review team.
            </p>
          )}
          {actionError && (
            <div className="mt-4">
              <MarketplaceError error={new Error(actionError)} />
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
