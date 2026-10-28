import { MemberOnly } from "@/components/marketplace/MarketplaceShell";
import { SellerDashboard } from "@/components/marketplace/SellerDashboard";
export default function SellerPage() {
  return (
    <MemberOnly>
      <SellerDashboard />
    </MemberOnly>
  );
}
