'use client';

import { useEffect, useMemo, useState } from 'react';
import { Boxes, ChevronDown, PackageCheck, RefreshCw } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { ErrorState } from '@/components/ui/ErrorState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useProduction } from '@/lib/hooks/useIntel';
import { formatCountdown } from '@/lib/utils/format';
import type { ProductionLineInfo } from '@/lib/api/types';

interface AmountSummary {
  explicitQuantity: number;
  implicitEntries: number;
}

interface ProductionItemSummary extends AmountSummary {
  itemTypeId: string;
  ready: AmountSummary;
  active: AmountSummary;
  queued: AmountSummary;
  nextEnd: number | null;
  finalEnd: number | null;
}

interface ProductionLineSummary {
  buildingId: number;
  lineId: number;
  items: ProductionItemSummary[];
  readyEntries: number;
  activeEntries: number;
  queuedEntries: number;
}

function addAmount(target: AmountSummary, cell: ProductionLineInfo) {
  if (cell.quantity != null) {
    target.explicitQuantity += cell.quantity;
  } else {
    target.implicitEntries += 1;
  }
}

function formatAmount(amount: AmountSummary): string | null {
  const parts: string[] = [];
  if (amount.explicitQuantity > 0) {
    parts.push(`${amount.explicitQuantity.toLocaleString()}×`);
  }
  if (amount.implicitEntries > 0) {
    parts.push(
      `${amount.implicitEntries} queue ${amount.implicitEntries === 1 ? 'entry' : 'entries'}`,
    );
  }
  return parts.length ? parts.join(' + ') : null;
}

function summarizeProduction(
  cells: ProductionLineInfo[],
  nowSeconds: number,
): ProductionLineSummary[] {
  const lineMap = new Map<string, ProductionLineSummary & {
    itemMap: Map<string, ProductionItemSummary>;
  }>();

  for (const cell of cells) {
    const lineKey = `${cell.building_id}:${cell.line_id}`;
    let line = lineMap.get(lineKey);
    if (!line) {
      line = {
        buildingId: cell.building_id,
        lineId: cell.line_id,
        items: [],
        itemMap: new Map(),
        readyEntries: 0,
        activeEntries: 0,
        queuedEntries: 0,
      };
      lineMap.set(lineKey, line);
    }

    const itemTypeId = cell.item_type_id || 'Unknown item';
    let item = line.itemMap.get(itemTypeId);
    if (!item) {
      item = {
        itemTypeId,
        explicitQuantity: 0,
        implicitEntries: 0,
        ready: { explicitQuantity: 0, implicitEntries: 0 },
        active: { explicitQuantity: 0, implicitEntries: 0 },
        queued: { explicitQuantity: 0, implicitEntries: 0 },
        nextEnd: null,
        finalEnd: null,
      };
      line.itemMap.set(itemTypeId, item);
    }

    addAmount(item, cell);

    const status = cell.status.toLowerCase();
    const readyByStatus = status.includes('ready') || status.includes('finish');
    const readyByTime = cell.end_time != null && cell.end_time <= nowSeconds;
    const activeByTime = cell.end_time != null && cell.end_time > nowSeconds;

    if (readyByStatus || readyByTime) {
      line.readyEntries += 1;
      addAmount(item.ready, cell);
    } else if (activeByTime) {
      line.activeEntries += 1;
      addAmount(item.active, cell);
      item.nextEnd = item.nextEnd == null
        ? cell.end_time!
        : Math.min(item.nextEnd, cell.end_time!);
      item.finalEnd = item.finalEnd == null
        ? cell.end_time!
        : Math.max(item.finalEnd, cell.end_time!);
    } else {
      line.queuedEntries += 1;
      addAmount(item.queued, cell);
    }
  }

  return [...lineMap.values()]
    .map(({ itemMap, ...line }) => ({
      ...line,
      items: [...itemMap.values()].sort((a, b) =>
        a.itemTypeId.localeCompare(b.itemTypeId)),
    }))
    .sort((a, b) =>
      a.buildingId - b.buildingId || a.lineId - b.lineId);
}

