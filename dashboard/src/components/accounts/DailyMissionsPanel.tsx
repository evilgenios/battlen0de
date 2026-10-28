'use client';

import { useMemo, useState } from 'react';
import { ChevronDown, GitCompareArrows, ListChecks, RefreshCw, ScanSearch, ShieldCheck } from 'lucide-react';
import { DailyAssistSection } from '@/components/accounts/DailyAssistSection';
import { Badge, type BadgeTone } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import {
  clearDailyMissionMapping,
  confirmDailyMissionMapping,
  getDailyMissionMapperDiff,
  setDailyMissionMapperBaseline,
} from '@/lib/api';
import { useDailyMissionPlan, useDailyMissions } from '@/lib/hooks/useIntel';
import { formatUnixSeconds } from '@/lib/utils/format';
import type {
  DailyMissionMapperDiffResult,
  DailyMissionTaskInfo,
} from '@/lib/api/types';

function taskTone(status: string): BadgeTone {
  if (status === 'task_reward_taken') return 'success';
  if (status === 'task_finished') return 'info';
  if (status === 'task_accepted') return 'warning';
  return 'neutral';
}

function rewardTone(status: string): BadgeTone {
  if (status === 'reward_taken') return 'success';
  if (status === 'reward_available') return 'accent';
  if (status === 'reward_unavailable') return 'neutral';
  return 'warning';
}

function planTone(state: string): BadgeTone {
  if (state === 'complete') return 'success';
  if (state === 'pending') return 'warning';
  if (state === 'mapped_missing' || state === 'unknown') return 'danger';
  return 'neutral';
}

function capabilityTone(state: string): BadgeTone {
  if (state === 'guarded_primitive') return 'info';
  return 'neutral';
}

function TaskRow({ task }: { task: DailyMissionTaskInfo }) {
  return (
    <div className="grid gap-3 border-t border-border/55 px-4 py-3 first:border-t-0 sm:grid-cols-[86px_110px_minmax(0,1fr)_120px] sm:items-center">
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Task ID</p>
        <p className="mt-1 font-mono text-xs font-semibold text-foreground">#{task.id}</p>
      </div>
      <div>
        <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Only ID</p>
        <p className="mt-1 font-mono text-xs font-semibold text-foreground">{task.only_id || '—'}</p>
      </div>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={taskTone(task.status_label)}>{task.status_label}</Badge>
          <span className="font-mono text-xs text-foreground">num {task.num.toLocaleString()}</span>
        </div>
        <p className="mt-1.5 truncate text-[10px] text-muted-foreground">
          Source: {task.source}
        </p>
      </div>
      <div className="sm:text-right">
        <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Finished</p>
        <p className="mt-1 text-[10px] font-medium text-foreground">
          {task.finish_timestamp ? formatUnixSeconds(task.finish_timestamp) : '—'}
        </p>
      </div>
    </div>
  );
}

