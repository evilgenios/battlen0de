'use client';

import Link from 'next/link';
import {
  ArrowRight,
  Fingerprint,
  Gauge,
  PlusCircle,
  ShieldCheck,
  Sparkles,
  Users,
  Wifi,
} from 'lucide-react';
import { AccountOverviewStats } from '@/components/accounts/AccountOverviewStats';
import { ActiveActionsPanel } from '@/components/accounts/ActiveActionsPanel';
import { ActionsPanel } from '@/components/accounts/ActionsPanel';
import { ActivityTimeline } from '@/components/accounts/ActivityTimeline';
import { ConnectionControls } from '@/components/accounts/ConnectionControls';
import { ConquestGuardControl } from '@/components/accounts/ConquestGuardControl';
import { ProductionPanel } from '@/components/accounts/ProductionPanel';
import { StatusBadge } from '@/components/accounts/StatusBadge';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useAccountsOverview } from '@/lib/hooks/useAccountsOverview';

export default function IndividualDashboardPage() {
  const { rows, isLoading, error, refresh } = useAccountsOverview();

  if (isLoading && !rows) {
    return (
      <div className="space-y-5 sm:space-y-7">
        <Skeleton className="h-64 w-full rounded-[1.5rem]" />
        <Skeleton className="h-28 w-full rounded-2xl" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }

  if (error) {
    return (
      <Card>
        <ErrorState error={error} onRetry={() => refresh()} title="Could not load your account" />
      </Card>
    );
  }

  if (!rows || rows.length === 0) {
    return (
      <div className="space-y-5 sm:space-y-7">
        <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8 lg:p-10">
          <div className="scan-line" />
          <div className="relative z-10 max-w-3xl">
            <span className="command-eyebrow">
              <span className="command-dot text-accent" />
              Individual plan
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.055em] text-foreground sm:text-5xl">
              Your personal Warpath command cockpit.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground sm:text-[15px]">
              Individual is built around one account: one connection, one production queue, one live action surface, and one activity history.
            </p>
            <Link href="/accounts/new" className="mt-7 inline-flex">
              <Button variant="primary" icon={<PlusCircle className="h-4 w-4" />}>
                Link your account
              </Button>
            </Link>
          </div>
        </section>

        <Card>
          <CardContent className="flex flex-col items-center justify-center py-14 text-center">
            <Fingerprint className="h-8 w-8 text-accent" />
            <p className="mt-4 text-sm font-semibold text-foreground">No account linked yet</p>
            <p className="mt-2 max-w-md text-xs leading-6 text-muted-foreground">
              Link one Warpath account to unlock the Individual dashboard.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (rows.length > 1) {
    return (
      <div className="space-y-5 sm:space-y-7">
        <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8 lg:p-10">
          <div className="relative z-10 max-w-3xl">
            <span className="command-eyebrow">
              <span className="command-dot text-info" />
              Alliance workspace detected
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.055em] text-foreground sm:text-5xl">
              This workspace has multiple accounts.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              The Individual dashboard is intentionally designed for one account. Your current workspace has {rows.length}, so the Alliance dashboard is the correct multi-account control surface.
            </p>
            <Link href="/alliance" className="mt-7 inline-flex">
              <Button variant="primary" icon={<Users className="h-4 w-4" />}>
                Open Alliance dashboard
              </Button>
            </Link>
          </div>
        </section>

        <Card>
          <CardHeader title="Why the dashboards are separate" />
          <CardContent className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-accent/20 bg-accent/5 p-4">
              <Gauge className="h-4 w-4 text-accent" />
              <p className="mt-3 text-sm font-semibold text-foreground">Individual</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Focused one-account cockpit with direct production, actions, and account activity.</p>
            </div>
            <div className="rounded-xl border border-info/20 bg-info/5 p-4">
              <Users className="h-4 w-4 text-info" />
              <p className="mt-3 text-sm font-semibold text-foreground">Alliance</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">Fleet-wide visibility for multiple accounts, operations, and aggregate activity.</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const row = rows[0];
  const account = row.account;
  const live = row.status?.live ?? null;
  const connected = live?.state === 'connected';

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] px-5 py-6 sm:px-7 sm:py-8 lg:px-9 lg:py-9">
        <div className="scan-line" />
        <div className="relative z-10 flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0 max-w-3xl">
            <span className="command-eyebrow">
              <span className="command-dot live-dot text-success" />
              Individual plan · 1 account
            </span>
            <div className="mt-4 flex flex-wrap items-center gap-3">
              <h1 className="truncate text-3xl font-semibold tracking-[-0.055em] text-foreground sm:text-4xl lg:text-[2.8rem]">
                {account.label}
              </h1>
              <StatusBadge state={live?.state} />
            </div>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-[15px]">
              Your personal command cockpit for connection state, production, active operations, direct controls, and account activity.
            </p>

            <div className="mt-5 flex flex-wrap gap-2">
              <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                <Fingerprint className="h-3.5 w-3.5 text-accent" />
                UID {account.app_uid}
              </span>
              <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
                <Wifi className="h-3.5 w-3.5 text-success" />
                {connected ? 'Live connection' : 'Not connected'}
              </span>
              <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
                <ShieldCheck className="h-3.5 w-3.5 text-info" />
                Owner-bound identity
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <ConnectionControls accountId={account.id} liveState={live?.state} size="md" />
            <Link href={`/accounts/${account.id}`}>
              <Button variant="outline" icon={<ArrowRight className="h-4 w-4" />}>
                Full account detail
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <AccountOverviewStats accountId={account.id} connected={connected} liveState={live?.state} />

      <ProductionPanel accountId={account.id} connected={connected} />

      <ActiveActionsPanel accountId={account.id} connected={connected} excludeProduction />

      <section className="space-y-3">
        <div className="flex items-center gap-3">
          <span className="command-eyebrow"><Sparkles className="h-3.5 w-3.5" /> Individual command deck</span>
          <div className="h-px flex-1 bg-border/70" />
        </div>
        <ActionsPanel accountId={account.id} connected={connected} />
        <ConquestGuardControl accountId={account.id} connected={connected} />
      </section>

      <ActivityTimeline accountId={account.id} />

      <div className="premium-panel flex flex-col gap-4 rounded-2xl p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-foreground">Managing more than one account?</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">
            Alliance is the multi-account dashboard for fleet-wide visibility and coordination.
          </p>
        </div>
        <Link href="/alliance">
          <Button variant="outline" icon={<Users className="h-4 w-4" />}>
            View Alliance plan
          </Button>
        </Link>
      </div>
    </div>
  );
}
