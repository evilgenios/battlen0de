import type { Metadata } from "next";
import { MarketplaceProvider } from "@/components/marketplace/MarketplaceProvider";
import { MarketplaceShell } from "@/components/marketplace/MarketplaceShell";
import "./marketplace.css";

export const metadata: Metadata = {
  title: "Commander Marketplace",
  description:
    "Explore the BattleN0de marketplace preview. Compare Warpath commander builds and discover the dedicated buyer and seller workspace.",
  robots: { index: false, follow: false },
};
export default function MarketplaceLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <MarketplaceProvider>
      <MarketplaceShell>{children}</MarketplaceShell>
    </MarketplaceProvider>
  );
}
