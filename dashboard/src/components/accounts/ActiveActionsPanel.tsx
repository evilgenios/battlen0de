'use client';

import { useEffect, useState } from 'react';
import { Compass, Package, Shield, Truck } from 'lucide-react';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useActiveActions } from '@/lib/hooks/useIntel';
import { calculateProgress, formatCountdown } from '@/lib/utils/format';
import { ProgressBar } from '@/components/ui/ProgressBar';
import type { ActiveActionInfo } from '@/lib/api/types';

const VEHICLE_TYPES = new Set([
  'vehicle_traveling', 'vehicle_gathering', 'vehicle_returning',
  'vehicle_repairing', 'vehicle_building', 'vehicle_demolishing', 'vehicle_delivering',
]);

// A distinct accent per category — purely visual grouping, not a claim
// about server state. Kept subtle (background tint only) rather than
// loud, per-category color blocking.
const CATEGORY_TINT: Record<string, string> = {
  vehicle: 'bg-sky-500/10 text-sky-500',
  production: 'bg-amber-500/10 text-amber-500',
  officer_task: 'bg-violet-500/10 text-violet-500',
  conquest_guard: 'bg-emerald-500/10 text-emerald-500',
};

function categoryOf(activityType: string): string {
  if (VEHICLE_TYPES.has(activityType)) return 'vehicle';
  if (activityType in CATEGORY_TINT) return activityType;
  return 'vehicle';
}

// Renders the element directly (rather than returning a component
// reference to use as <Icon/>) so this isn't mistaken for defining a new
// component on every render.
function activityIcon(activityType: string) {
  const className = 'h-4 w-4';
  if (VEHICLE_TYPES.has(activityType)) return <Truck className={className} />;
  if (activityType === 'production') return <Package className={className} />;
  if (activityType === 'conquest_guard') return <Shield className={className} />;
  return <Compass className={className} />;
}

function titleFor(activity: ActiveActionInfo): string {
  switch (activity.activity_type) {
    case 'vehicle_traveling': return 'Vehicle Traveling';
    case 'vehicle_gathering': return 'Resource Gathering';
    case 'vehicle_returning': return 'Vehicle Returning';
    case 'vehicle_repairing': return 'Vehicle Repairing';
    case 'vehicle_building': return 'Vehicle Building';
    case 'vehicle_demolishing': return 'Vehicle Demolishing';
    case 'vehicle_delivering': return 'Delivering Resources';
    case 'production': return 'Production';
    case 'officer_task': return 'Officer Task';
    case 'conquest_guard': return 'Conquest Guard';
    default: return activity.activity_type;
  }
}

function toneFor(activity: ActiveActionInfo): BadgeTone {
  if (activity.activity_type === 'conquest_guard') {
    return activity.status === 'exit_pending' ? 'warning' : 'success';
  }
  if (activity.status === 'finished' || activity.status === 'Ready') return 'success';
  return 'info';
}

/** Every value rendered here comes straight from ActiveActionInfo — no
 * value is invented client-side. The only thing that ticks locally is the
 * countdown string's re-render (every second), which just re-derives
 * "time until this real end_time" from Date.now(); the underlying
 * end_time never changes except when the backend sends a fresher one. */
