'use client';

import { useState } from 'react';
import { ChevronDown, RefreshCw, Swords } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorState, describeError } from '@/components/ui/ErrorState';
import { useToast } from '@/components/ui/Toast';
import { refreshBattleReports } from '@/lib/api';
import { useBattleReports } from '@/lib/hooks/useIntel';
import { formatUnixSeconds } from '@/lib/utils/format';

export function BattleReportAnalyzerPanel({ accountId, connected }: { accountId: string; connected: boolean }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const { reports, error, isLoading, refresh } = useBattleReports(accountId, true);

  async function handleRefresh() {
    setRefreshing(true);
    try {
      const result = await refreshBattleReports(accountId);
      toast.success('Battle reports refreshed', `${result.report_count} report summaries loaded.`);
      await refresh();
    } catch (cause) {
      toast.error('Battle report refresh failed', describeError(cause));
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <section className="premium-panel overflow-hidden rounded-2xl">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}
        className="group flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-surface-muted/25 sm:px-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-danger/20 bg-danger/8 text-danger">
          <Swords className="h-[18px] w-[18px]" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">Battle Report Analyzer</span>
            <Badge tone="info">summary analysis</Badge>
            {reports?.observed && <Badge tone="success">{reports.report_count} reports</Badge>}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            Damage, losses, kill points and participants from the real report inbox.
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-border/70 p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-[10px] leading-5 text-muted-foreground">
              Refresh reads only the Warpath report mailbox summary list. Full report details stay locked until mail-ID semantics are proven live.
            </p>
            <Button size="sm" variant="secondary" icon={<RefreshCw className="h-3.5 w-3.5" />}
              disabled={!connected} loading={refreshing} onClick={handleRefresh}>
              Refresh reports
            </Button>
          </div>

          {error ? (
            <div className="mt-4"><ErrorState error={error} onRetry={() => refresh()} title="Could not load reports" /></div>
          ) : isLoading && !reports ? (
            <p className="mt-4 text-xs text-muted-foreground">Loading report cache…</p>
          ) : (
            <>
              <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-5">
                {[
                  ['Reports', reports?.report_count ?? 0],
                  ['Attacker damage', reports?.total_attacker_damage ?? 0],
                  ['Attacker dead', reports?.total_attacker_dead ?? 0],
                  ['Defender dead', reports?.total_defender_dead ?? 0],
                  ['Kill points', reports?.total_kill_points ?? 0],
                ].map(([label, value]) => (
                  <div key={String(label)} className="data-chip rounded-xl p-3">
                    <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
                    <p className="mt-1 text-sm font-semibold text-foreground">{Number(value).toLocaleString()}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 space-y-2">
                {(reports?.reports ?? []).slice(0, 30).map((report) => (
                  <div key={report.id} className="rounded-xl border border-border/70 bg-surface/35 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-xs font-semibold text-foreground">{report.title || `Report #${report.id}`}</p>
                        <p className="mt-1 text-[10px] text-muted-foreground">
                          {report.players.map((player) => player.name || String(player.uid)).join(' vs ') || report.kind}
                        </p>
                      </div>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {report.create_time ? formatUnixSeconds(report.create_time) : '—'}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      <Badge tone="neutral">type {report.battle_type || '—'}</Badge>
                      <Badge tone="info">attacker damage {report.attacker_damage.toLocaleString()}</Badge>
                      <Badge tone="neutral">attacker dead {report.attacker_dead.toLocaleString()}</Badge>
                      <Badge tone="neutral">defender dead {report.defender_dead.toLocaleString()}</Badge>
                      <Badge tone="accent">KP {report.kill_point.toLocaleString()}</Badge>
                      {report.group_kill_num > 0 && <Badge tone="success">AG kills {report.group_kill_num}</Badge>}
                    </div>
                  </div>
                ))}
                {reports?.observed && reports.report_count === 0 && (
                  <p className="text-xs text-muted-foreground">The report inbox returned no battle summaries.</p>
                )}
                {!reports?.observed && (
                  <p className="text-xs text-muted-foreground">Press Refresh reports after connecting to load the report inbox.</p>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
