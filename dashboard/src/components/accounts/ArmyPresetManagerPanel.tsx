'use client';

import { useState } from 'react';
import { ChevronDown, Save, ShieldCheck } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { describeError, ErrorState } from '@/components/ui/ErrorState';
import { useToast } from '@/components/ui/Toast';
import { renameArmyPreset } from '@/lib/api';
import { useArmyPresets } from '@/lib/hooks/useIntel';

const PLAY_TYPE_LABELS: Record<number, string> = {
  10: 'Main Map', 11: 'Guardian', 12: 'Dungeon', 13: 'Arena',
  1001: 'Exercise', 1002: 'Exercise Navy',
};

export function ArmyPresetManagerPanel({ accountId, connected }: { accountId: string; connected: boolean }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [names, setNames] = useState<Record<string, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const { presets, error, isLoading, refresh } = useArmyPresets(accountId, true);

  async function rename(presetId: number, playType: number, currentName: string) {
    const key = `${playType}:${presetId}`;
    const name = (names[key] ?? currentName).trim();
    if (!name) return;
    setBusyKey(key);
    try {
      const result = await renameArmyPreset(accountId, presetId, playType, name);
      toast.success('Preset renamed', `Preset #${result.preset_id} is now “${result.name}”.`);
      await refresh();
    } catch (cause) {
      toast.error('Preset rename failed', describeError(cause));
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <section className="premium-panel overflow-hidden rounded-2xl">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}
        className="group flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-surface-muted/25 sm:px-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-info/20 bg-info/8 text-info">
          <ShieldCheck className="h-[18px] w-[18px]" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">Army Preset Manager</span>
            <Badge tone="success">passive state</Badge>
            <Badge tone="info">rename verified</Badge>
            {presets?.observed && <Badge tone="neutral">{presets.presets.length} presets</Badge>}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            Inspect saved cards/officers/auto-train settings; rename with server confirmation.
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-border/70 p-4 sm:p-5">
          {error ? (
            <ErrorState error={error} onRetry={() => refresh()} title="Could not load army presets" />
          ) : isLoading && !presets ? (
            <p className="text-xs text-muted-foreground">Loading presets…</p>
          ) : (presets?.presets ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No preset state has been observed yet. Reconnect the account to receive login-state presets.
            </p>
          ) : (
            <div className="grid gap-3 lg:grid-cols-2">
              {(presets?.presets ?? []).map((preset) => {
                const key = `${preset.play_type}:${preset.preset_id}`;
                return (
                  <div key={key} className="rounded-xl border border-border/70 bg-surface/35 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-foreground">{preset.name || `Preset #${preset.preset_id}`}</p>
                        <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                          #{preset.preset_id} · {PLAY_TYPE_LABELS[preset.play_type] ?? `play type ${preset.play_type}`}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {preset.is_auto_train && <Badge tone="success">auto train</Badge>}
                        {preset.is_only_use_officer && <Badge tone="info">officers only</Badge>}
                        <Badge tone="warning">apply locked</Badge>
                      </div>
                    </div>
                    <div className="mt-3 space-y-2">
                      {preset.armies.map((army) => (
                        <div key={army.army_id} className="rounded-lg border border-border/60 px-3 py-2 text-[10px]">
                          <span className="font-semibold text-foreground">Army {army.army_id}</span>
                          <span className="ml-2 text-muted-foreground">card {army.card_id || '—'}</span>
                          <p className="mt-1 text-muted-foreground">
                            Officers: {army.officers.map((officer) => officer.officer_id || `slot ${officer.index}`).join(', ') || 'none reported'}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <input
                        className="min-w-[170px] flex-1 rounded-lg border border-border bg-surface px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                        aria-label={`Rename preset ${preset.preset_id}`}
                        value={names[key] ?? preset.name}
                        maxLength={64}
                        disabled={!connected || busyKey !== null}
                        onChange={(event) => setNames((current) => ({ ...current, [key]: event.target.value }))}
                      />
                      <Button size="sm" variant="secondary" icon={<Save className="h-3.5 w-3.5" />}
                        loading={busyKey === key} disabled={!connected || busyKey !== null}
                        onClick={() => rename(preset.preset_id, preset.play_type, preset.name)}>
                        Rename
                      </Button>
                    </div>
                    <p className="mt-2 text-[10px] leading-5 text-muted-foreground">
                      Apply is disabled until Assist can preview any resource/item effects before sending it.
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
