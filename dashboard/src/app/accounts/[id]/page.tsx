import { AccountDetailsClient } from '@/components/accounts/AccountDetailsClient';

export default async function AccountDetailsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AccountDetailsClient id={id} />;
}
