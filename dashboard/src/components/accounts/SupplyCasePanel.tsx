'use client';

import { useState } from 'react';
import { ChevronDown, PackageOpen } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { ErrorState } from '@/components/ui/ErrorState';
import { useSupplyCases } from '@/lib/hooks/useIntel';

export function SupplyCasePanel({ accountId }: { accountId: string }) {
  const [open, setOpen] = useState(false);
  const { supply, error, isLoading, refresh } = useSupplyCases(accountId, true);

  return (
    <section className="premium-panel overflow-hidden rounded-2xl">
      <button type="button" onClick={() => setOpen((value) => !value)} aria-expanded={open}
        className="group flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-surface-muted/25 sm:px-5">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-warning/20 bg-warning/8 text-warning">
          <PackageOpen className="h-[18px] w-[18px]" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">Supply / Campaign Resupply</span>
            <Badge tone="info">evidence view</Badge>
            <Badge tone={supply?.campaign_mapping_state === 'complete' ? 'success' : 'warning'}>
              campaign {supply?.campaign_mapping_state?.replace(/_/g, ' ') ?? 'unmapped'}
            </Badge>
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            Raw supply-case state, last confirmed reply, and Campaign Resupply mapper progress.
          </span>
        </span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="border-t border-border/70 p-4 sm:p-5">
          {error ? (
            <ErrorState error={error} onRetry={() => refresh()} title="Could not load supply state" />
          ) : isLoading && !supply ? (
            <p className="text-xs text-muted-foreground">Loading supply state…</p>
          ) : (
            <>
              <div className="flex flex-wrap gap-2">
                {(supply?.cases ?? []).map((entry) => (
                  <Badge key={entry.key} tone="neutral">{entry.key}: {entry.value}</Badge>
                ))}
                {(supply?.cases ?? []).length === 0 && (
                  <span className="text-xs text-muted-foreground">No supply-case key/value state has been observed.</span>
                )}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <div className="data-chip rounded-xl p-3">
                  <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Campaign task</p>
                  <p className="mt-1 font-mono text-xs text-foreground">{supply?.campaign_task_id ? `#${supply.campaign_task_id}` : 'unmapped'}</p>
                </div>
                <div className="data-chip rounded-xl p-3">
                  <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Observed num</p>
                  <p className="mt-1 text-xs font-semibold text-foreground">{supply?.campaign_num ?? '—'}</p>
                </div>
                <div className="data-chip rounded-xl p-3">
                  <p className="text-[9px] uppercase tracking-[0.12em] text-muted-foreground">Execution</p>
                  <p className="mt-1 text-xs font-semibold text-warning">claim / rush locked</p>
                </div>
              </div>
              {supply?.last_reply && (
                <div className="mt-4 rounded-xl border border-border/70 bg-surface/35 p-3">
                  <p className="text-xs font-semibold text-foreground">Last confirmed supply-case reply</p>
                  <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all font-mono text-[10px] leading-5 text-muted-foreground">
                    {JSON.stringify(supply.last_reply, null, 2)}
                  </pre>
                </div>
              )}
              <p className="mt-4 text-[10px] leading-5 text-muted-foreground">{supply?.limitation}</p>
            </>
          )}
        </div>
      )}
    </section>
  );
}
