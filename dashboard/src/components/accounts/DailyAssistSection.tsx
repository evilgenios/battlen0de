'use client';

import { useState } from 'react';
import { CheckCircle2, Play, ShieldAlert, Sparkles } from 'lucide-react';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { describeError } from '@/components/ui/ErrorState';
import { useToast } from '@/components/ui/Toast';
import {
  runDailyOfficerExpAssist,
  runDailyOfficerMissionAssist,
  runDailyUnitCouponAssist,
} from '@/lib/api';
import { useDailyMissionAssist } from '@/lib/hooks/useIntel';
import type {
  DailyObservedMissionOption,
  DailyObservedOfficerOption,
} from '@/lib/api/types';

function assistTone(state: string): BadgeTone {
  if (state === 'complete') return 'success';
  if (state === 'ready') return 'accent';
  if (state === 'mapping_required' || state === 'evidence_required') return 'warning';
  if (state === 'combat_disabled') return 'danger';
  if (state === 'input_required' || state === 'validation_required') return 'info';
  return 'neutral';
}

function officerOptions(value: unknown): DailyObservedOfficerOption[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is DailyObservedOfficerOption =>
        Boolean(entry && typeof entry === 'object' && 'officer_id' in entry))
    : [];
}

function missionOptions(value: unknown): DailyObservedMissionOption[] {
  return Array.isArray(value)
    ? value.filter((entry): entry is DailyObservedMissionOption =>
        Boolean(entry && typeof entry === 'object' && 'task_id' in entry))
    : [];
}

