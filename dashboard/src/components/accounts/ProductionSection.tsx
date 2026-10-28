'use client';

import { useEffect, useState } from 'react';
import { useProduction } from '@/lib/hooks/useIntel';
import { calculateProgress, formatCountdown } from '@/lib/utils/format';
import { ProgressBar } from '@/components/ui/ProgressBar';

/** Dedicated Production view — reads GET /production, the complete,
 * unfiltered picture of every known produce_cell (see
 * app/core/warpath/active_actions.py: list_production_cells). Nothing
 * here invents a production category or field; 'status' is exactly what
 * the backend derived from comparing real timestamps to now. */
export function ProductionSection({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { lines, isLoading } = useProduction(accountId, connected);
  const [, forceTick] = useState(0);

  useEffect(() => {
    const hasTimer = lines.some((l) => l.end_time);
    if (!hasTimer) return;
    const interval = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(interval);
  }, [lines]);

  if (!connected) return <p className="py-2 text-xs text-muted-foreground">Connect the account to see production.</p>;
  if (isLoading && lines.length === 0) return <p className="py-2 text-xs text-muted-foreground">Loading…</p>;
  if (lines.length === 0) return <p className="py-2 text-xs text-muted-foreground">No production data yet — use Refresh.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-left text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="pb-1 pr-3">Building</th>
            <th className="pb-1 pr-3">Line</th>
            <th className="pb-1 pr-3">Item</th>
            <th className="pb-1 pr-3">Quantity</th>
            <th className="pb-1 pr-3">Progress</th>
            <th className="pb-1 pr-3">Status</th>
            <th className="pb-1">ETA</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, index) => {
            const progress = calculateProgress(line.start_time, line.end_time);
            return (
              <tr key={`${line.building_id}-${line.line_id}-${index}`} className="border-t border-border">
                <td className="py-1.5 pr-3 text-foreground">#{line.building_id}</td>
                <td className="py-1.5 pr-3 text-foreground">{line.line_id}</td>
                <td className="py-1.5 pr-3 capitalize text-foreground">{line.item_type_id ?? '—'}</td>
                <td className="py-1.5 pr-3 text-foreground">{line.quantity?.toLocaleString() ?? '—'}</td>
                <td className="py-1.5 pr-3">
                  {progress != null ? <ProgressBar value={progress} className="w-20" /> : '—'}
                </td>
                <td className="py-1.5 pr-3 capitalize text-foreground">{line.status}</td>
                <td className="py-1.5 font-mono text-foreground">{line.end_time ? formatCountdown(line.end_time) : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
