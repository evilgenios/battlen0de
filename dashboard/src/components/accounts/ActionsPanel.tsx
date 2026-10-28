'use client';

import { useState } from 'react';
import {
  ChevronDown,
  Compass,
  Crosshair,
  HeartPulse,
  Loader2,
  Package,
  RadioTower,
  RefreshCw,
  RotateCcw,
  Truck,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useAccountActions, type AccountActionName } from '@/lib/hooks/useAccountActions';
import { MassDeployControl } from '@/components/accounts/MassDeployControl';
import type { FarmResource } from '@/lib/api/types';

const fieldClass =
  'h-10 w-full rounded-xl border border-border/80 bg-surface/55 px-3 text-sm text-foreground outline-none transition focus:border-accent/45 focus:ring-4 focus:ring-accent/10';

function QuickCommand({
  icon: Icon,
  title,
  description,
  disabled,
  loading,
  tone = 'accent',
  onClick,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  disabled: boolean;
  loading: boolean;
  tone?: 'accent' | 'info' | 'success' | 'warning';
  onClick: () => void;
}) {
  const toneClass = {
    accent: 'text-accent border-accent/20 bg-accent/8 group-hover:border-accent/35',
    info: 'text-info border-info/20 bg-info/8 group-hover:border-info/35',
    success: 'text-success border-success/20 bg-success/8 group-hover:border-success/35',
    warning: 'text-warning border-warning/20 bg-warning/8 group-hover:border-warning/35',
  }[tone];

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="group premium-lift relative overflow-hidden rounded-2xl border border-border/75 bg-surface-muted/28 p-4 text-left disabled:cursor-not-allowed disabled:opacity-45 disabled:transform-none"
    >
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent opacity-0 transition group-hover:opacity-100" />
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl border ${toneClass}`}>
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Icon className="h-4 w-4" />}
      </div>
      <p className="mt-4 text-sm font-semibold tracking-[-0.02em] text-foreground">{title}</p>
      <p className="mt-1.5 text-[11px] leading-5 text-muted-foreground">{description}</p>
      <span className="mt-4 inline-flex items-center gap-1 font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground transition group-hover:text-foreground">
        {loading ? 'Command pending' : 'Execute'}
        <span aria-hidden>→</span>
      </span>
    </button>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-3">
      <span className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-muted-foreground">{children}</span>
      <div className="h-px flex-1 bg-border/70" />
    </div>
  );
}

function pending(actionsPending: AccountActionName | null, action: AccountActionName) {
  return actionsPending === action;
}

export function ActionsPanel({ accountId, connected }: { accountId: string; connected: boolean }) {
  const actions = useAccountActions(accountId);
  const [resource, setResource] = useState<FarmResource>('gold');
  const [level, setLevel] = useState('1');
  const [vehicleId, setVehicleId] = useState('');
  const [planeId, setPlaneId] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <div className="premium-panel overflow-hidden rounded-2xl">
      <div className="border-b border-border/75 px-5 py-4 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="command-eyebrow"><span className="command-dot text-accent" /> Command console</p>
            <h2 className="mt-2 text-lg font-semibold tracking-[-0.03em] text-foreground">Account controls</h2>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              {connected ? 'Direct commands for this connected account.' : 'Connect the account to activate command controls.'}
            </p>
          </div>
          <span className={`data-chip rounded-full px-3 py-1.5 font-mono text-[9px] uppercase tracking-[0.12em] ${connected ? 'text-success' : 'text-muted-foreground'}`}>
            {connected ? '● command link live' : '○ offline'}
          </span>
        </div>
      </div>

      <div className="space-y-6 p-4 sm:p-5">
        <div>
          <SectionLabel>Quick commands</SectionLabel>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <QuickCommand
              icon={Package}
              title="Collect Production"
              description="Collect completed resources from your Production Buildings."
              disabled={!connected}
              loading={pending(actions.pending, 'collect')}
              tone="warning"
              onClick={actions.collect}
            />
            <QuickCommand
              icon={Crosshair}
              title="Map Scan"
              description="Scan the World Map around your current Base."
              disabled={!connected}
              loading={pending(actions.pending, 'scan')}
              tone="info"
              onClick={() => actions.scan()}
            />
            <QuickCommand
              icon={RefreshCw}
              title="Refresh Base Intel"
              description="Request fresh Base, movement and account state."
              disabled={!connected}
              loading={pending(actions.pending, 'refresh')}
              onClick={() => actions.refresh()}
            />
            <QuickCommand
              icon={HeartPulse}
              title="Ping Session"
              description="Send a manual heartbeat through the live Warpath session."
              disabled={!connected}
              loading={pending(actions.pending, 'heartbeat')}
              tone="success"
              onClick={() => actions.heartbeat()}
            />
          </div>
        </div>

        <div>
          <SectionLabel>Deployment</SectionLabel>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-border/75 bg-surface-muted/24 p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-warning/20 bg-warning/8 text-warning">
                  <Truck className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">Collection Convoy</p>
                  <p className="mt-1 text-[11px] leading-5 text-muted-foreground">Choose a resource target and level, then dispatch an idle Collection Convoy.</p>
                </div>
              </div>
              <div className="mt-4 grid grid-cols-[1fr_88px_auto] gap-2">
                <select
                  className={fieldClass}
                  value={resource}
                  onChange={(e) => setResource(e.target.value as FarmResource)}
                  aria-label="Resource"
                >
                  <option value="gold">Military Funds</option>
                  <option value="metal">Steel</option>
                  <option value="oil">Crude Oil</option>
                </select>
                <input
                  className={fieldClass}
                  type="number"
                  min={1}
                  max={10}
                  value={level}
                  onChange={(e) => setLevel(e.target.value)}
                  aria-label="Mine level"
                />
                <Button
                  variant="primary"
                  disabled={!connected}
                  loading={pending(actions.pending, 'farm')}
                  onClick={() => actions.farm({ resource, level: Number(level) || 1 })}
                >
                  Deploy
                </Button>
              </div>
            </div>

            <div className="rounded-2xl border border-border/75 bg-surface-muted/24 p-4">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-info/20 bg-info/8 text-info">
                  <Compass className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-sm font-semibold text-foreground">Scout Plane</p>
                  <p className="mt-1 text-[11px] leading-5 text-muted-foreground">Dispatch an idle Scout Plane from your Airport using its Plane ID.</p>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <input
                  className={fieldClass}
                  type="number"
                  placeholder="Plane ID"
                  value={planeId}
                  onChange={(e) => setPlaneId(e.target.value)}
                  aria-label="Plane ID"
                />
                <Button
                  variant="primary"
                  disabled={!connected || !planeId}
                  loading={pending(actions.pending, 'scout')}
                  onClick={() => actions.scout({ plane_id: Number(planeId) })}
                >
                  Dispatch
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div>
          <SectionLabel>Convoy control</SectionLabel>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-border/75 bg-surface-muted/24 p-4">
              <div className="flex items-center gap-3">
                <RadioTower className="h-4 w-4 text-accent" />
                <div>
                  <p className="text-sm font-semibold text-foreground">Recall Convoy</p>
                  <p className="text-[11px] text-muted-foreground">Recall one active Collection Convoy by Vehicle ID.</p>
                </div>
              </div>
              <div className="mt-4 flex gap-2">
                <input
                  className={fieldClass}
                  type="number"
                  placeholder="Vehicle ID"
                  value={vehicleId}
                  onChange={(e) => setVehicleId(e.target.value)}
                  aria-label="Vehicle ID"
                />
                <Button
                  variant="outline"
                  disabled={!connected || !vehicleId}
                  loading={pending(actions.pending, 'recall')}
                  onClick={() => actions.recall({ vehicle_id: Number(vehicleId) })}
                >
                  Recall
                </Button>
              </div>
            </div>

            <button
              type="button"
              disabled={!connected}
              onClick={() => actions.recallAll()}
              className="group premium-lift flex min-h-[118px] items-center gap-4 rounded-2xl border border-danger/15 bg-danger/[0.035] p-4 text-left disabled:cursor-not-allowed disabled:opacity-45 disabled:transform-none"
            >
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-danger/20 bg-danger/8 text-danger">
                {pending(actions.pending, 'recallAll') ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
              </span>
              <span>
                <span className="block text-sm font-semibold text-foreground">Recall all Convoys</span>
                <span className="mt-1 block text-[11px] leading-5 text-muted-foreground">Recall every Collection Convoy currently traveling or gathering.</span>
                <span className="mt-2 block font-mono text-[9px] uppercase tracking-[0.12em] text-danger">all convoys →</span>
              </span>
            </button>
          </div>
        </div>

        <div>
          <button
            type="button"
            onClick={() => setAdvancedOpen((value) => !value)}
            className="flex w-full items-center justify-between rounded-xl border border-border/70 bg-surface-muted/20 px-4 py-3 text-left transition hover:border-accent/25 hover:bg-accent/[0.035]"
            aria-expanded={advancedOpen}
          >
            <div>
              <p className="text-xs font-semibold text-foreground">Advanced controls</p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">Advanced multi-dispatch tools and dry-run workflows.</p>
            </div>
            <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${advancedOpen ? 'rotate-180 text-accent' : ''}`} />
          </button>
          {advancedOpen && (
            <div className="mt-2 rounded-xl border border-border/70 bg-surface/25 px-4 motion-safe:animate-[landing-rise_.25s_ease-out]">
              <MassDeployControl accountId={accountId} connected={connected} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
