'use client';

import { Compass, Package, Radio, Shield, Truck, Users, Wifi } from 'lucide-react';
import { useActiveActions, useArmies, useConquestGuard } from '@/lib/hooks/useIntel';
import type { SessionState } from '@/lib/api/types';

const VEHICLE_TYPES = new Set([
  'vehicle_traveling', 'vehicle_gathering', 'vehicle_returning',
  'vehicle_repairing', 'vehicle_building', 'vehicle_demolishing', 'vehicle_delivering',
]);

function StatTile({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-muted">
        <Icon className="h-4 w-4 text-muted-foreground" />
      </div>
      <div className="min-w-0">
        <p className="truncate text-sm font-semibold text-foreground">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
      </div>
    </div>
  );
}

/** Seven compact counts, all derived from data the page already fetches
 * elsewhere (Active Actions, Armies, Conquest Guard) — no new protocol
 * calls, just a glanceable summary above the full sections below. */
export function AccountOverviewStats({ accountId, connected, liveState }: { accountId: string; connected: boolean; liveState: SessionState | null | undefined }) {
  const { activities } = useActiveActions(accountId, connected);
  const { armies } = useArmies(accountId, connected);
  const { status: conquestGuard } = useConquestGuard(accountId);

  const vehicleCount = activities.filter((a) => VEHICLE_TYPES.has(a.activity_type)).length;
  const productionCount = activities.filter((a) => a.activity_type === 'production').length;
  const officerCount = activities.filter((a) => a.activity_type === 'officer_task').length;
  const agCount = new Set(armies.filter((a) => a.group_unique_id).map((a) => a.group_unique_id)).size;
  const connectionLabel = liveState ? liveState.charAt(0).toUpperCase() + liveState.slice(1) : 'Never connected';

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
      <StatTile icon={Radio} label="Active actions" value={activities.length} />
      <StatTile icon={Truck} label="Vehicles" value={vehicleCount} />
      <StatTile icon={Package} label="Production" value={productionCount} />
      <StatTile icon={Compass} label="Officer tasks" value={officerCount} />
      <StatTile icon={Users} label="In Army Groups" value={agCount} />
      <StatTile icon={Shield} label="Conquest Guard" value={conquestGuard?.enabled ? 'Armed' : 'Off'} />
      <StatTile icon={Wifi} label="Connection" value={connectionLabel} />
    </div>
  );
}
