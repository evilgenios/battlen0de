import useSWR from 'swr';
import { getAccountStatus, getAccountsOverview, listAccounts } from '@/lib/api/accounts';
import { ApiError } from '@/lib/api/client';
import type { Account, SessionStatus } from '@/lib/api/types';

export interface AccountWithStatus {
  account: Account;
  status: SessionStatus | null;
}

const REFRESH_INTERVAL_MS = 8_000;

async function fetchOverview(): Promise<AccountWithStatus[]> {
  try {
    return await getAccountsOverview();
  } catch (error) {
    if (!(error instanceof ApiError) || ![404, 422].includes(error.status)) throw error;
    // Safe rolling-deploy fallback: the previous backend resolves the new
    // static path as missing (or as a UUID validation error).
    const accounts = await listAccounts();
    return Promise.all(
      accounts.map(async (account): Promise<AccountWithStatus> => {
        try {
          return { account, status: await getAccountStatus(account.id) };
        } catch {
          return { account, status: null };
        }
      }),
    );
  }
}

/** New backends return all owner-scoped accounts + live state in one HTTP
 * response. The legacy fan-out path remains only as a deployment fallback
 * and disappears automatically once /accounts/overview is available. */
export function useAccountsOverview() {
  const { data, error, isLoading, mutate } = useSWR<AccountWithStatus[]>(
    'accounts-overview',
    fetchOverview,
    { refreshInterval: REFRESH_INTERVAL_MS, revalidateOnFocus: true },
  );

  return {
    rows: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}

export interface AccountOverviewStats {
  total: number;
  connected: number;
  disconnected: number;
  errors: number;
}

export function summarizeOverview(rows: AccountWithStatus[] | undefined): AccountOverviewStats {
  if (!rows) return { total: 0, connected: 0, disconnected: 0, errors: 0 };
  let connected = 0;
  let errors = 0;
  for (const row of rows) {
    const state = row.status?.live?.state;
    if (state === 'connected') connected += 1;
    else if (state === 'failed' || state === 'restricted') errors += 1;
  }
  return {
    total: rows.length,
    connected,
    errors,
    disconnected: rows.length - connected - errors,
  };
}