export function DailyMissionsPanel({
  accountId,
  connected,
  canMap = false,
}: {
  accountId: string;
  connected: boolean;
  canMap?: boolean;
}) {
  const { dailyMissions, error, isLoading, refresh } = useDailyMissions(accountId, true);
  const {
    dailyPlan,
    error: planError,
    isLoading: planLoading,
    refresh: refreshPlan,
  } = useDailyMissionPlan(accountId, true);
  const [open, setOpen] = useState(false);
  const [mapperBusy, setMapperBusy] = useState(false);
  const [mapperError, setMapperError] = useState<string | null>(null);
  const [mapperMessage, setMapperMessage] = useState<string | null>(null);
  const [mapperDiff, setMapperDiff] = useState<DailyMissionMapperDiffResult | null>(null);
  const [baselineCaptured, setBaselineCaptured] = useState(false);
  const [selectedObjectiveKey, setSelectedObjectiveKey] = useState('');

  async function captureBaseline() {
    setMapperBusy(true);
    setMapperError(null);
    setMapperMessage(null);
    try {
      await setDailyMissionMapperBaseline(accountId);
      setBaselineCaptured(true);
      setMapperDiff(null);
    } catch (caught) {
      setMapperError(caught instanceof Error ? caught.message : 'Could not capture mapper baseline');
    } finally {
      setMapperBusy(false);
    }
  }

  async function compareBaseline() {
    setMapperBusy(true);
    setMapperError(null);
    setMapperMessage(null);
    try {
      setMapperDiff(await getDailyMissionMapperDiff(accountId));
    } catch (caught) {
      setMapperError(caught instanceof Error ? caught.message : 'Could not compare mapper baseline');
    } finally {
      setMapperBusy(false);
    }
  }

  async function confirmMapping() {
    if (!selectedObjectiveKey) return;
    setMapperBusy(true);
    setMapperError(null);
    setMapperMessage(null);
    try {
      const mapping = await confirmDailyMissionMapping(accountId, selectedObjectiveKey);
      setMapperMessage(`Mapped ${mapping.label} to task #${mapping.task_id}.`);
      setBaselineCaptured(false);
      setMapperDiff(null);
      setSelectedObjectiveKey('');
      await Promise.all([refresh(), refreshPlan()]);
    } catch (caught) {
      setMapperError(caught instanceof Error ? caught.message : 'Could not confirm mission mapping');
    } finally {
      setMapperBusy(false);
    }
  }

  async function clearMapping(objectiveKey: string, label: string) {
    setMapperBusy(true);
    setMapperError(null);
    setMapperMessage(null);
    try {
      await clearDailyMissionMapping(accountId, objectiveKey);
      setMapperMessage(`Cleared mapping for ${label}.`);
      await refreshPlan();
    } catch (caught) {
      setMapperError(caught instanceof Error ? caught.message : 'Could not clear mission mapping');
    } finally {
      setMapperBusy(false);
    }
  }

  const confirmableChanges = mapperDiff?.task_changes.filter(
    (change) => change.kind === 'changed'
      && change.after
      && change.changed_fields.some((field) => field === 'status' || field === 'num'),
  ) ?? [];
  const mappingConfirmable = confirmableChanges.length === 1;

  const tasks = useMemo(
    () => [...(dailyMissions?.tasks ?? [])].sort((a, b) => a.id - b.id),
    [dailyMissions?.tasks],
  );
  const completed = tasks.filter((task) => task.status_label === 'task_reward_taken').length;
  const claimable = tasks.filter((task) => task.status_label === 'task_finished').length;
  const awards = dailyMissions?.daily_awards ?? [];
  const supplyCases = dailyMissions?.supply_cases ?? [];

  return (
    <section className="premium-panel overflow-hidden rounded-2xl">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="group flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-surface-muted/25 sm:px-5"
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-info/20 bg-info/8 text-info">
          <ListChecks className="h-[18px] w-[18px]" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">Daily Missions</span>
            <Badge tone="info">Read only</Badge>
            {!connected && <Badge tone="neutral">Offline</Badge>}
            {dailyMissions?.state_source === 'live' && <Badge tone="success">Live state</Badge>}
            {dailyMissions?.state_source === 'persisted' && <Badge tone="warning">Last observed</Badge>}
            {dailyMissions?.observed && <Badge tone="success">{tasks.length} observed</Badge>}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            {dailyMissions?.observed
              ? `${dailyMissions.activition_point} activation · ${completed} claimed tasks · ${claimable} finished`
              : isLoading
                ? 'Loading observed daily state…'
                : 'No daily mission observation is cached yet.'}
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-300 ${
            open ? 'rotate-180 text-accent' : 'group-hover:text-foreground'
          }`}
        />
      </button>

      {open && (
        <div className="border-t border-border/70 bg-surface/25 motion-safe:animate-[premium-reveal_.3s_ease-out]">
          {error ? (
            <div className="p-5">
              <ErrorState error={error} onRetry={() => refresh()} title="Could not load daily mission state" />
            </div>
          ) : isLoading && !dailyMissions ? (
            <div className="space-y-2 p-5">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : !dailyMissions?.observed ? (
            <div className="px-5 py-6 text-sm text-muted-foreground">
              Connect this account once to observe server-provided daily task state. This panel never sends a game action.
            </div>
          ) : (
            <>
              <div className="grid gap-3 border-b border-border/70 px-4 py-4 sm:grid-cols-2 lg:grid-cols-4 sm:px-5">
                <div className="data-chip rounded-xl p-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Activation</p>
                  <p className="mt-1 text-lg font-semibold text-foreground">{dailyMissions.activition_point}</p>
                </div>
                <div className="data-chip rounded-xl p-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Tasks</p>
                  <p className="mt-1 text-lg font-semibold text-foreground">{tasks.length}</p>
                </div>
                <div className="data-chip rounded-xl p-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Rewards</p>
                  <p className="mt-1 text-lg font-semibold text-foreground">{awards.length}</p>
                </div>
                <div className="data-chip rounded-xl p-3">
                  <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Supply cases</p>
                  <p className="mt-1 text-lg font-semibold text-foreground">{supplyCases.length}</p>
                </div>
              </div>

              <div className="border-b border-border/70 px-4 py-4 sm:px-5">
                <DailyAssistSection
                  accountId={accountId}
                  connected={connected}
                  onChanged={async () => {
                    await Promise.all([refresh(), refreshPlan()]);
                  }}
                />
              </div>

              <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border/70 px-4 py-3 sm:px-5">
                <div className="max-w-3xl">
                  <p className="flex items-center gap-2 text-xs font-semibold text-foreground">
                    <ShieldCheck className="h-3.5 w-3.5 text-success" />
                    Protocol-observed state
                  </p>
                  <p className="mt-1 text-[10px] leading-5 text-muted-foreground">{dailyMissions.limitation}</p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                  onClick={() => refresh()}
                >
                  Refresh
                </Button>
              </div>

              <div className="border-b border-border/70 px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold text-foreground">Evidence-backed daily plan</p>
                    <p className="mt-1 text-[10px] leading-5 text-muted-foreground">
                      The seven requested objectives are listed here, but a protocol task is attached only after
                      a before/after mapper capture proves the relationship.
                    </p>
                  </div>
                  {dailyPlan && (
                    <div className="flex flex-wrap gap-2">
                      <Badge tone="info">{dailyPlan.mapped_count}/{dailyPlan.total_count} mapped</Badge>
                      <Badge tone="success">{dailyPlan.complete_count}/{dailyPlan.total_count} complete</Badge>
                    </div>
                  )}
                </div>

                {planError ? (
                  <p className="mt-3 text-xs text-danger">Could not load the evidence-backed plan.</p>
                ) : planLoading && !dailyPlan ? (
                  <div className="mt-3 space-y-2">
                    <Skeleton className="h-12 w-full" />
                    <Skeleton className="h-12 w-full" />
                  </div>
                ) : (
                  <div className="mt-3 grid gap-2 lg:grid-cols-2">
                    {(dailyPlan?.objectives ?? []).map((objective) => (
                      <div
                        key={objective.key}
                        className="rounded-xl border border-border/70 bg-surface/35 px-3 py-3"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-xs font-semibold text-foreground">{objective.label}</p>
                          <div className="flex flex-wrap gap-1.5">
                            <Badge tone={capabilityTone(objective.automation_state)}>
                              {objective.automation_state.replace(/_/g, ' ')}
                            </Badge>
                            <Badge tone={planTone(objective.mapping_state)}>
                              {objective.mapping_state.replace(/_/g, ' ')}
                            </Badge>
                            {objective.combat && <Badge tone="danger">combat</Badge>}
                            {!objective.execution_exposed && <Badge tone="neutral">execution locked</Badge>}
                          </div>
                        </div>
                        <p className="mt-1 text-[10px] leading-4 text-muted-foreground">
                          {objective.requested_goal}
                        </p>
                        <p className="mt-2 text-[10px] leading-4 text-muted-foreground">
                          {objective.blockers.join(' · ')}
                        </p>
                        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[9px] text-muted-foreground">
                          <span>task {objective.task_id == null ? 'unmapped' : `#${objective.task_id}`}</span>
                          {objective.only_id != null && <span>only_id {objective.only_id}</span>}
                          {objective.num != null && <span>num {objective.num.toLocaleString()}</span>}
                          {objective.task_status_label && <span>{objective.task_status_label}</span>}
                        </div>
                        {canMap && objective.mapping_state !== 'unmapped' && (
                          <div className="mt-2">
                            <Button
                              size="sm"
                              variant="ghost"
                              disabled={mapperBusy}
                              onClick={() => clearMapping(objective.key, objective.label)}
                            >
                              Clear mapping
                            </Button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {dailyPlan && <p className="mt-3 text-[10px] text-muted-foreground">{dailyPlan.limitation}</p>}
              </div>

              {canMap && (
                <div className="border-b border-border/70 px-4 py-4 sm:px-5">
                  <div className="rounded-xl border border-accent/20 bg-accent/5 p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p className="flex items-center gap-2 text-xs font-semibold text-foreground">
                          <ScanSearch className="h-3.5 w-3.5 text-accent" />
                          Daily Mission Mapper
                        </p>
                        <p className="mt-1 max-w-2xl text-[10px] leading-5 text-muted-foreground">
                          Capture a protocol baseline, perform exactly one manual in-game action, then compare.
                          The mapper never sends the game action itself.
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={!connected || mapperBusy}
                          icon={<ScanSearch className="h-3.5 w-3.5" />}
                          onClick={captureBaseline}
                        >
                          Capture baseline
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={!connected || mapperBusy || !baselineCaptured}
                          icon={<GitCompareArrows className="h-3.5 w-3.5" />}
                          onClick={compareBaseline}
                        >
                          Compare
                        </Button>
                      </div>
                    </div>

                    {!connected && (
                      <p className="mt-3 text-[10px] text-warning">
                        Mapper controls require a live connected observation. Persisted state remains view-only.
                      </p>
                    )}
                    {baselineCaptured && !mapperDiff && !mapperError && (
                      <p className="mt-3 text-[10px] text-success">
                        Baseline captured. Perform one manual action, then press Compare.
                      </p>
                    )}
                    {mapperError && (
                      <p className="mt-3 text-[10px] text-danger">{mapperError}</p>
                    )}
                    {mapperMessage && (
                      <p className="mt-3 text-[10px] text-success">{mapperMessage}</p>
                    )}
                    {mapperDiff && (
                      <div className="mt-4 rounded-lg border border-border/70 bg-surface/45 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={mapperDiff.has_changes ? 'warning' : 'success'}>
                            {mapperDiff.has_changes ? 'Changes detected' : 'No changes'}
                          </Badge>
                          <span className="font-mono text-[10px] text-muted-foreground">
                            activation Δ {mapperDiff.activation.delta}
                          </span>
                        </div>
                        {mapperDiff.task_changes.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {mapperDiff.task_changes.map((change) => (
                              <div
                                key={change.id}
                                className="rounded-lg border border-border/60 bg-surface/40 px-3 py-2"
                              >
                                <div className="flex flex-wrap items-center gap-2">
                                  <span className="font-mono text-xs font-semibold text-foreground">
                                    Task #{change.id}
                                  </span>
                                  <Badge tone="info">{change.kind}</Badge>
                                  <span className="text-[10px] text-muted-foreground">
                                    {change.changed_fields.join(', ')}
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        {mapperDiff.reward_changes.length > 0 && (
                          <p className="mt-3 text-[10px] text-muted-foreground">
                            {mapperDiff.reward_changes.length} reward-state change
                            {mapperDiff.reward_changes.length === 1 ? '' : 's'} detected.
                          </p>
                        )}

                        {mapperDiff.inventory_changes.length > 0 && (
                          <div className="mt-3 rounded-lg border border-border/60 bg-surface/40 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                              Inventory evidence
                            </p>
                            <div className="mt-2 space-y-1.5">
                              {mapperDiff.inventory_changes.map((change) => (
                                <div
                                  key={change.item_id}
                                  className="flex flex-wrap items-center gap-2 font-mono text-[10px]"
                                >
                                  <span className="text-foreground">{change.item_id}</span>
                                  <span className="text-muted-foreground">
                                    {change.before_quantity} → {change.after_quantity}
                                  </span>
                                  <Badge tone={change.delta < 0 ? 'warning' : 'success'}>
                                    Δ {change.delta > 0 ? '+' : ''}{change.delta}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {!mapperDiff.inventory_observed.before || !mapperDiff.inventory_observed.after ? (
                          <p className="mt-3 text-[10px] leading-5 text-muted-foreground">
                            Inventory evidence unavailable for this comparison; both baseline and current
                            observations must include a real bag snapshot.
                          </p>
                        ) : null}

                        {mapperDiff.supply_case_changes.length > 0 && (
                          <div className="mt-3 rounded-lg border border-border/60 bg-surface/40 p-3">
                            <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
                              Supply-case evidence
                            </p>
                            <div className="mt-2 space-y-1.5">
                              {mapperDiff.supply_case_changes.map((change) => (
                                <div
                                  key={change.key}
                                  className="flex flex-wrap items-center gap-2 font-mono text-[10px]"
                                >
                                  <span className="text-foreground">{change.key}</span>
                                  <span className="text-muted-foreground">
                                    {change.before_value} → {change.after_value}
                                  </span>
                                  <Badge tone={change.delta < 0 ? 'warning' : 'success'}>
                                    Δ {change.delta > 0 ? '+' : ''}{change.delta}
                                  </Badge>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {!mapperDiff.supply_case_observed.before || !mapperDiff.supply_case_observed.after ? (
                          <p className="mt-3 text-[10px] leading-5 text-muted-foreground">
                            Supply-case evidence unavailable for this comparison; both baseline and current
                            observations must include real supply-case state.
                          </p>
                        ) : null}

                        <div className="mt-4 border-t border-border/60 pt-3">
                          {mappingConfirmable ? (
                            <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                              <label className="min-w-0 flex-1 text-[10px] text-muted-foreground">
                                Objective this manual action represented
                                <select
                                  className="mt-1 w-full rounded-lg border border-border/80 bg-surface px-3 py-2 text-xs text-foreground"
                                  value={selectedObjectiveKey}
                                  onChange={(event) => setSelectedObjectiveKey(event.target.value)}
                                  aria-label="Daily objective to map"
                                >
                                  <option value="">Select objective…</option>
                                  {(dailyPlan?.objectives ?? []).map((objective) => (
                                    <option key={objective.key} value={objective.key}>
                                      {objective.label}
                                    </option>
                                  ))}
                                </select>
                              </label>
                              <Button
                                size="sm"
                                variant="primary"
                                disabled={mapperBusy || !selectedObjectiveKey}
                                onClick={confirmMapping}
                              >
                                Confirm mapping
                              </Button>
                            </div>
                          ) : (
                            <p className="text-[10px] leading-5 text-warning">
                              Mapping confirmation is locked unless exactly one existing daily task changed
                              in status or num. Repeat the capture with only one manual action if this diff is ambiguous.
                            </p>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="p-3 sm:p-4">
                <div className="overflow-hidden rounded-xl border border-border/70 bg-surface/35">
                  {tasks.map((task) => <TaskRow key={task.id} task={task} />)}
                </div>

                <div className="mt-4 rounded-xl border border-border/70 bg-surface/35 p-4">
                  <p className="text-xs font-semibold text-foreground">Daily activation rewards</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {awards.map((award) => (
                      <Badge key={award.award_index} tone={rewardTone(award.award_status_label)}>
                        Reward {award.award_index}: {award.award_status_label}
                      </Badge>
                    ))}
                    {awards.length === 0 && (
                      <span className="text-xs text-muted-foreground">No reward slots reported.</span>
                    )}
                  </div>
                </div>

                <div className="mt-4 rounded-xl border border-border/70 bg-surface/35 p-4">
                  <p className="text-xs font-semibold text-foreground">Campaign / supply-case raw state</p>
                  <p className="mt-1 text-[10px] leading-5 text-muted-foreground">
                    Unmapped protocol key/value data. No key is treated as Campaign Resupply until a live before/after capture proves it.
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {supplyCases.map((entry) => (
                      <Badge key={entry.key} tone="neutral">
                        {entry.key}: {entry.value}
                      </Badge>
                    ))}
                    {supplyCases.length === 0 && (
                      <span className="text-xs text-muted-foreground">No supply-case state reported.</span>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
