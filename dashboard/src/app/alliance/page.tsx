'use client';

import Link from 'next/link';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  PlusCircle,
  Radar,
  ShieldCheck,
  Users,
  Wifi,
  WifiOff,
  Zap,
} from 'lucide-react';
import { StatCard } from '@/components/dashboard/StatCard';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { EventsTable } from '@/components/events/EventsTable';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonRows } from '@/components/ui/Skeleton';
import { useAccountsOverview, summarizeOverview } from '@/lib/hooks/useAccountsOverview';
import { useAllEvents } from '@/lib/hooks/useAllEvents';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

export default function AllianceDashboardPage() {
  const { user } = useAuthSession();
  const { rows, isLoading, error, refresh } = useAccountsOverview();
  const { events, isLoading: eventsLoading, error: eventsError } = useAllEvents(10, 8);
  const stats = summarizeOverview(rows);
  const connectionRate = stats.total ? Math.round((stats.connected / stats.total) * 100) : 0;

  if (user?.plan === 'individual') {
    return (
      <div className="space-y-5 sm:space-y-7">
        <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8 lg:p-10">
          <div className="scan-line" />
          <div className="relative z-10 max-w-3xl">
            <span className="command-eyebrow">
              <span className="command-dot text-info" />
              Alliance plan
            </span>
            <h1 className="mt-4 text-3xl font-semibold tracking-[-0.055em] text-foreground sm:text-5xl">
              Multi-account control is an Alliance capability.
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-muted-foreground">
              Your current server policy is Individual, which allows one linked Warpath account. Alliance raises the account limit and unlocks the fleet-wide control surface without changing your existing account identity.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/dashboard">
                <Button variant="outline">Back to Individual</Button>
              </Link>
              <Link href="/#plans">
                <Button variant="primary" icon={<Users className="h-4 w-4" />}>View Alliance plan</Button>
              </Link>
            </div>
          </div>
        </section>

        <Card>
          <CardHeader title="Current entitlement" description="Limits are enforced by the backend, not only hidden in the interface." />
          <CardContent className="grid gap-3 sm:grid-cols-3">
            <div className="data-chip rounded-xl p-4">
              <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Plan</p>
              <p className="mt-2 text-sm font-semibold text-foreground">Individual</p>
            </div>
            <div className="data-chip rounded-xl p-4">
              <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Linked accounts</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{user.max_accounts ?? 1}</p>
            </div>
            <div className="data-chip rounded-xl p-4">
              <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Active accounts</p>
              <p className="mt-2 text-sm font-semibold text-foreground">{user.max_active_accounts ?? 1}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] px-5 py-6 sm:px-7 sm:py-8 lg:px-9 lg:py-9">
        <div className="scan-line" />
        <div className="relative z-10 flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <span className="command-eyebrow">
              <span className="command-dot live-dot text-success" />
              Alliance plan · multi-account
            </span>
            <h1 className="mt-4 max-w-2xl text-3xl font-semibold tracking-[-0.055em] text-foreground sm:text-4xl lg:text-[2.8rem] lg:leading-[1.02]">
              Your alliance operation,
              <span className="block bg-gradient-to-r from-accent via-info to-foreground bg-clip-text text-transparent">
                one fleet-wide control surface.
              </span>
            </h1>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-[15px]">
              Monitor multiple linked accounts, inspect fleet-wide operations, review activity across the workspace, and coordinate from one command surface.
            </p>
          </div>

          <div className="flex flex-wrap gap-3">
            <Link href="/operations">
              <Button variant="outline" icon={<Radar className="h-4 w-4" />}>
                Open operations
              </Button>
            </Link>
            <Link href="/accounts/new">
              <Button variant="primary" icon={<PlusCircle className="h-4 w-4" />}>
                Add account
              </Button>
            </Link>
          </div>
        </div>

        <div className="relative z-10 mt-8 grid gap-3 sm:grid-cols-3">
          <div className="data-chip rounded-xl p-3.5">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Connectivity</span>
              <Wifi className="h-3.5 w-3.5 text-success" />
            </div>
            <p className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">{connectionRate}%</p>
          </div>
          <div className="data-chip rounded-xl p-3.5">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Active nodes</span>
              <Zap className="h-3.5 w-3.5 text-accent" />
            </div>
            <p className="mt-2 text-xl font-semibold tracking-[-0.04em] text-foreground">{stats.connected}</p>
          </div>
          <div className="data-chip rounded-xl p-3.5">
            <div className="flex items-center justify-between gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">Security</span>
              <ShieldCheck className="h-3.5 w-3.5 text-info" />
            </div>
            <p className="mt-2 text-sm font-semibold text-foreground">Session enforced</p>
          </div>
        </div>
      </section>

      {error ? (
        <Card>
          <ErrorState error={error} onRetry={() => refresh()} title="Could not load accounts" />
        </Card>
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
          <StatCard label="Total accounts" value={stats.total} icon={Users} loading={isLoading} />
          <StatCard label="Connected" value={stats.connected} icon={Wifi} tone="success" loading={isLoading} />
          <StatCard label="Disconnected" value={stats.disconnected} icon={WifiOff} tone="neutral" loading={isLoading} />
          <StatCard label="Attention" value={stats.errors} icon={AlertTriangle} tone="danger" loading={isLoading} />
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
        <Card className="h-full">
          <CardHeader title="Alliance shortcuts" description="Fleet-wide routes for multi-account operators." />
          <CardContent className="space-y-3">
            {[
              { href: '/operations', icon: Radar, title: 'Operations center', body: 'Inspect active actions and account state.' },
              { href: '/accounts', icon: Users, title: 'Account fleet', body: 'Manage every linked Warpath identity.' },
              { href: '/events', icon: Activity, title: 'Activity intelligence', body: 'Review the latest system and account events.' },
            ].map(({ href, icon: Icon, title, body }) => (
              <Link
                key={href}
                href={href}
                className="premium-lift group flex items-center gap-4 rounded-xl border border-border/70 bg-surface-muted/35 p-4"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-accent/20 bg-accent/8 text-accent">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-semibold text-foreground">{title}</span>
                  <span className="mt-0.5 block text-xs leading-5 text-muted-foreground">{body}</span>
                </span>
                <ArrowUpRight className="h-4 w-4 text-muted-foreground transition group-hover:text-accent" />
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader
            title="Recent activity"
            description="Latest events across the command surface."
            action={
              <Link href="/events" className="text-xs font-semibold text-accent hover:text-info">
                View all
              </Link>
            }
          />
          <CardContent className="p-0">
            {eventsLoading && !events ? (
              <div className="p-5 sm:p-6">
                <SkeletonRows rows={4} />
              </div>
            ) : eventsError ? (
              <ErrorState error={eventsError} title="Could not load recent events" />
            ) : (
              <EventsTable rows={events ?? []} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
