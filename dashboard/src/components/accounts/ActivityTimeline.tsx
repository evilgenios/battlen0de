'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonRows } from '@/components/ui/Skeleton';
import { CustomerActivityList } from '@/components/events/CustomerActivityList';
import { useAccountEvents } from '@/lib/hooks/useAccountEvents';
import { classifyEvent, EVENT_CATEGORIES, type EventCategory } from '@/lib/utils/eventCategory';
import { cn } from '@/lib/utils/cn';

/** Real confirmed events only — the same account_events rows the backend
 * already writes for connect/disconnect/collect/farm/recall/AG/conquest
 * actions (see app/api/*.py). This never synthesizes a timeline entry;
 * filtering just buckets the existing rows by classifyEvent(). */
export function ActivityTimeline({ accountId }: { accountId: string }) {
  const { events, isLoading, error, refresh } = useAccountEvents(accountId, 50);
  const [filter, setFilter] = useState<EventCategory | 'all'>('all');

  const filtered = filter === 'all' ? events : events?.filter((e) => classifyEvent(e) === filter);

  return (
    <Card>
      <CardHeader title="Base Activity" description="Important confirmed activity for this Base, translated into player-friendly BattleN0de language." />
      <div className="flex flex-wrap gap-1.5 border-b border-border px-5 pb-3">
        {EVENT_CATEGORIES.map(({ value, label }) => (
          <button
            key={value}
            type="button"
            onClick={() => setFilter(value)}
            className={cn(
              'rounded-full px-3 py-1 text-xs font-medium transition-colors',
              filter === value
                ? 'bg-accent/15 text-accent'
                : 'text-muted-foreground hover:bg-surface-muted hover:text-foreground',
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <CardContent className="p-0">
        {isLoading && !events ? (
          <div className="p-5">
            <SkeletonRows rows={4} />
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={() => refresh()} title="Could not load events" />
        ) : (
          <CustomerActivityList rows={(filtered ?? []).map((event) => ({ event }))} />
        )}
      </CardContent>
    </Card>
  );
}
