"use client";

import Link from "next/link";
import { useState } from "react";
import {
  ArrowUpRight,
  Check,
  GitCompareArrows,
  Heart,
  Plane,
  Shield,
  ShieldCheck,
  Swords,
} from "lucide-react";
import type { Listing } from "@/lib/api/marketplace";
import { money, strengthLabel } from "@/lib/marketplace/demo";
import { useMarketplace } from "./MarketplaceProvider";

export function CommanderArtwork({
  listing,
  large = false,
}: {
  listing: Listing;
  large?: boolean;
}) {
  const Icon =
    listing.composition === "air"
      ? Plane
      : listing.composition === "ground"
        ? Swords
        : Shield;
  return (
    <div
      className={`mp-art mp-art-${listing.composition} ${large ? "mp-art-large" : ""}`}
    >
      <div className="mp-art-grid" />
      <div className="mp-art-orbit" />
      <div className="mp-art-cross mp-art-cross-a" />
      <div className="mp-art-cross mp-art-cross-b" />
      <span className="mp-art-coordinate">
        WPT / S{String(listing.server).padStart(3, "0")}
      </span>
      <Icon className="mp-art-icon" strokeWidth={0.8} aria-hidden="true" />
      <span className="mp-art-type">
        {listing.composition === "air"
          ? "Air superiority"
          : listing.composition === "ground"
            ? "Ground command"
            : "Combined arms"}
      </span>
      <span className="mp-art-number">
        {String(listing.commander_level).padStart(2, "0")}
        <small>COMMANDER LVL</small>
      </span>
    </div>
  );
}

export function ListingCard({ listing }: { listing: Listing }) {
  const { toggleSaved, isSaved, comparison, toggleCompare } = useMarketplace();
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const selected = comparison.some((row) => row.id === listing.id);
  async function save() {
    setError("");
    setSaving(true);
    try {
      await toggleSaved(listing);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save listing.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <article className="mp-listing-card">
      <div className="relative">
        <Link
          href={`/marketplace/${listing.id}`}
          aria-label={`View ${listing.title}`}
        >
          <CommanderArtwork listing={listing} />
        </Link>
        <div className="mp-card-flags">
          <span className="mp-tag">
            {listing.is_demo
              ? "DEMO LISTING"
              : listing.stats_reviewed
                ? "STATS REVIEWED"
                : "SELLER SUBMITTED"}
          </span>
          <button
            type="button"
            className={`mp-icon-button ${isSaved(listing) ? "mp-saved" : ""}`}
            aria-label={`${isSaved(listing) ? "Unsave" : "Save"} ${listing.title}`}
            aria-pressed={isSaved(listing)}
            disabled={saving}
            onClick={() => void save()}
          >
            <Heart
              size={16}
              fill={isSaved(listing) ? "currentColor" : "none"}
            />
          </button>
        </div>
      </div>
      <div className="p-5">
        <p className="mp-kicker">
          SERVER {listing.server} <span className="mx-2 text-border">/</span>{" "}
          {listing.composition}
        </p>
        <Link href={`/marketplace/${listing.id}`} className="mp-card-title">
          {listing.title}
          <ArrowUpRight size={16} />
        </Link>
        <div className="mp-card-stats">
          <div>
            <strong>{strengthLabel(listing.strength)}</strong>
            <span>Strength</span>
          </div>
          <div>
            <strong>{listing.collector_level}</strong>
            <span>Collector</span>
          </div>
          <div>
            <strong>{listing.airspace.toLocaleString()}</strong>
            <span>Airspace</span>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-border/60 pt-4">
          <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
            <ShieldCheck size={14} className="shrink-0 text-accent" />
            <span className="truncate">{listing.seller_name}</span>
          </span>
          <div className="text-right">
            <strong className="mp-price">{money(listing.price_cents)}</strong>
            <span className="block text-[9px] text-muted-foreground">
              {listing.is_demo ? "Illustrative price" : "Asking price · USD"}
            </span>
          </div>
        </div>
        <button
          type="button"
          className={`mp-compare-button ${selected ? "mp-compare-selected" : ""}`}
          onClick={() => toggleCompare(listing)}
          aria-pressed={selected}
          disabled={!selected && comparison.length >= 3}
        >
          {selected ? <Check size={14} /> : <GitCompareArrows size={14} />}
          {selected ? "Added to comparison" : "Add to comparison"}
        </button>
        {error && (
          <p role="alert" className="mt-2 text-xs text-danger">
            {error}
          </p>
        )}
      </div>
    </article>
  );
}

export function EmptyCatalog({
  title = "No commanders found.",
  text = "Try a different search or reset your filters.",
}: {
  title?: string;
  text?: string;
}) {
  return (
    <div className="mp-panel mp-empty">
      <Swords size={30} className="text-accent" />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}
