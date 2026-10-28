import useSWR from 'swr';
import { getAccountEvents, getAllEvents, listAccounts } from '@/lib/api/accounts';
import { ApiError } from '@/lib/api/client';
import type { Account, AccountEvent } from '@/lib/api/types';

export interface EventWithAccount {
  event: AccountEvent;
  accountLabel: string | null;
}

const REFRESH_INTERVAL_MS = 15_000;

async function fetchAggregateEvents(limitPerAccount: number, maxTotal: number): Promise<EventWithAccount[]> {
  const backendLimit = Math.min(200, Math.max(limitPerAccount, maxTotal));
  try {
    const rows = await getAllEvents(backendLimit);
    return rows.slice(0, maxTotal).map((row) => ({
      event: row.event,
      accountLabel: row.account_label,
    }));
  } catch (error) {
    if (!(error instanceof ApiError) || ![404, 422].includes(error.status)) throw error;
    // Rolling-deploy compatibility for the previous backend only.
    const accounts = await listAccounts();
    const labelById = new Map<string, string>(accounts.map((account: Account) => [account.id, account.label]));
    const perAccount = await Promise.all(
      accounts.map((account) => getAccountEvents(account.id, limitPerAccount).catch(() => [] as AccountEvent[])),
    );
    const merged = perAccount.flat().map((event) => ({
      event,
      accountLabel: event.account_id ? labelById.get(event.account_id) ?? null : null,
    }));
    merged.sort((a, b) => Date.parse(b.event.created_at) - Date.parse(a.event.created_at));
    return merged.slice(0, maxTotal);
  }
}

/** New backends aggregate recent owner-scoped events in one request.
 * Client-side fan-out is retained only for a safe frontend-first rollout. */
export function useAllEvents(limitPerAccount = 25, maxTotal = 100) {
  const { data, error, isLoading, mutate } = useSWR<EventWithAccount[]>(
    ['all-events', limitPerAccount, maxTotal],
    () => fetchAggregateEvents(limitPerAccount, maxTotal),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );

  return {
    events: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
