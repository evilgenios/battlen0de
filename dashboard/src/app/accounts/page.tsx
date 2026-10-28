'use client';

import Link from 'next/link';
import { PlusCircle, ShieldCheck, Users } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonRows } from '@/components/ui/Skeleton';
import { AccountsTable } from '@/components/accounts/AccountsTable';
import { useAccountsOverview } from '@/lib/hooks/useAccountsOverview';

export default function AccountsPage() {
  const { rows, isLoading, error, refresh } = useAccountsOverview();
  const connected = rows?.filter((row) => row.status?.live?.state === 'connected').length ?? 0;

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10 flex flex-col gap-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <span className="command-eyebrow"><span className="command-dot text-accent" /> Account fleet</span>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">Linked accounts</h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
              Manage ownership-safe Warpath identities and move directly into each account&apos;s live control view.
            </p>
          </div>
          <Link href="/accounts/new">
            <Button variant="primary" icon={<PlusCircle className="h-4 w-4" />}>Add account</Button>
          </Link>
        </div>

        <div className="relative z-10 mt-7 flex flex-wrap gap-2">
          <span className="data-chip rounded-full px-3 py-1.5 text-xs text-muted-foreground">
            <strong className="text-foreground">{rows?.length ?? 0}</strong> linked
          </span>
          <span className="data-chip rounded-full px-3 py-1.5 text-xs text-muted-foreground">
            <strong className="text-success">{connected}</strong> connected
          </span>
          <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-info" /> canonical identity enforced
          </span>
        </div>
      </section>

      <Card>
        <CardHeader
          title="Fleet roster"
          description="All Warpath accounts linked to your dashboard identity."
          action={<Badge tone="neutral">{rows?.length ?? 0} accounts</Badge>}
        />
        <CardContent className="p-0">
          {isLoading && !rows ? (
            <div className="p-5 sm:p-6"><SkeletonRows rows={5} /></div>
          ) : error ? (
            <ErrorState error={error} onRetry={() => refresh()} title="Could not load accounts" />
          ) : rows && rows.length > 0 ? (
            <AccountsTable rows={rows} />
          ) : (
            <EmptyState
              icon={Users}
              title="No accounts yet"
              description="Add your first Warpath account to start monitoring it from the command center."
              action={
                <Link href="/accounts/new">
                  <Button variant="primary" size="sm" icon={<PlusCircle className="h-4 w-4" />}>Add account</Button>
                </Link>
              }
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
