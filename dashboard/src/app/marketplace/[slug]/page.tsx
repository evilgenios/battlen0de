import { ListingDetail } from "@/components/marketplace/ListingDetail";
export default async function ListingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return <ListingDetail id={slug} />;
}
