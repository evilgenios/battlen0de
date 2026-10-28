"use client";

import { useDeferredValue, useState } from "react";
import Link from "next/link";
import useSWR from "swr";
import {
  ArrowRight,
  CheckCheck,
  GitCompareArrows,
  LockKeyhole,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { marketplaceApi } from "@/lib/api/marketplace";
import { DEMO_LISTINGS } from "@/lib/marketplace/demo";
import { useMarketplace } from "./MarketplaceProvider";
import { EmptyCatalog, ListingCard } from "./ListingCard";
import { MarketplaceError } from "./MarketplaceShell";

const initialFilters = {
  q: "",
  server: "",
  composition: "",
  strength: "",
  collector: "",
  airspace: "",
  vip: "",
  commander: "",
  research: "",
  price: "",
  sort: "newest",
};
export type CatalogFilters = typeof initialFilters;
export function filterExamples(filters: CatalogFilters) {
  const rows = DEMO_LISTINGS.filter(
    (row) =>
      `${row.title} ${row.commander_name}`
        .toLowerCase()
        .includes(filters.q.toLowerCase()) &&
      (!filters.server || row.server === Number(filters.server)) &&
      (!filters.composition || row.composition === filters.composition) &&
      row.strength >= Number(filters.strength) * 1e6 &&
      row.collector_level >= Number(filters.collector) &&
      row.airspace >= Number(filters.airspace) &&
      row.vip >= Number(filters.vip) &&
      row.commander_level >= Number(filters.commander) &&
      row.research >= Number(filters.research) &&
      (!filters.price || row.price_cents <= Number(filters.price) * 100),
  );
  return rows.sort((a, b) =>
    filters.sort === "price_asc"
      ? a.price_cents - b.price_cents
      : filters.sort === "price_desc"
        ? b.price_cents - a.price_cents
        : filters.sort === "strength"
          ? b.strength - a.strength
          : b.created_at.localeCompare(a.created_at),
  );
}

export function Storefront() {
  const { config } = useMarketplace();
  const [filters, setFilters] = useState(initialFilters);
  const [advanced, setAdvanced] = useState(false);
  const [offset, setOffset] = useState(0);
  const deferred = useDeferredValue(filters);
  const live = config?.public_listings_enabled === true;
  const params = new URLSearchParams({
    q: deferred.q,
    sort: deferred.sort,
    offset: String(offset),
    limit: "24",
  });
  for (const [key, value] of Object.entries({
    server: deferred.server,
    composition: deferred.composition,
    min_strength: deferred.strength
      ? String(Number(deferred.strength) * 1e6)
      : "",
    min_collector: deferred.collector,
    min_airspace: deferred.airspace,
    min_vip: deferred.vip,
    min_commander: deferred.commander,
    min_research: deferred.research,
    max_price: deferred.price
      ? String(Math.round(Number(deferred.price) * 100))
      : "",
  }))
    if (value) params.set(key, value);
  const { data, error, isLoading, mutate } = useSWR(
    live ? ["marketplace-listings", params.toString()] : null,
    ([, query]) => marketplaceApi.listings(query),
  );
  const items = live ? (data?.items ?? []) : filterExamples(deferred);
  const total = live ? (data?.total ?? 0) : items.length;
  function change(key: keyof CatalogFilters, value: string) {
    setFilters((current) => ({ ...current, [key]: value }));
    setOffset(0);
  }
  const active = Object.entries(filters).filter(
    ([key, value]) => value && key !== "sort" && key !== "q",
  ).length;
  return (
    <>
      <section className="mp-hero">
        <div className="mp-hero-content">
          <p className="mp-kicker">
            <span className="mp-dot" /> THE NEXT CHAPTER OF BATTLEN0DE
          </p>
          <h1>
            Your next command.
            <br />
            <span>A clearer perspective.</span>
          </h1>
          <p className="mp-hero-description">
            Discover the details behind every Commander. Compare military
            development, explore specialized builds, and find your next
            direction.
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <a href="#catalog" className="mp-button mp-button-primary">
              Explore commanders <ArrowRight size={16} />
            </a>
            <Link href="/marketplace/compare" className="mp-back-link">
              <GitCompareArrows size={16} /> Compare side by side
            </Link>
          </div>
        </div>
        <div className="mp-hero-radar" aria-hidden="true">
          <div />
          <div />
          <div />
          <span className="mp-radar-axis" />
          <GitCompareArrows size={48} strokeWidth={1} />
          <span className="mp-radar-label">INTELLIGENCE BEFORE COMMITMENT</span>
          <i />
          <i />
        </div>
        <span className="mp-hero-index">N0DE / MARKETPLACE / 01</span>
      </section>
      <div className="mp-trust-strip">
        <span>
          <CheckCheck size={16} /> Statistics with context
        </span>
        <span>
          <GitCompareArrows size={16} /> Built for real comparison
        </span>
        <span>
          <LockKeyhole size={16} /> Your game access stays private
        </span>
      </div>
      {!live && (
        <div className="mp-preview-banner">
          <span className="mp-tag">PREVIEW</span>
          <p>
            Explore {DEMO_LISTINGS.length} sample commanders. All statistics,
            sellers, and prices are illustrative. Public trading and checkout
            are not enabled.
          </p>
        </div>
      )}
      <section id="catalog" className="scroll-mt-6">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mp-kicker">THE COMMANDER INDEX</p>
            <h2 className="mp-section-title">Find your next advantage.</h2>
          </div>
          <span className="text-xs text-muted-foreground">
            {live ? "Seller-submitted listings" : "A look at what’s coming"}
          </span>
        </div>
        <div className="mp-catalog-layout">
          <aside className="mp-filters mp-panel">
            <div className="flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <SlidersHorizontal size={15} /> Refine search
              </h3>
              <button
                type="button"
                onClick={() => {
                  setFilters(initialFilters);
                  setOffset(0);
                }}
                className="text-xs text-accent"
              >
                Reset
              </button>
            </div>
            <label className="mp-field">
              Server
              <input
                type="number"
                min="1"
                max="10000"
                placeholder="All servers"
                value={filters.server}
                onChange={(e) => change("server", e.target.value)}
              />
            </label>
            <label className="mp-field">
              Military focus
              <select
                value={filters.composition}
                onChange={(e) => change("composition", e.target.value)}
              >
                <option value="">All compositions</option>
                <option value="ground">Ground command</option>
                <option value="air">Air superiority</option>
                <option value="balanced">Combined arms</option>
              </select>
            </label>
            <label className="mp-field">
              Minimum strength <span className="mp-input-unit">M</span>
              <input
                type="number"
                min="0"
                placeholder="e.g. 500"
                value={filters.strength}
                onChange={(e) => change("strength", e.target.value)}
              />
            </label>
            <label className="mp-field">
              Maximum price <span className="mp-input-unit">USD</span>
              <input
                type="number"
                min="0"
                placeholder="Any budget"
                value={filters.price}
                onChange={(e) => change("price", e.target.value)}
              />
            </label>
            <button
              type="button"
              className="mp-filter-expand"
              aria-expanded={advanced}
              onClick={() => setAdvanced(!advanced)}
            >
              {advanced ? "Fewer filters" : "Advanced filters"}{" "}
              <span>{advanced ? "−" : "+"}</span>
            </button>
            {advanced && (
              <>
                {(
                  [
                    ["collector", "Minimum collector level"],
                    ["airspace", "Minimum airspace"],
                    ["commander", "Minimum commander level"],
                    ["vip", "Minimum VIP"],
                    ["research", "Minimum research %"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="mp-field">
                    {label}
                    <input
                      type="number"
                      min="0"
                      value={filters[key]}
                      onChange={(e) => change(key, e.target.value)}
                      placeholder="Any"
                    />
                  </label>
                ))}
              </>
            )}
            <div className="mp-filter-note">
              <ShieldCheckIcon />
              <strong>Know what’s been checked.</strong>
              <p>
                Verification describes a specific review. It never guarantees
                transferable rights or account safety.
              </p>
            </div>
          </aside>
          <div className="min-w-0">
            <div className="mp-search-row">
              <label className="mp-search">
                <Search size={18} />
                <input
                  aria-label="Search commanders"
                  placeholder="Search commanders, builds, or specialties…"
                  value={filters.q}
                  onChange={(e) => change("q", e.target.value)}
                />
                {filters.q && (
                  <button
                    type="button"
                    aria-label="Clear search"
                    onClick={() => change("q", "")}
                  >
                    <X size={16} />
                  </button>
                )}
              </label>
              <label className="mp-sort">
                <span className="sr-only">Sort listings</span>
                <select
                  value={filters.sort}
                  onChange={(e) => change("sort", e.target.value)}
                >
                  <option value="newest">Newest first</option>
                  <option value="price_asc">Price: low to high</option>
                  <option value="price_desc">Price: high to low</option>
                  <option value="strength">Highest strength</option>
                </select>
              </label>
            </div>
            <div className="my-5 flex justify-between text-xs text-muted-foreground">
              <span>
                <strong className="text-foreground">{total}</strong>{" "}
                {live ? "commanders" : "sample commanders"}
                {active > 0 ? ` · ${active} filters applied` : ""}
              </span>
              <span>
                {isLoading ? "Loading listings…" : "Compare up to 3 accounts"}
              </span>
            </div>
            {error ? (
              <MarketplaceError error={error} retry={() => void mutate()} />
            ) : isLoading ? (
              <div className="mp-empty" role="status">
                Loading commanders…
              </div>
            ) : items.length ? (
              <div className="mp-listing-grid">
                {items.map((row) => (
                  <ListingCard key={row.id} listing={row} />
                ))}
              </div>
            ) : (
              <EmptyCatalog />
            )}
            {live && total > 24 && (
              <div className="mt-6 flex items-center justify-center gap-5">
                <button
                  type="button"
                  className="mp-button"
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 24))}
                >
                  Previous
                </button>
                <span className="text-sm">
                  Page {Math.floor(offset / 24) + 1}
                </span>
                <button
                  type="button"
                  className="mp-button"
                  disabled={offset + 24 >= total}
                  onClick={() => setOffset(offset + 24)}
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      </section>
      <section className="mp-bottom-callout">
        <div>
          <p className="mp-kicker">BUILT A COMMANDER WORTH KNOWING?</p>
          <h2>Give the details a proper home.</h2>
          <p>
            Create a private draft, organize your statistics, and prepare for
            review.
          </p>
        </div>
        <Link href="/marketplace/sell" className="mp-button">
          Create your listing <ArrowRight size={16} />
        </Link>
      </section>
    </>
  );
}
function ShieldCheckIcon() {
  return <CheckCheck size={20} className="mb-3 text-accent" />;
}
