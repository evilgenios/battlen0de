import { MemberOnly } from "@/components/marketplace/MarketplaceShell";
import { SellerDashboard } from "@/components/marketplace/SellerDashboard";
export default function ListingsPage() {
  return (
    <MemberOnly>
      <SellerDashboard listingsOnly />
    </MemberOnly>
  );
}
