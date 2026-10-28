import { MemberOnly } from "@/components/marketplace/MarketplaceShell";
import { ListingWizard } from "@/components/marketplace/ListingWizard";
export default function SellPage() {
  return (
    <MemberOnly>
      <ListingWizard />
    </MemberOnly>
  );
}
