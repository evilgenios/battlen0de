import useSWR from 'swr';
import { getAccountStatus } from '@/lib/api/accounts';
import type { SessionStatus } from '@/lib/api/types';

/** Faster than useAccounts' interval: this is the live connection state
 * (connecting/connected/reconnecting/...) that a control panel needs to
 * feel responsive right after Connect/Disconnect/Reconnect. */
const REFRESH_INTERVAL_MS = 4_000;

export function useAccountStatus(id: string | undefined, options: { enabled?: boolean } = {}) {
  const enabled = options.enabled ?? true;
  const { data, error, isLoading, mutate } = useSWR<SessionStatus>(
    id && enabled ? ['account-status', id] : null,
    () => getAccountStatus(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS, revalidateOnFocus: true },
  );

  return {
    status: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
