import useSWR from 'swr';
import { getAccountStatus, listAccounts } from '@/lib/api/accounts';
import { getAccountSummary, getActiveActions, getConquestGuard } from '@/lib/api/intel';
import type { Account, ActiveActionInfo, ConquestGuardStatus, SessionStatus, AccountSummaryInfo } from '@/lib/api/types';

export interface OperationsRow {
  account: Account;
  status: SessionStatus | null;
  summary: AccountSummaryInfo | null;
  activeActions: ActiveActionInfo[];
  conquestGuard: ConquestGuardStatus | null;
}

const REFRESH_INTERVAL_MS = 8_000;

/** The /operations page's single aggregation point: GET /accounts, then per
 * account status + summary + active-actions + conquest-guard in parallel —
 * the same N+1 fan-out pattern useAccountsOverview already uses for the
 * Dashboard/Accounts pages (see that file's docstring), just with the extra
 * calls this page needs. Every value here is read from the SAME already-
 * existing endpoints (no new backend route, no duplicated protocol
 * parsing) — active-actions in particular reuses the exact
 * ActiveActionInfo model the Active Actions tab uses. */
export function useOperationsOverview() {
  const { data, error, isLoading, mutate } = useSWR<OperationsRow[]>(
    'operations-overview',
    async () => {
      const accounts = await listAccounts();
      return Promise.all(
        accounts.map(async (account): Promise<OperationsRow> => {
          const [status, summary, activeActions, conquestGuard] = await Promise.all([
            getAccountStatus(account.id).catch(() => null),
            getAccountSummary(account.id).catch(() => null),
            getActiveActions(account.id).catch(() => [] as ActiveActionInfo[]),
            getConquestGuard(account.id).catch(() => null),
          ]);
          return { account, status, summary, activeActions, conquestGuard };
        }),
      );
    },
    { refreshInterval: REFRESH_INTERVAL_MS, revalidateOnFocus: true },
  );

  return { rows: data, isLoading, error: error as Error | undefined, refresh: mutate };
}

const VEHICLE_TYPES = new Set([
  'vehicle_traveling', 'vehicle_gathering', 'vehicle_returning',
  'vehicle_repairing', 'vehicle_building', 'vehicle_demolishing', 'vehicle_delivering',
]);

export function countByCategory(activities: ActiveActionInfo[]) {
  let vehicles = 0;
  let production = 0;
  let officerTasks = 0;
  for (const a of activities) {
    if (VEHICLE_TYPES.has(a.activity_type)) vehicles += 1;
    else if (a.activity_type === 'production') production += 1;
    else if (a.activity_type === 'officer_task') officerTasks += 1;
  }
  return { vehicles, production, officerTasks };
}

/** The soonest real end_time across every activity that has one — the
 * account's "next known event", not a fabricated countdown. */
export function nextEventEndTime(activities: ActiveActionInfo[]): number | null {
  const times = activities.map((a) => a.end_time).filter((t): t is number => t != null && t > Date.now() / 1000);
  return times.length ? Math.min(...times) : null;
}
