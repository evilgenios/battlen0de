import useSWR from 'swr';
import { getAccount } from '@/lib/api/accounts';
import type { Account } from '@/lib/api/types';

export function useAccount(id: string | undefined) {
  const { data, error, isLoading, mutate } = useSWR<Account>(
    id ? ['account', id] : null,
    () => getAccount(id as string),
  );

  return {
    account: data,
    isLoading,
    error: error as Error | undefined,
    refresh: mutate,
  };
}