export function DailyAssistSection({
  accountId,
  connected,
  onChanged,
}: {
  accountId: string;
  connected: boolean;
  onChanged?: () => void | Promise<void>;
}) {
  const toast = useToast();
  const { assist, error, isLoading, refresh } = useDailyMissionAssist(accountId, true);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [officerExpId, setOfficerExpId] = useState('');
  const [missionTaskId, setMissionTaskId] = useState('');
  const [missionOfficerIds, setMissionOfficerIds] = useState<string[]>([]);

  async function afterConfirmed() {
    await refresh();
    await onChanged?.();
  }

  async function runUnitCoupon() {
    const objective = assist?.objectives.find((item) => item.key === 'use_1_unit_coupon');
    if (!objective || objective.assist_state !== 'ready') return;
    const itemId = String(objective.resolved_parameters.item_id ?? '');
    if (!window.confirm(
      `Assist will use exactly 1 evidence-proven Unit Coupon item (${itemId}). Continue?`,
    )) return;

    setBusyKey(objective.key);
    try {
      const result = await runDailyUnitCouponAssist(accountId);
      toast.success('Assist action confirmed', result.detail);
      await afterConfirmed();
    } catch (cause) {
      toast.error('Assist action failed', describeError(cause));
    } finally {
      setBusyKey(null);
    }
  }

  async function runOfficerExp() {
    const objective = assist?.objectives.find((item) => item.key === 'use_3_officer_exp');
    if (!objective || objective.action_key !== 'use_officer_exp' || !officerExpId) return;
    const itemId = String(objective.resolved_parameters.item_id ?? '');
    if (!window.confirm(
      `Assist will use exactly 3 evidence-proven Officer EXP items (${itemId}) on officer ${officerExpId}. Continue?`,
    )) return;

    setBusyKey(objective.key);
    try {
      const result = await runDailyOfficerExpAssist(accountId, officerExpId);
      toast.success('Officer EXP confirmed', result.detail);
      await afterConfirmed();
    } catch (cause) {
      toast.error('Officer EXP Assist failed', describeError(cause));
    } finally {
      setBusyKey(null);
    }
  }

  async function runOfficerMission() {
    const objective = assist?.objectives.find((item) => item.key === 'launch_officer_mission');
    if (
      !objective
      || objective.action_key !== 'launch_officer_mission'
      || !missionTaskId
      || missionOfficerIds.length === 0
    ) return;

    if (!window.confirm(
      `Assist will launch observed mission ${missionTaskId} with officers ${missionOfficerIds.join(', ')}. Continue?`,
    )) return;

    setBusyKey(objective.key);
    try {
      const result = await runDailyOfficerMissionAssist(
        accountId,
        missionTaskId,
        missionOfficerIds,
      );
      toast.success('Officer Mission confirmed', result.detail);
      await afterConfirmed();
    } catch (cause) {
      toast.error('Officer Mission Assist failed', describeError(cause));
    } finally {
      setBusyKey(null);
    }
  }

  function toggleMissionOfficer(officerId: string) {
    setMissionOfficerIds((current) =>
      current.includes(officerId)
        ? current.filter((value) => value !== officerId)
        : [...current, officerId],
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-danger/25 bg-danger/5 p-3 text-xs text-danger">
        Assist plan could not be loaded.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-accent/25 bg-accent/5 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold text-foreground">
            <Sparkles className="h-3.5 w-3.5 text-accent" />
            Assist Mode
          </p>
          <p className="mt-1 max-w-3xl text-[10px] leading-5 text-muted-foreground">
            Assist prepares only evidence-backed actions. Nothing loops in the background and every executable step requires your confirmation.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Badge tone="accent">{assist?.ready_count ?? 0} ready</Badge>
          <Badge tone="success">{assist?.complete_count ?? 0}/{assist?.total_count ?? 7} complete</Badge>
          <Badge tone="neutral">auto execution off</Badge>
        </div>
      </div>

      {isLoading && !assist ? (
        <p className="mt-3 text-xs text-muted-foreground">Loading Assist plan…</p>
      ) : (
        <div className="mt-3 grid gap-2 lg:grid-cols-2">
          {(assist?.objectives ?? []).map((objective) => {
            const officers = officerOptions(objective.resolved_parameters.officer_options);
            const missions = missionOptions(objective.resolved_parameters.mission_options);
            const displayParameters = Object.entries(objective.resolved_parameters)
              .filter(([key]) => key !== 'officer_options' && key !== 'mission_options');

            return (
              <div key={objective.key} className="rounded-lg border border-border/70 bg-surface/45 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    {objective.assist_state === 'complete' ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-success" />
                    ) : (
                      <ShieldAlert className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                    <span className="text-xs font-semibold text-foreground">{objective.label}</span>
                  </div>
                  <Badge tone={assistTone(objective.assist_state)}>
                    {objective.assist_state.replace(/_/g, ' ')}
                  </Badge>
                </div>

                <p className="mt-2 text-[10px] leading-5 text-muted-foreground">
                  {objective.assist_reason}
                </p>

                {displayParameters.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {displayParameters.map(([key, value]) => (
                      <Badge key={key} tone="neutral">
                        {key.replace(/_/g, ' ')}: {String(value)}
                      </Badge>
                    ))}
                  </div>
                )}

                {objective.action_key === 'use_officer_exp' && (
                  <div className="mt-3 space-y-2">
                    <select
                      aria-label="Officer for EXP Assist"
                      className="w-full rounded-lg border border-border bg-surface px-2.5 py-2 text-xs text-foreground"
                      value={officerExpId}
                      disabled={!connected || busyKey !== null}
                      onChange={(event) => setOfficerExpId(event.target.value)}
                    >
                      <option value="">Choose observed officer…</option>
                      {officers.map((officer) => (
                        <option key={officer.officer_id} value={officer.officer_id}>
                          {officer.officer_id} · level {officer.level} · power {officer.power}
                        </option>
                      ))}
                    </select>
                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Play className="h-3.5 w-3.5" />}
                      loading={busyKey === objective.key}
                      disabled={!connected || !officerExpId || busyKey !== null}
                      onClick={runOfficerExp}
                    >
                      Confirm 3 Officer EXP
                    </Button>
                  </div>
                )}

                {objective.action_key === 'launch_officer_mission' && (
                  <div className="mt-3 space-y-2">
                    <select
                      aria-label="Officer mission for Assist"
                      className="w-full rounded-lg border border-border bg-surface px-2.5 py-2 text-xs text-foreground"
                      value={missionTaskId}
                      disabled={!connected || busyKey !== null}
                      onChange={(event) => {
                        setMissionTaskId(event.target.value);
                        setMissionOfficerIds([]);
                      }}
                    >
                      <option value="">Choose observed mission…</option>
                      {missions.map((mission) => (
                        <option key={mission.task_id} value={mission.task_id}>
                          {mission.task_id} · status {mission.status}
                        </option>
                      ))}
                    </select>

                    {officers.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {officers.map((officer) => {
                          const selected = missionOfficerIds.includes(officer.officer_id);
                          return (
                            <button
                              key={officer.officer_id}
                              type="button"
                              disabled={!connected || busyKey !== null}
                              onClick={() => toggleMissionOfficer(officer.officer_id)}
                              className={`rounded-lg border px-2 py-1 text-[10px] transition ${
                                selected
                                  ? 'border-accent/50 bg-accent/10 text-accent'
                                  : 'border-border bg-surface text-muted-foreground'
                              }`}
                            >
                              {officer.officer_id}
                            </button>
                          );
                        })}
                      </div>
                    )}

                    <Button
                      size="sm"
                      variant="secondary"
                      icon={<Play className="h-3.5 w-3.5" />}
                      loading={busyKey === objective.key}
                      disabled={
                        !connected
                        || !missionTaskId
                        || missionOfficerIds.length === 0
                        || busyKey !== null
                      }
                      onClick={runOfficerMission}
                    >
                      Confirm Officer Mission
                    </Button>
                  </div>
                )}

                {objective.assist_state === 'ready' && objective.action_key === 'use_unit_coupon' && (
                  <Button
                    className="mt-3"
                    size="sm"
                    variant="primary"
                    icon={<Play className="h-3.5 w-3.5" />}
                    loading={busyKey === objective.key}
                    disabled={!connected || busyKey !== null}
                    onClick={runUnitCoupon}
                  >
                    Confirm & run
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
