'use client';

import { useEffect, useState } from 'react';
import { useVehicles } from '@/lib/hooks/useIntel';
import { calculateProgress, formatCountdown } from '@/lib/utils/format';
import { ProgressBar } from '@/components/ui/ProgressBar';

const EMPTY_ROW = <span className="text-muted-foreground">—</span>;

/** Dedicated Vehicles view — every value is a real field already returned
 * by GET /vehicles (see app/schemas/intel.py: VehicleInfo, extended with
 * x/y/start_time/end_time/max_gather_num/target_x/target_y — confirmed via
 * a live protocol capture on 2026-09-15). Progress/ETA are derived purely
 * from start_time/end_time, never invented. */
export function VehiclesSection({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { vehicles, isLoading } = useVehicles(accountId, connected);
  const [, forceTick] = useState(0);

  useEffect(() => {
    const hasTimer = vehicles.some((v) => v.end_time);
    if (!hasTimer) return;
    const interval = setInterval(() => forceTick((n) => n + 1), 1000);
    return () => clearInterval(interval);
  }, [vehicles]);

  if (!connected) return <p className="py-2 text-xs text-muted-foreground">Connect the account to see vehicles.</p>;
  if (isLoading && vehicles.length === 0) return <p className="py-2 text-xs text-muted-foreground">Loading…</p>;
  if (vehicles.length === 0) return <p className="py-2 text-xs text-muted-foreground">No vehicle data yet — use Refresh.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-xs">
        <thead className="text-muted-foreground">
          <tr>
            <th className="pb-1 pr-3">ID</th>
            <th className="pb-1 pr-3">State</th>
            <th className="pb-1 pr-3">Position</th>
            <th className="pb-1 pr-3">Mine</th>
            <th className="pb-1 pr-3">Progress</th>
            <th className="pb-1 pr-3">ETA</th>
            <th className="pb-1">Locked</th>
          </tr>
        </thead>
        <tbody>
          {vehicles.map((v) => {
            const progress = calculateProgress(v.start_time, v.end_time);
            return (
              <tr key={v.id} className="border-t border-border">
                <td className="py-1.5 pr-3 text-foreground">{v.id}</td>
                <td className="py-1.5 pr-3 text-foreground">{v.state_label}</td>
                <td className="py-1.5 pr-3 text-foreground">{v.x || v.y ? `(${v.x}, ${v.y})` : EMPTY_ROW}</td>
                <td className="py-1.5 pr-3 text-foreground">{v.mine_id || EMPTY_ROW}</td>
                <td className="py-1.5 pr-3">
                  {progress != null ? <ProgressBar value={progress} className="w-20" /> : EMPTY_ROW}
                </td>
                <td className="py-1.5 pr-3 font-mono text-foreground">{v.end_time ? formatCountdown(v.end_time) : EMPTY_ROW}</td>
                <td className="py-1.5 text-foreground">{v.is_locked ? 'Yes' : 'No'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
