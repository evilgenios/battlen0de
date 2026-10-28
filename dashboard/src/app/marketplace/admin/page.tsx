import { MemberOnly } from "@/components/marketplace/MarketplaceShell";
import { AdminReviewQueue } from "@/components/marketplace/AdminReviewQueue";
export default function ReviewPage() {
  return (
    <MemberOnly>
      <AdminReviewQueue />
    </MemberOnly>
  );
}
