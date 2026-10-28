'use client';

import { Activity, DatabaseZap, RadioTower } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonRows } from '@/components/ui/Skeleton';
import { CustomerActivityList } from '@/components/events/CustomerActivityList';
import { useAllEvents } from '@/lib/hooks/useAllEvents';

export default function EventsPage() {
  const { events, isLoading, error, refresh } = useAllEvents(25, 150);

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10">
          <span className="command-eyebrow"><span className="command-dot text-info" /> Commander activity</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">Activity</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            A simple timeline of the things that matter: Base connections, commands, linked accounts and Conquest Guard.
          </p>
        </div>
        <div className="relative z-10 mt-7 flex flex-wrap gap-2">
          <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
            <RadioTower className="h-3.5 w-3.5 text-success" /> live refresh
          </span>
          <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground">
            <DatabaseZap className="h-3.5 w-3.5 text-accent" /> persisted event history
          </span>
        </div>
      </section>

      <Card>
        <CardHeader
          title="Your BattleN0de activity"
          description="Most recent first. Technical security metadata is kept in the administrator audit center instead of cluttering this view."
          action={<Badge tone="neutral">{events?.length ?? 0} loaded</Badge>}
        />
        <CardContent className="p-0">
          {isLoading && !events ? (
            <div className="p-5 sm:p-6"><SkeletonRows rows={8} /></div>
          ) : error ? (
            <ErrorState error={error} onRetry={() => refresh()} title="Could not load events" />
          ) : (
            <CustomerActivityList rows={events ?? []} />
          )}
        </CardContent>
      </Card>

      <div className="premium-panel flex items-start gap-3 rounded-2xl p-4 text-xs leading-5 text-muted-foreground">
        <Activity className="mt-0.5 h-4 w-4 shrink-0 text-accent" />
        This view is intentionally customer-friendly. BattleN0de never shows saved game credentials or raw protocol payloads here.
      </div>
    </div>
  );
}
