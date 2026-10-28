import { LinkAccountWizard } from '@/components/accounts/LinkAccountWizard';

export default async function RelinkPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <div className="max-w-lg space-y-4"><h1 className="text-xl font-semibold">Relink account</h1><p>Disconnect this account first. Verify its original game identity to replace credentials while preserving its history.</p><LinkAccountWizard accountId={id} /></div>;
}
