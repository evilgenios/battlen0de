'use client';

import Link from 'next/link';
import { Users } from 'lucide-react';
import { LinkAccountWizard } from '@/components/accounts/LinkAccountWizard';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useAccountsOverview } from '@/lib/hooks/useAccountsOverview';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

export function AccountLinkGate() {
  const { user } = useAuthSession();
  const { rows, isLoading } = useAccountsOverview();

  if (isLoading && !rows) {
    return (
      <Card>
        <CardContent className="py-8 text-sm text-muted-foreground">Checking your account entitlement…</CardContent>
      </Card>
    );
  }

  const maxAccounts = user?.max_accounts;
  const reachedLimit = maxAccounts != null && (rows?.length ?? 0) >= maxAccounts;

  if (user?.plan === 'individual' && reachedLimit) {
    return (
      <Card>
        <CardHeader
          title="Individual account limit reached"
          description="Your current server policy allows one linked Warpath account."
        />
        <CardContent>
          <div className="rounded-xl border border-info/20 bg-info/5 p-4">
            <Users className="h-4 w-4 text-info" />
            <p className="mt-3 text-sm font-semibold text-foreground">Need another account?</p>
            <p className="mt-1.5 text-xs leading-5 text-muted-foreground">
              Alliance is the multi-account plan. Upgrading raises the backend account limit while keeping your existing linked identity intact.
            </p>
            <div className="mt-4 flex flex-wrap gap-2">
              <Link href="/#plans">
                <Button variant="primary" size="sm">View Alliance plan</Button>
              </Link>
              <Link href="/dashboard">
                <Button variant="outline" size="sm">Back to Individual</Button>
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  return <LinkAccountWizard />;
}
