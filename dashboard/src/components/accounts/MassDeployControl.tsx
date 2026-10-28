'use client';

import { useState } from 'react';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { Rocket, Square } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { massCancel, massDeploy } from '@/lib/api/actions';
import { ApiError } from '@/lib/api/client';
import { useToast } from '@/components/ui/Toast';
import type { MassDeployResult } from '@/lib/api/types';

const inputClass =
  'w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50';

/** Mass Deploy: teleport this account near a player and join its units to
 * an Army Group. Ported from the legacy Discord bot's /mass_deploy — see
 * service/app/core/mass_deploy.py for what could and couldn't be ported.
 * This account-detail page only targets THIS account (never "every stored
 * account" — the backend requires explicit account_ids either way).
 * Execute requires an explicit confirmation dialog — dry run does not. */
export function MassDeployControl({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { user } = useAuthSession();
  if (user?.role !== 'admin') return null;
  return <AdminMassDeployControl accountId={accountId} connected={connected} />;
}

function AdminMassDeployControl({ accountId, connected }: { accountId: string; connected: boolean }) {
  const [agId, setAgId] = useState('');
  const [playerUid, setPlayerUid] = useState('');
  const [armyIds, setArmyIds] = useState('auto');
  const [groupType, setGroupType] = useState<'auto' | 'land' | 'navy'>('auto');
  const [execute, setExecute] = useState(false);
  const [pending, setPending] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MassDeployResult | null>(null);
  const toast = useToast();

  async function runDeploy() {
    if (pending) return;
    setError(null);
    setResult(null);
    setPending(true);
    try {
      const response = await massDeploy({
        account_ids: [accountId],
        ag_id: agId,
        player_uid: playerUid,
        army_ids: armyIds || 'auto',
        group_type: groupType,
        execute,
      });
      setResult(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Mass deploy request failed.');
    } finally {
      setPending(false);
    }
  }

  function handleRunClick() {
    if (execute) {
      setConfirmOpen(true);
      return;
    }
    void runDeploy();
  }

  async function handleCancel() {
    if (cancelling) return;
    setCancelling(true);
    try {
      const response = await massCancel();
      toast[response.cancelled ? 'success' : 'error'](
        response.cancelled ? 'Cancellation requested' : 'Nothing to cancel', response.detail,
      );
    } catch (err) {
      toast.error('Cancel failed', err instanceof ApiError ? err.message : 'Could not reach the dashboard server.');
    } finally {
      setCancelling(false);
    }
  }

  const canSubmit = agId.trim() !== '' && playerUid.trim() !== '' && !pending;

  return (
    <div className="flex flex-col gap-3 border-b border-border py-4 last:border-0">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-surface-muted">
          <Rocket className="h-4 w-4 text-muted-foreground" />
        </div>
        <div>
          <p className="text-sm font-medium text-foreground">Mass Deploy</p>
          <p className="text-xs text-muted-foreground">
            Teleport this account near a player and join an Army Group. Dry run by default.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <input
          className={inputClass}
          placeholder="AG ID"
          value={agId}
          onChange={(e) => setAgId(e.target.value)}
          aria-label="Army Group ID"
        />
        <input
          className={inputClass}
          placeholder="Player UID"
          value={playerUid}
          onChange={(e) => setPlayerUid(e.target.value)}
          aria-label="Target player UID"
        />
        <input
          className={inputClass}
          placeholder="Army slots (auto)"
          value={armyIds}
          onChange={(e) => setArmyIds(e.target.value)}
          aria-label="Army slots"
        />
        <select
          className={inputClass}
          value={groupType}
          onChange={(e) => setGroupType(e.target.value as 'auto' | 'land' | 'navy')}
          aria-label="Group type"
        >
          <option value="auto">Auto-detect</option>
          <option value="land">Land</option>
          <option value="navy">Navy</option>
        </select>
      </div>

      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          <input type="checkbox" checked={execute} onChange={(e) => setExecute(e.target.checked)} />
          Execute (unchecked = dry run, sends no requests)
        </label>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="outline" icon={<Square className="h-3.5 w-3.5" />} loading={cancelling} onClick={handleCancel}>
            Cancel running deployment
          </Button>
          <Button
            size="sm"
            variant={execute ? 'danger' : 'secondary'}
            disabled={!canSubmit || !connected}
            title={connected ? undefined : 'Connect the account first'}
            loading={pending}
            onClick={handleRunClick}
          >
            {execute ? 'Run' : 'Preview (dry run)'}
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={runDeploy}
        title="Execute Mass Deploy"
        description={
          <>
            This will actually teleport this account near player <span className="font-medium text-foreground">{playerUid}</span> and
            attempt to join Army Group <span className="font-medium text-foreground">{agId}</span> — using teleport items, never premium
            currency. This is a real game action, not a preview.
          </>
        }
        confirmLabel="Execute"
        destructive
      />

      {error && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">{error}</div>
      )}

      {result && (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            result.execute ? 'border-border bg-surface-muted' : 'border-accent/30 bg-accent/5'
          }`}
        >
          <p className="font-medium text-foreground">
            {result.execute
              ? `Execution: ${result.complete_count}/${result.total_count} fully completed`
              : 'Dry run — no game requests were sent'}
          </p>
          <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
            {result.results.map((row) => (
              <li key={row.account_id}>
                {row.label}: {row.error ? `failed — ${row.error}` : `teleport: ${row.teleport}; AG: ${row.ag}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
