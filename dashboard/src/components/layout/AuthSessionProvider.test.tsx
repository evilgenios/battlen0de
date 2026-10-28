import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import useSWR, { useSWRConfig } from 'swr';
import { AuthSessionProvider } from './AuthSessionProvider';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import type { MeResponse } from '@/lib/api/types';
import { LogoutButton } from './LogoutButton';

const mocks = vi.hoisted(() => ({ me: vi.fn(), logout: vi.fn(), push: vi.fn(), refresh: vi.fn(), private: vi.fn(), pathname: vi.fn() }));
vi.mock('@/lib/api/auth', () => ({ getMe: mocks.me, logout: mocks.logout }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mocks.push, refresh: mocks.refresh }), usePathname: () => mocks.pathname() }));

const alice: MeResponse = { user_id: 'alice', session_key: 'session-a', email: 'alice@example.test', role: 'member', active_sessions: 1 };
const bob: MeResponse = { user_id: 'bob', session_key: 'session-b', email: 'bob@example.test', role: 'member', active_sessions: 1 };
const observedCaches: ReturnType<typeof useSWRConfig>['cache'][] = [];
function PrivateAccount() {
  const { cache } = useSWRConfig();
  if (!observedCaches.includes(cache)) observedCaches.push(cache);
  const { data } = useSWR('accounts', () => mocks.private());
  return <div>{data ?? 'waiting for private data'}</div>;
}
function Harness() {
  const { user, refresh, clear } = useAuthSession();
  return <>
    <button onClick={() => void refresh()}>Refresh identity</button>
    <button onClick={clear}>Clear identity</button>
    <div>{user?.email ?? 'anonymous'}</div>
    {user && <><PrivateAccount /><LogoutButton /></>}
  </>;
}
function mount() { return render(<AuthSessionProvider><Harness /></AuthSessionProvider>); }

beforeEach(() => {
  vi.resetAllMocks();
  observedCaches.length = 0;
  mocks.pathname.mockReturnValue('/dashboard');
  mocks.me.mockResolvedValue(alice);
  mocks.private.mockResolvedValue('Alice account telemetry');
  mocks.logout.mockResolvedValue(undefined);
});

describe('private session cache boundaries', () => {
  it('clears auth and private caches on actual logout without refetching the old user', async () => {
    mount();
    await screen.findByText('Alice account telemetry');
    const old = observedCaches[0];
    fireEvent.click(screen.getByRole('button', { name: 'Log out' }));
    await screen.findByText('anonymous');
    expect(screen.queryByText('Alice account telemetry')).not.toBeInTheDocument();
    expect([...old.keys()]).toEqual([]);
    expect(mocks.logout).toHaveBeenCalledOnce();
    expect(mocks.push).toHaveBeenCalledWith('/login');
  });

  it('uses a new cache and never shows Alice data when Bob signs in', async () => {
    mount();
    await screen.findByText('Alice account telemetry');
    const old = observedCaches[0];
    mocks.me.mockResolvedValue(bob);
    mocks.private.mockResolvedValue('Bob account telemetry');
    fireEvent.click(screen.getByText('Refresh identity'));
    await screen.findByText('Bob account telemetry');
    expect(screen.queryByText('Alice account telemetry')).not.toBeInTheDocument();
    expect([...old.keys()]).toEqual([]);
    expect(observedCaches.at(-1)).not.toBe(old);
  });

  it('isolates late SWR replies from the old identity', async () => {
    let finishOld!: (data: string) => void;
    mocks.private.mockImplementationOnce(() => new Promise<string>((resolve) => { finishOld = resolve; }));
    mount();
    await screen.findByText(alice.email);
    await waitFor(() => expect(mocks.private).toHaveBeenCalledOnce());
    mocks.me.mockResolvedValue(bob);
    mocks.private.mockResolvedValue('Bob account telemetry');
    fireEvent.click(screen.getByText('Refresh identity'));
    await screen.findByText('Bob account telemetry');
    await act(async () => finishOld('Alice late secret'));
    expect(screen.queryByText('Alice late secret')).not.toBeInTheDocument();
    expect(screen.getByText('Bob account telemetry')).toBeInTheDocument();
  });

  it('rotates caches for a new session of the same user', async () => {
    mount();
    await screen.findByText('Alice account telemetry');
    const old = observedCaches[0];
    mocks.me.mockResolvedValue({ ...alice, session_key: 'new-session' });
    mocks.private.mockResolvedValue('Fresh telemetry');
    fireEvent(window, new Event('focus'));
    await screen.findByText('Fresh telemetry');
    expect(observedCaches.at(-1)).not.toBe(old);
    expect([...old.keys()]).toEqual([]);
  });

  it('clears private data when an API request reports session expiry', async () => {
    mount();
    await screen.findByText('Alice account telemetry');
    fireEvent(window, new Event('warpath-auth-expired'));
    await screen.findByText('anonymous');
    expect(screen.queryByText('Alice account telemetry')).not.toBeInTheDocument();
  });

  it('handles another tab changing website users', async () => {
    mount();
    await screen.findByText('Alice account telemetry');
    mocks.me.mockResolvedValue(bob);
    mocks.private.mockResolvedValue('Bob account telemetry');
    fireEvent(window, new StorageEvent('storage', { key: 'warpath-auth-change', newValue: '2' }));
    await screen.findByText('Bob account telemetry');
    expect(screen.queryByText('Alice account telemetry')).not.toBeInTheDocument();
  });

  it('does not resurrect identity from an auth response that arrives after logout', async () => {
    let finish!: (user: MeResponse) => void;
    mocks.me.mockImplementationOnce(() => new Promise<MeResponse>((resolve) => { finish = resolve; }));
    mount();
    await waitFor(() => expect(mocks.me).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByText('Clear identity'));
    await act(async () => finish(alice));
    expect(screen.getByText('anonymous')).toBeInTheDocument();
    expect(mocks.private).not.toHaveBeenCalled();
  });
});


describe('public route auth isolation', () => {
  it('does not probe /auth/me on the public marketing homepage', async () => {
    mocks.pathname.mockReturnValue('/');
    mount();
    await screen.findByText('anonymous');
    await waitFor(() => expect(mocks.me).not.toHaveBeenCalled());
  });

  it('does not probe /auth/me on public legal pages', async () => {
    mocks.pathname.mockReturnValue('/terms');
    mount();
    await screen.findByText('anonymous');
    await waitFor(() => expect(mocks.me).not.toHaveBeenCalled());
  });
});