function ItemSummaryRow({
  item,
}: {
  item: ProductionItemSummary;
}) {
  const total = formatAmount(item);
  const ready = formatAmount(item.ready);
  const active = formatAmount(item.active);
  const queued = formatAmount(item.queued);

  return (
    <div className="border-t border-border/55 px-4 py-3 first:border-t-0">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-foreground">
            {item.itemTypeId}
          </p>
          <p className="mt-1 text-[10px] text-muted-foreground">
            {total ?? 'Quantity not reported'}
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          {ready && <Badge tone="success">{ready} ready to claim</Badge>}
          {active && <Badge tone="info">{active} producing</Badge>}
          {queued && <Badge tone="warning">{queued} queued</Badge>}
        </div>
      </div>

      {item.nextEnd != null && (
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-muted-foreground">
          <span>
            Next ready <strong className="text-foreground">{formatCountdown(item.nextEnd)}</strong>
          </span>
          {item.finalEnd != null && item.finalEnd !== item.nextEnd && (
            <span>
              Queue clear <strong className="text-foreground">{formatCountdown(item.finalEnd)}</strong>
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function ProductionPanel({
  accountId,
  connected,
}: {
  accountId: string;
  connected: boolean;
}) {
  const { lines, error, isLoading, refresh } = useProduction(accountId, connected);
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!open || !connected) return;
    const interval = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [open, connected]);

  const summaries = useMemo(
    () => summarizeProduction(lines, now / 1000),
    [lines, now],
  );

  const readyEntries = summaries.reduce((sum, line) => sum + line.readyEntries, 0);
  const activeEntries = summaries.reduce((sum, line) => sum + line.activeEntries, 0);
  const queuedEntries = summaries.reduce((sum, line) => sum + line.queuedEntries, 0);

  return (
    <section className="premium-panel overflow-hidden rounded-2xl">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="group flex w-full items-center gap-4 px-4 py-4 text-left transition-colors hover:bg-surface-muted/25 sm:px-5"
      >
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-amber-400/20 bg-amber-400/8 text-amber-500 dark:text-amber-300">
          <Boxes className="h-[18px] w-[18px]" />
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-foreground">Production</span>
            {!connected && <Badge tone="neutral">Offline</Badge>}
            {connected && summaries.length > 0 && (
              <Badge tone="info">
                {summaries.length} line{summaries.length === 1 ? '' : 's'}
              </Badge>
            )}
          </span>
          <span className="mt-1 block text-xs text-muted-foreground">
            {connected
              ? summaries.length
                ? `${activeEntries} producing · ${readyEntries} ready to claim · ${queuedEntries} queued`
                : isLoading
                  ? 'Loading production state…'
                  : 'No production queues currently reported.'
              : 'Connect the account to load production.'}
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
          {!connected ? (
            <div className="px-5 py-6 text-sm text-muted-foreground">
              Connect this account to inspect production.
            </div>
          ) : error ? (
            <div className="p-5">
              <ErrorState
                error={error}
                onRetry={() => refresh()}
                title="Could not load production"
              />
            </div>
          ) : isLoading && lines.length === 0 ? (
            <div className="space-y-2 p-5">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : summaries.length === 0 ? (
            <div className="flex items-center gap-3 px-5 py-6 text-sm text-muted-foreground">
              <PackageCheck className="h-4 w-4 text-amber-400" />
              No production lines are currently reported.
            </div>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/70 px-4 py-3 sm:px-5">
                <div>
                  <p className="text-xs font-semibold text-foreground">
                    Production lines
                  </p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    Repeated protocol cells are grouped by line and item. “×” is shown only when Warpath reports an explicit quantity.
                  </p>
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

              <div className="max-h-[720px] space-y-3 overflow-y-auto overscroll-contain p-3 sm:p-4">
                {summaries.map((line) => (
                  <div
                    key={`${line.buildingId}-${line.lineId}`}
                    className="overflow-hidden rounded-xl border border-border/70 bg-surface/35"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 bg-surface-muted/30 px-4 py-3">
                      <div>
                        <p className="text-sm font-semibold text-foreground">
                          Line {line.lineId}
                        </p>
                        <p className="mt-0.5 font-mono text-[10px] text-muted-foreground">
                          Building #{line.buildingId}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {line.readyEntries > 0 && (
                          <Badge tone="success">{line.readyEntries} ready</Badge>
                        )}
                        {line.activeEntries > 0 && (
                          <Badge tone="info">{line.activeEntries} producing</Badge>
                        )}
                        {line.queuedEntries > 0 && (
                          <Badge tone="warning">{line.queuedEntries} queued</Badge>
                        )}
                      </div>
                    </div>

                    <div>
                      {line.items.map((item) => (
                        <ItemSummaryRow
                          key={item.itemTypeId}
                          item={item}
                        />
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