function ActivityCard({ activity }: { activity: ActiveActionInfo }) {
  const [, forceTick] = useState(0);

  useEffect(() => {
    if (!activity.end_time) return;
    const interval = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(interval);
  }, [activity.end_time]);

  const identifier =
    activity.vehicle_id != null ? `Vehicle #${activity.vehicle_id}` :
    activity.building_id != null ? `Building #${activity.building_id}` :
    activity.task_id != null ? `Task #${activity.task_id}` :
    null;

  const progress = calculateProgress(activity.start_time, activity.end_time);
  const category = categoryOf(activity.activity_type);

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-surface px-4 py-3 sm:flex-row sm:items-start">
      <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${CATEGORY_TINT[category]}`}>
        {activityIcon(activity.activity_type)}
      </div>
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-sm font-semibold uppercase tracking-wide text-foreground">{titleFor(activity)}</p>
          <Badge tone={toneFor(activity)}>{activity.status}</Badge>
        </div>
        {identifier && <p className="text-sm text-foreground">{identifier}</p>}
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {activity.mine_id != null && <span>Mine #{activity.mine_id}</span>}
          {activity.item_type_id && <span className="capitalize">{activity.item_type_id}</span>}
          {activity.quantity != null && <span>Qty {activity.quantity.toLocaleString()}</span>}
          {activity.map_id != null && <span>Map {activity.map_id}</span>}
          {activity.x != null && activity.y != null && <span>Source ({activity.x}, {activity.y})</span>}
          {activity.target_x != null && activity.target_y != null && (
            <span>Target ({activity.target_x}, {activity.target_y})</span>
          )}
          {activity.task_status != null && <span>Raw status {activity.task_status}</span>}
          {activity.detail && <span>{activity.detail}</span>}
        </div>
        {progress != null && <ProgressBar value={progress} className="mt-1" />}
      </div>
      {activity.end_time != null && (
        <div className="shrink-0 text-right">
          <p className="text-xs text-muted-foreground">ETA</p>
          <p className="font-mono text-sm font-medium text-foreground">{formatCountdown(activity.end_time)}</p>
        </div>
      )}
    </div>
  );
}

const DEFAULT_VISIBLE_COUNT = 8;

type CategoryFilter = 'all' | 'vehicle' | 'production' | 'officer_task' | 'conquest_guard';

const CATEGORY_TABS: { value: CategoryFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'vehicle', label: 'Vehicles' },
  { value: 'production', label: 'Production' },
  { value: 'officer_task', label: 'Officer' },
  { value: 'conquest_guard', label: 'Conquest' },
];

/** Ticks once a second purely to re-render an already-computed relative
 * time string ("Synced 4s ago") — Date.now() is read here, in an effect
 * callback, never during render itself. */
function useNow(intervalMs: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(interval);
  }, [intervalMs]);
  return now;
}

export function ActiveActionsPanel({ accountId, connected, excludeProduction = false }: { accountId: string; connected: boolean; excludeProduction?: boolean }) {
  const { activities, error, isLoading, lastSyncedAt, refresh } = useActiveActions(accountId, connected);
  const [showAll, setShowAll] = useState(false);
  const [filter, setFilter] = useState<CategoryFilter>('all');
  const now = useNow(1000);
  const displayActivities = excludeProduction ? activities.filter((a) => a.activity_type !== 'production') : activities;

  const filtered = filter === 'all' ? displayActivities : displayActivities.filter((a) => categoryOf(a.activity_type) === filter);
  // A single production building can queue many cells (a real account's
  // building #108 had 20+) — soonest-first, capped by default on the "All"
  // tab so it doesn't drown out everything else. Selecting a specific
  // category (e.g. clicking "Production" to see all 300+ queued cells) is
  // an explicit ask to see everything, so that cap doesn't apply there.
  const sorted = [...filtered].sort((a, b) => (a.end_time ?? Infinity) - (b.end_time ?? Infinity));
  const capApplies = filter === 'all' && !showAll;
  const visible = capApplies ? sorted.slice(0, DEFAULT_VISIBLE_COUNT) : sorted;
  const hiddenCount = sorted.length - visible.length;

  return (
    <Card>
      <CardHeader
        title="Active Actions"
        description={excludeProduction ? "Confirmed non-production activity. Production queues are grouped in the dedicated Production bar above." : "What this account is actually doing right now, per confirmed server state — not a request-sent indicator."}
        action={
          connected && lastSyncedAt ? (
            <p className="text-xs text-muted-foreground">Synced {Math.max(0, Math.round((now - lastSyncedAt) / 1000))}s ago</p>
          ) : undefined
        }
      />
      {connected && displayActivities.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-border px-5 pb-3">
          {CATEGORY_TABS.filter(({ value }) => !(excludeProduction && value === 'production')).map(({ value, label }) => (
            <button
              key={value}
              type="button"
              onClick={() => setFilter(value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                filter === value ? 'bg-accent/15 text-accent' : 'text-muted-foreground hover:bg-surface-muted hover:text-foreground'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <CardContent>
        {!connected ? (
          <EmptyState icon={Compass} title="Not connected" description="Connect the account to see live operations." />
        ) : error ? (
          <ErrorState error={error} onRetry={() => refresh()} title="Could not load active actions" />
        ) : isLoading && displayActivities.length === 0 ? (
          <div className="space-y-2">
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        ) : displayActivities.length === 0 ? (
          <EmptyState icon={Compass} title="No activity in progress" description="Nothing confirmed as active right now — try Refresh." />
        ) : filtered.length === 0 ? (
          <EmptyState icon={Compass} title="Nothing in this category" description="No confirmed activity of this type right now." />
        ) : (
          <div className="space-y-2">
            {filter !== 'all' && (
              <p className="pb-1 text-xs text-muted-foreground">{sorted.length} item{sorted.length === 1 ? '' : 's'}</p>
            )}
            {visible.map((activity, index) => {
              // A building can have multiple queued production lines, so
              // building_id alone collided (every cell for building #108
              // rendered with the same key — confirmed live via a real
              // account's production queue). line_id plus the index as a
              // final tiebreaker keeps every card's key unique.
              const key = [
                activity.activity_type, activity.building_id, activity.line_id,
                activity.vehicle_id, activity.task_id, index,
              ].filter((part) => part !== null && part !== undefined).join('-');
              return <ActivityCard key={key} activity={activity} />;
            })}
            {hiddenCount > 0 && (
              <button
                type="button"
                onClick={() => setShowAll(true)}
                className="w-full rounded-lg border border-dashed border-border py-2 text-xs text-muted-foreground hover:text-foreground"
              >
                Show {hiddenCount} more
              </button>
            )}
            {filter === 'all' && showAll && sorted.length > DEFAULT_VISIBLE_COUNT && (
              <button
                type="button"
                onClick={() => setShowAll(false)}
                className="w-full rounded-lg border border-dashed border-border py-2 text-xs text-muted-foreground hover:text-foreground"
              >
                Show less
              </button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
