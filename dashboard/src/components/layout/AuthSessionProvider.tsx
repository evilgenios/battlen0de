'use client';

import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { SWRConfig } from 'swr';
import { getMe } from '@/lib/api/auth';
import type { MeResponse } from '@/lib/api/types';
import { ToastProvider } from '@/components/ui/Toast';

const AUTH_CHANGE = 'warpath-auth-change';
const PUBLIC_ROUTES = new Set(['/', '/terms', '/privacy', '/refunds']);
interface AuthState { user?: MeResponse; isLoading: boolean }
const AuthContext = createContext({
  user: undefined as MeResponse | undefined,
  isLoading: true,
  isAuthenticated: false,
  unauthenticated: false,
  refresh: async (): Promise<void> => {},
  clear: () => {},
});

function SessionCache({ children }: { children: React.ReactNode }) {
  const [cache] = useState(() => new Map());
  useEffect(() => () => cache.clear(), [cache]);
  return <SWRConfig value={{ provider: () => cache }}><ToastProvider>{children}</ToastProvider></SWRConfig>;
}

/** Auth lives outside the private SWR provider. Every website session gets
 * a new map AND component tree, including account selection/forms/toasts.
 * Late responses can only reach the detached old map, never a new user's.
 */
export function AuthSessionProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isPublicRoute = PUBLIC_ROUTES.has(pathname);
  const [state, setState] = useState<AuthState>({ isLoading: !isPublicRoute });
  const generation = useRef(0);
  const probe = useCallback(async () => {
    const request = ++generation.current;
    try {
      const user = await getMe();
      if (generation.current === request) setState({ user, isLoading: false });
    } catch {
      if (generation.current === request) setState({ isLoading: false });
    }
  }, []);
  const clear = useCallback(() => {
    generation.current++;
    setState({ isLoading: false });
  }, []);
  const refresh = useCallback(async () => {
    clear();
    // Broadcast no identity or credentials; other tabs discard their state.
    try { localStorage.setItem(AUTH_CHANGE, String(Date.now())); } catch { /* storage may be disabled */ }
    await probe();
  }, [clear, probe]);
  useEffect(() => {
    let mounted = true;
    const requestGeneration = generation;

    if (isPublicRoute) {
      requestGeneration.current++;
      queueMicrotask(() => { if (mounted) setState({ isLoading: false }); });
      return () => {
        mounted = false;
        requestGeneration.current++;
      };
    }

    queueMicrotask(() => {
      if (!mounted) return;
      setState((current) => current.user ? current : { isLoading: true });
      void probe();
    });
    const storage = (event: StorageEvent) => {
      if (event.key === AUTH_CHANGE) { clear(); void probe(); }
    };
    const expired = () => clear();
    const focus = () => { void probe(); };
    window.addEventListener('storage', storage);
    window.addEventListener('warpath-auth-expired', expired);
    window.addEventListener('focus', focus);
    return () => {
      mounted = false;
      requestGeneration.current++;
      window.removeEventListener('storage', storage);
      window.removeEventListener('warpath-auth-expired', expired);
      window.removeEventListener('focus', focus);
    };
  }, [clear, probe, isPublicRoute]);
  const logoutClear = useCallback(() => {
    clear();
    try { localStorage.setItem(AUTH_CHANGE, String(Date.now())); } catch { /* storage may be disabled */ }
  }, [clear]);
  const key = state.user ? `${state.user.user_id}:${state.user.session_key}:${state.user.role}` : 'anonymous';
  return (
    <AuthContext.Provider value={{ ...state, user: state.user, isAuthenticated: Boolean(state.user),
      unauthenticated: !state.isLoading && !state.user, refresh, clear: logoutClear }}>
      <SessionCache key={key}>{children}</SessionCache>
    </AuthContext.Provider>
  );
}

export function useAuthContext() { return useContext(AuthContext); }
