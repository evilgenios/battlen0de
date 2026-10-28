import Link from 'next/link';
import { EventTypeBadge } from '@/components/events/EventTypeBadge';
import { EmptyState } from '@/components/ui/EmptyState';
import { formatDateTime } from '@/lib/utils/format';
import type { AccountEvent } from '@/lib/api/types';
import { Activity } from 'lucide-react';

export interface EventRow {
  event: AccountEvent;
  accountLabel?: string | null;
}

function summarizeDetail(detail: Record<string, unknown>): string | null {
  const entries = Object.entries(detail).filter(([key]) => key !== 'account_id' && key !== 'detail');
  if (entries.length === 0) return null;
  return entries
    .map(([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`)
    .join(', ')
    .slice(0, 160);
}

export function EventsTable({ rows, showAccount = true }: { rows: EventRow[]; showAccount?: boolean }) {
  if (rows.length === 0) {
    return <EmptyState icon={Activity} title="No events yet" description="Account activity will appear here as it happens." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/80 bg-surface-muted/25 text-left font-mono text-[10px] uppercase tracking-[0.13em] text-muted-foreground">
            <th className="px-5 py-3.5 font-semibold">Timestamp</th>
            {showAccount && <th className="px-5 py-3.5 font-semibold">Account</th>}
            <th className="px-5 py-3.5 font-semibold">Event</th>
            <th className="px-5 py-3.5 font-semibold">Actor</th>
            <th className="px-5 py-3.5 font-semibold">Details</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ event, accountLabel }) => {
            const summary = summarizeDetail(event.detail);
            return (
              <tr key={event.id} className="border-b border-border/70 last:border-0 transition-colors hover:bg-accent/[0.035]">
                <td className="whitespace-nowrap px-5 py-4 font-mono text-[11px] text-muted-foreground">{formatDateTime(event.created_at)}</td>
                {showAccount && (
                  <td className="px-5 py-4">
                    {event.account_id && accountLabel ? (
                      <Link href={`/accounts/${event.account_id}`} className="font-medium text-foreground transition hover:text-accent">{accountLabel}</Link>
                    ) : (
                      <span className="text-muted-foreground italic">deleted account</span>
                    )}
                  </td>
                )}
                <td className="px-5 py-4"><EventTypeBadge eventType={event.event_type} /></td>
                <td className="px-5 py-4 text-xs text-muted-foreground">{event.actor}</td>
                <td className="max-w-[320px] truncate px-5 py-4 text-xs text-muted-foreground" title={summary ?? undefined}>{summary ?? '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
