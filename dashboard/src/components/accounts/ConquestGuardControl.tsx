'use client';

import { useState } from 'react';
import { Crosshair, Loader2, ShieldAlert, ShieldCheck, Siren } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { disableConquestGuard, enableConquestGuard } from '@/lib/api/intel';
import { useConquestGuard } from '@/lib/hooks/useIntel';

export function ConquestGuardControl({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { status, refresh } = useConquestGuard(accountId);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const armed = Boolean(status?.enabled);

  async function handleToggle() {
    setPending(true);
    setError(null);
    try {
      if (armed) await disableConquestGuard(accountId);
      else await enableConquestGuard(accountId);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Request failed.');
    } finally {
      setPending(false);
    }
  }

  return (
    <section className={`premium-panel relative overflow-hidden rounded-2xl ${armed ? 'border-success/25 shadow-[0_20px_70px_color-mix(in_srgb,var(--color-success)_8%,transparent)]' : ''}`}>
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent ${armed ? 'via-success' : 'via-info'} to-transparent opacity-70`} />
      <div className="p-5 sm:p-6">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex items-start gap-4">
            <div className={`relative flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border ${armed ? 'border-success/25 bg-success/10 text-success' : 'border-info/20 bg-info/8 text-info'}`}>
              {armed ? <ShieldCheck className="h-6 w-6" /> : <ShieldAlert className="h-6 w-6" />}
              {armed && <span className="absolute inset-[-6px] rounded-[1.15rem] border border-success/10 motion-safe:animate-pulse" />}
            </div>
            <div>
              <p className="command-eyebrow"><span className={`command-dot ${armed ? 'text-success' : 'text-info'}`} /> Protection protocol</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold tracking-[-0.03em] text-foreground">Conquest Guard</h2>
                {armed ? <Badge tone="success" dot>Armed</Badge> : <Badge tone="neutral">Disabled</Badge>}
              </div>
              <p className="mt-2 max-w-lg text-xs leading-5 text-muted-foreground">
                Watches this account for a main-base attack and can leave Theater of Conquest automatically while connected.
              </p>
            </div>
          </div>

          <Button
            variant={armed ? 'danger' : 'primary'}
            disabled={!connected}
            loading={pending}
            icon={pending ? <Loader2 className="h-4 w-4 animate-spin" /> : armed ? <Siren className="h-4 w-4" /> : <ShieldCheck className="h-4 w-4" />}
            onClick={handleToggle}
          >
            {armed ? 'Disarm guard' : 'Arm guard'}
          </Button>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-2 lg:grid-cols-5">
          {[
            ['Connected UID', status?.connected_uid ?? '—'],
            ['Exit pending', status?.in_progress ? 'YES' : 'No'],
            ['Attempts', status?.attempts ?? 0],
            ['Last attack', status?.last_attack ? String(status.last_attack.attacker_uid ?? 'unknown') : '—'],
            ['Last result', status?.last_result ? String(status.last_result.status) : 'Standby'],
          ].map(([label, value], index) => (
            <div key={label} className="data-chip rounded-xl p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-mono text-[8px] uppercase tracking-[0.11em] text-muted-foreground">{label}</p>
                {index === 1 && status?.in_progress && <Crosshair className="h-3 w-3 animate-pulse text-danger" />}
              </div>
              <p className={`mt-2 truncate text-xs font-semibold ${index === 1 && status?.in_progress ? 'text-danger' : 'text-foreground'}`}>{String(value)}</p>
            </div>
          ))}
        </div>

        {!connected && (
          <div className="mt-4 rounded-xl border border-warning/20 bg-warning/5 px-3.5 py-3 text-xs text-warning">
            Connect the account before arming Conquest Guard.
          </div>
        )}
        {error && (
          <div className="mt-4 rounded-xl border border-danger/25 bg-danger/7 px-3.5 py-3 text-xs text-danger">{error}</div>
        )}
      </div>
    </section>
  );
}
