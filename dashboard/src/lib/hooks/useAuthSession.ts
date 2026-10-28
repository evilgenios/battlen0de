import { useAuthContext } from '@/components/layout/AuthSessionProvider';

/** A single root identity source, outside all private SWR caches. */
export function useAuthSession() {
  return useAuthContext();
}
