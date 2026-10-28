import useSWR from 'swr';
import { getHealth } from '@/lib/api/health';
import type { HealthStatus } from '@/lib/api/types';

const REFRESH_INTERVAL_MS = 15_000;

export function useHealth() {
  const { data, error, isLoading } = useSWR<HealthStatus>('health', getHealth, {
    refreshInterval: REFRESH_INTERVAL_MS,
    revalidateOnFocus: true,
    shouldRetryOnError: true,
    errorRetryInterval: 5_000,
  });

  return {
    health: data,
    // A thrown ApiError (e.g. 503 from /health itself) means "down", same
    // as a network failure — both are just "not healthy" to the UI.
    isDown: Boolean(error),
    isLoading,
  };
}
