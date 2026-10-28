"use client";

import Link from "next/link";
import { ArrowRight, Heart, X } from "lucide-react";
import { DEMO_LISTINGS, money, strengthLabel } from "@/lib/marketplace/demo";
import type { Listing } from "@/lib/api/marketplace";
import { useMarketplace } from "./MarketplaceProvider";
import { EmptyCatalog, ListingCard } from "./ListingCard";

export function BuyerDashboard() {
  const { demoSaved, favorites } = useMarketplace();
  const items = [
    ...favorites,
    ...DEMO_LISTINGS.filter((row) => demoSaved.includes(row.id)),
  ];
  return (
    <>
      <div className="mp-page-heading">
        <p className="mp-kicker">YOUR BUYER WORKSPACE</p>
        <h1>A shortlist worth a closer look.</h1>
        <p>
          Keep interesting builds together and compare the details before you
          decide. Sample saves stay in this browser.
        </p>
      </div>
      <div className="mp-notice mb-7 flex items-center gap-3">
        <Heart size={17} className="shrink-0 text-accent" />
        <span>
          {favorites.length} live listings · {demoSaved.length} sample listings
          saved. Samples are illustrative and cannot be purchased.
        </span>
      </div>
      {items.length ? (
        <div className="mp-listing-grid">
          {items.map((listing) => (
            <ListingCard key={listing.id} listing={listing} />
          ))}
        </div>
      ) : (
        <>
          <EmptyCatalog
            title="Your shortlist starts here."
            text="Save a commander from the catalog to keep it here for comparison."
          />
          <Link
            href="/marketplace"
            className="mp-button mp-button-primary mt-5"
          >
            Discover commanders <ArrowRight size={15} />
          </Link>
        </>
      )}
    </>
  );
}

const metrics: {
  label: string;
  value: (row: Listing) => number;
  format: (n: number) => string;
  lower?: boolean;
}[] = [
  {
    label: "Asking price",
    value: (r) => r.price_cents,
    format: money,
    lower: true,
  },
  { label: "Strength", value: (r) => r.strength, format: strengthLabel },
  { label: "Commander level", value: (r) => r.commander_level, format: String },
  { label: "Collector level", value: (r) => r.collector_level, format: String },
  {
    label: "Airspace",
    value: (r) => r.airspace,
    format: (n) => n.toLocaleString(),
  },
  { label: "VIP level", value: (r) => r.vip, format: String },
  {
    label: "Research progress",
    value: (r) => r.research,
    format: (n) => `${n}%`,
  },
];
export function ComparisonView() {
  const { comparison, toggleCompare } = useMarketplace();
  return (
    <>
      <div className="mp-page-heading">
        <p className="mp-kicker">COMMANDER INTELLIGENCE</p>
        <h1>Look beyond the strength number.</h1>
        <p>
          Compare up to three commanders across their military development.
          Highlighted values show the leading number in each row, without
          implying a valuation.
        </p>
      </div>
      {comparison.length ? (
        <>
          <div className="mp-panel mp-table-wrap">
            <table className="mp-table">
              <caption className="mp-table-caption">
                {comparison.some((row) => row.is_demo)
                  ? "Includes synthetic sample data. Prices are illustrative."
                  : "Seller-submitted statistics. Review each listing’s verification scope."}
              </caption>
              <thead>
                <tr>
                  <th scope="col">Commander attributes</th>
                  {comparison.map((row) => (
                    <th key={row.id} scope="col">
                      <div className="flex items-start justify-between gap-4">
                        <Link
                          className="text-foreground"
                          href={`/marketplace/${row.id}`}
                        >
                          {row.title}
                        </Link>
                        <button
                          type="button"
                          aria-label={`Remove ${row.title} from comparison`}
                          onClick={() => toggleCompare(row)}
                        >
                          <X size={14} />
                        </button>
                      </div>
                      <p className="mt-2 text-[10px]">
                        Server {row.server} ·{" "}
                        {row.is_demo ? "Demo" : row.composition}
                      </p>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {metrics.map((metric) => {
                  const values = comparison.map(metric.value);
                  const best = metric.lower
                    ? Math.min(...values)
                    : Math.max(...values);
                  return (
                    <tr key={metric.label}>
                      <th scope="row">{metric.label}</th>
                      {comparison.map((row) => (
                        <td
                          key={row.id}
                          className={
                            comparison.length > 1 && metric.value(row) === best
                              ? "mp-best"
                              : ""
                          }
                        >
                          {metric.format(metric.value(row))}
                        </td>
                      ))}
                    </tr>
                  );
                })}
                <tr>
                  <th scope="row">Military focus</th>
                  {comparison.map((row) => (
                    <td key={row.id} className="capitalize">
                      {row.composition}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Statistics reviewed</th>
                  {comparison.map((row) => (
                    <td key={row.id}>
                      {row.stats_reviewed
                        ? "Evidence reviewed"
                        : "Not reviewed"}
                    </td>
                  ))}
                </tr>
                <tr>
                  <th scope="row">Control demonstrated</th>
                  {comparison.map((row) => (
                    <td key={row.id}>
                      {row.control_demonstrated
                        ? "At review time"
                        : "Not demonstrated"}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <div className="mp-notice mt-5">
            Research percentages and military statistics are supplied by
            sellers. This comparison does not assess account ownership,
            transferable rights, or fair market value.
          </div>
          <Link href="/marketplace" className="mp-button mt-5">
            {comparison.length < 3
              ? "Add another commander"
              : "Back to catalog"}{" "}
            <ArrowRight size={15} />
          </Link>
        </>
      ) : (
        <>
          <EmptyCatalog
            title="Start with two perspectives."
            text="Add commanders to comparison from the catalog. You can select up to three."
          />
          <Link
            href="/marketplace"
            className="mp-button mp-button-primary mt-5"
          >
            Choose commanders <ArrowRight size={15} />
          </Link>
        </>
      )}
    </>
  );
}
