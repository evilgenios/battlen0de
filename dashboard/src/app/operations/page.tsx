'use client';

import Link from 'next/link';
import { Activity, ArrowUpRight, RadioTower, Radar, Shield, Zap } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonRows } from '@/components/ui/Skeleton';
import { StatusBadge } from '@/components/accounts/StatusBadge';
import { countByCategory, nextEventEndTime, useOperationsOverview, type OperationsRow } from '@/lib/hooks/useOperationsOverview';
import { formatCountdown } from '@/lib/utils/format';

function OperationsRowCard({ row }: { row: OperationsRow }) {
  const { account, status, summary, activeActions, conquestGuard } = row;
  const { vehicles, production, officerTasks } = countByCategory(activeActions);
  const nextEnd = nextEventEndTime(activeActions);
  const armed = conquestGuard?.enabled;

  return (
    <Link href={`/accounts/${account.id}`} className="block">
      <div className="premium-lift group relative overflow-hidden rounded-2xl border border-border/75 bg-surface-muted/30 p-4 sm:p-5">
        <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-accent via-info to-transparent opacity-70" />
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="truncate text-sm font-semibold text-foreground">{account.label}</p>
              <StatusBadge state={status?.live?.state} />
              {armed && (
                <Badge tone="success" dot>
                  <Shield className="h-3 w-3" /> Guard armed
                </Badge>
              )}
            </div>
            <p className="mt-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
              {summary?.uid != null ? `UID ${summary.uid}` : 'UID unknown'} · {activeActions.length} active action{activeActions.length === 1 ? '' : 's'}
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 xl:min-w-[30rem]">
            <Stat label="Vehicles" value={vehicles} />
            <Stat label="Production" value={production} />
            <Stat label="Officer" value={officerTasks} />
            <div className="data-chip rounded-xl px-3 py-2.5">
              <p className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">Next event</p>
              <p className="mt-1 font-mono text-sm font-semibold text-foreground">{formatCountdown(nextEnd)}</p>
            </div>
          </div>

          <ArrowUpRight className="hidden h-4 w-4 shrink-0 text-muted-foreground transition group-hover:text-accent xl:block" />
        </div>
      </div>
    </Link>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="data-chip rounded-xl px-3 py-2.5">
      <p className="text-[10px] uppercase tracking-[0.1em] text-muted-foreground">{label}</p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

export default function OperationsPage() {
  const { rows, isLoading, error, refresh } = useOperationsOverview();
  const totalActions = rows?.reduce((sum, row) => sum + row.activeActions.length, 0) ?? 0;
  const connected = rows?.filter((row) => row.status?.live?.state === 'connected').length ?? 0;
  const guards = rows?.filter((row) => row.conquestGuard?.enabled).length ?? 0;

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="command-eyebrow"><span className="command-dot text-info" /> Operations center</span>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">Live operational picture</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Every linked account, active action, and known event window in one dense command view.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2 sm:min-w-[24rem]">
            <Stat label="Connected" value={connected} />
            <Stat label="Actions" value={totalActions} />
            <Stat label="Guards" value={guards} />
          </div>
        </div>
      </section>

      <Card>
        <CardHeader
          title="Operational accounts"
          description="Select an account to open its full active-actions view."
          action={<Badge tone="neutral">{rows?.length ?? 0} linked</Badge>}
        />
        <CardContent className="p-0">
          {isLoading && !rows ? (
            <div className="p-5 sm:p-6"><SkeletonRows rows={4} /></div>
          ) : error ? (
            <ErrorState error={error} onRetry={() => refresh()} title="Could not load operations overview" />
          ) : !rows || rows.length === 0 ? (
            <EmptyState icon={Radar} title="No accounts yet" description="Link a Warpath account to see it here." />
          ) : (
            <div className="space-y-3 p-4 sm:p-5">
              {rows.map((row) => <OperationsRowCard key={row.account.id} row={row} />)}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { icon: RadioTower, title: 'Live telemetry', body: 'Operational state refreshes automatically from existing account endpoints.' },
          { icon: Zap, title: 'Action awareness', body: 'See active vehicles, production, officer tasks, and known timing windows.' },
          { icon: Activity, title: 'No hidden automation', body: 'Phase 6 remains observation-first and fail-closed for game-changing actions.' },
        ].map(({ icon: Icon, title, body }) => (
          <div key={title} className="premium-panel rounded-2xl p-5">
            <Icon className="h-4 w-4 text-accent" />
            <p className="mt-4 text-sm font-semibold text-foreground">{title}</p>
            <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{body}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
