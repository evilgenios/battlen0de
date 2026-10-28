import useSWR from 'swr';
import { listAccounts } from '@/lib/api/accounts';
import type { Account } from '@/lib/api/types';

/** Polling is the agreed approach for this version (no WebSocket support on
 * the backend) — 15s is frequent enough for a control panel without
 * hammering the proxy/backend for data that rarely changes (account rows
 * themselves, not their live connection state — see useAccountStatus for
 * that faster-moving data). */
const REFRESH_INTERVAL_MS = 15_000;

export function useAccounts() {
  const { data, error, isLoading, mutate } = useSWR<Account[]>('accounts', listAccounts, {
    refreshInterval: REFRESH_INTERVAL_MS,
    revalidateOnFocus: true,
  });

  return {
    accounts: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
