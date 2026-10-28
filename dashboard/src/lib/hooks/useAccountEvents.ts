import useSWR from 'swr';
import { getAccountEvents } from '@/lib/api/accounts';
import type { AccountEvent } from '@/lib/api/types';

export function useAccountEvents(id: string | undefined, limit = 50) {
  const { data, error, isLoading, mutate } = useSWR<AccountEvent[]>(
    id ? ['account-events', id, limit] : null,
    () => getAccountEvents(id as string, limit),
    { refreshInterval: 10_000 },
  );

  return {
    events: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
