import type { Listing } from "@/lib/api/marketplace";

/** Synthetic proposal examples. Never sent to the database or presented as live inventory. */
const examples = [
  {
    id: "demo-ground-commander",
    title: "Elite Ground Commander",
    commander_name: "Iron Vanguard",
    server: 32,
    strength: 822000000,
    collector_level: 68,
    airspace: 1900,
    price_cents: 145000,
    composition: "ground",
    research: 92,
    vip: 18,
    commander_level: 80,
    seller_name: "Vanguard • Demo",
    description:
      "A ground-focused example with a developed armored core, infantry support, and balanced research. Explore the military statistics and compare this sample with other commander builds.",
  },
  {
    id: "demo-air-superiority",
    title: "Air Superiority Specialist",
    commander_name: "Sky Marshal",
    server: 41,
    strength: 758000000,
    collector_level: 56,
    airspace: 2030,
    price_cents: 118000,
    composition: "air",
    research: 86,
    vip: 17,
    commander_level: 76,
    seller_name: "Skyward • Demo",
    description:
      "An air-focused example built around airspace development and a specialized aircraft roster. A useful comparison for players evaluating air capability beyond headline strength.",
  },
  {
    id: "demo-balanced-base",
    title: "Balanced Midgame Base",
    commander_name: "Atlas",
    server: 58,
    strength: 345000000,
    collector_level: 42,
    airspace: 1250,
    price_cents: 39000,
    composition: "balanced",
    research: 64,
    vip: 12,
    commander_level: 60,
    seller_name: "Atlas • Demo",
    description:
      "A balanced example with room to develop both ground and air units. Compare its collector level, military research, and airspace against the more specialized sample builds.",
  },
] as const;
export const DEMO_LISTINGS: Listing[] = examples.map((row) => ({
  ...row,
  currency: "USD",
  status: "active",
  version: 1,
  is_demo: true,
  stats_reviewed: false,
  control_demonstrated: false,
  created_at: "2026-10-15T00:00:00Z",
  updated_at: "2026-10-15T00:00:00Z",
}));

export const money = (cents: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: cents % 100 === 0 ? 0 : 2,
  }).format(cents / 100);
export const strengthLabel = (value: number) =>
  value >= 1e9
    ? `${(value / 1e9).toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}B`
    : `${(value / 1e6).toFixed(1).replace(/\.0$/, "")}M`;
export const statusLabel = (status: string) =>
  status.replaceAll("_", " ").replace(/^./, (letter) => letter.toUpperCase());
