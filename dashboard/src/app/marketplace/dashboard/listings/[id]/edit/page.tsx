import { MemberOnly } from "@/components/marketplace/MarketplaceShell";
import { ListingWizard } from "@/components/marketplace/ListingWizard";
export default async function EditListingPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <MemberOnly>
      <ListingWizard id={id} />
    </MemberOnly>
  );
}
