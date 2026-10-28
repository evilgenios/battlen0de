'use client';

import Link from 'next/link';
import { DevelopmentToolsPanel } from './DevelopmentToolsPanel';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { ArrowLeft, Fingerprint, RadioTower, ShieldCheck } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { StatusBadge } from '@/components/accounts/StatusBadge';
import { ConnectionControls } from '@/components/accounts/ConnectionControls';
import { ObservationAccessControl } from '@/components/accounts/ObservationAccessControl';
import { DeleteAccountButton } from '@/components/accounts/DeleteAccountButton';
import { AccountOverviewStats } from '@/components/accounts/AccountOverviewStats';
import { ActionsPanel } from '@/components/accounts/ActionsPanel';
import { CommandStatusPanel } from '@/components/accounts/CommandStatusPanel';
import { ActiveActionsPanel } from '@/components/accounts/ActiveActionsPanel';
import { ProductionPanel } from '@/components/accounts/ProductionPanel';
import { ActivityTimeline } from '@/components/accounts/ActivityTimeline';
import { IntelligencePanel } from '@/components/accounts/IntelligencePanel';
import { ConquestGuardControl } from '@/components/accounts/ConquestGuardControl';
import { DiagnosticsPanel } from '@/components/accounts/DiagnosticsPanel';
import { useAccount } from '@/lib/hooks/useAccount';
import { useAccountStatus } from '@/lib/hooks/useAccountStatus';
import { useAccountSummary } from '@/lib/hooks/useIntel';
import { formatDateTime, formatUnixSeconds } from '@/lib/utils/format';

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-2.5 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium text-foreground">{value}</span>
    </div>
  );
}

export function AccountDetailsClient({ id }: { id: string }) {
  const { user } = useAuthSession();
  const { account, isLoading: accountLoading, error: accountError, refresh: refreshAccount } = useAccount(id);
  const { status } = useAccountStatus(id);
  const { summary } = useAccountSummary(id);

  if (accountLoading && !account) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-36 w-full rounded-[1.5rem]" />
        <Skeleton className="h-48 w-full rounded-2xl" />
        <Skeleton className="h-48 w-full rounded-2xl" />
      </div>
    );
  }

  if (accountError || !account) {
    return (
      <div className="space-y-6">
        <Link href="/accounts" className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" />
          Back to accounts
        </Link>
        <Card>
          <ErrorState error={accountError} onRetry={() => refreshAccount()} title="Could not load this account" />
        </Card>
      </div>
    );
  }

  const live = status?.live ?? null;
  const canRelink = user?.user_id === account.owner_user_id && ['active', 'needs_reauth'].includes(account.status);
  const connected = live?.state === 'connected';

  return (
    <div className="space-y-5 sm:space-y-7">
      <Link href="/accounts" className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Back to account fleet
      </Link>

      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <span className="command-eyebrow"><span className="command-dot text-info" /> Account command</span>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="truncate text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">{account.label}</h1>
              <StatusBadge state={live?.state} />
            </div>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Live account state, intelligence, active operations, controls, diagnostics, and event history.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                <Fingerprint className="h-3.5 w-3.5 text-accent" /> UID {account.app_uid}
              </span>
              <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
                <RadioTower className="h-3.5 w-3.5 text-info" /> {connected ? 'connected' : 'not connected'}
              </span>
              <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 text-success" /> {account.status}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {canRelink && (
              <Link
                className="rounded-xl border border-border/80 bg-surface/30 px-3 py-2 text-xs font-semibold text-foreground transition hover:border-accent/40 hover:bg-accent/5"
                href={`/accounts/${id}/relink`}
              >
                Relink credentials
              </Link>
            )}
            <ObservationAccessControl accountId={id} canAuthorize={user?.role === 'admin'} />
            <ConnectionControls accountId={id} liveState={live?.state} size="md" />
            <DeleteAccountButton accountId={id} accountLabel={account.label} size="md" redirectAfterDelete />
          </div>
        </div>
      </section>

      {live?.last_error && (
        <Card className="border-danger/30 bg-danger/5">
          <CardContent className="text-sm text-danger">
            <span className="font-medium">Last error: </span>
            {live.last_error}
          </CardContent>
        </Card>
      )}

      <AccountOverviewStats accountId={id} connected={connected} liveState={live?.state} />
      <CommandStatusPanel accountId={id} />
      <ProductionPanel accountId={id} connected={connected} />
      <DevelopmentToolsPanel accountId={id} connected={connected} />
      <ActiveActionsPanel accountId={id} connected={connected} excludeProduction />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Account information" description="Safe metadata only — credentials are never exposed here." />
          <CardContent className="divide-y divide-border/80">
            <InfoRow label="App UID" value={account.app_uid} />
            <InfoRow label="Linked email" value={account.linked_email ?? '—'} />
            <InfoRow label="Platform" value={account.platform} />
            <InfoRow label="Profile UID" value={account.profile_uid ?? '—'} />
            <InfoRow label="Account status" value={account.status} />
            <InfoRow label="Base level" value={summary?.mainbase_level ?? '—'} />
            <InfoRow label="Base state" value={summary?.base_state ?? '—'} />
            <InfoRow label="Coordinates" value={summary?.base_x != null ? `(${summary.base_x}, ${summary.base_y})` : '—'} />
            <InfoRow label="Linked at" value={formatDateTime(account.linked_at)} />
            <InfoRow label="Created" value={formatDateTime(account.created_at)} />
            <InfoRow label="Updated" value={formatDateTime(account.updated_at)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader title="Runtime / session status" description="Live state from this worker process." />
          <CardContent className="divide-y divide-border/80">
            <InfoRow label="Connection state" value={<StatusBadge state={live?.state} />} />
            <InfoRow label="Authenticated" value={live ? String(live.authenticated) : '—'} />
            <InfoRow label="Socket state" value={live?.connection_state ?? '—'} />
            <InfoRow label="Retry count" value={live?.retry_count ?? '—'} />
            <InfoRow label="Auth failure count" value={live?.auth_failure_count ?? '—'} />
            <InfoRow label="Session started" value={formatUnixSeconds(live?.started_at)} />
            <InfoRow label="Last connected" value={formatUnixSeconds(live?.last_connected_at)} />
          </CardContent>
        </Card>
      </div>

      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <span className="command-eyebrow"><span className="command-dot text-accent" /> Command deck</span>
          <div className="h-px flex-1 bg-border/70" />
        </div>
        <ActionsPanel accountId={id} connected={connected} />
        <ConquestGuardControl accountId={id} connected={connected} />
      </section>

      <IntelligencePanel accountId={id} connected={connected} />
      <DiagnosticsPanel accountId={id} connected={connected} />
      <ActivityTimeline accountId={id} />
    </div>
  );
}

