import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '@/test/test-utils';
import AccountsPage from './page';
import type { Account, SessionStatus } from '@/lib/api/types';

const { getAccountsOverviewMock } = vi.hoisted(() => ({
  getAccountsOverviewMock: vi.fn(),
}));

vi.mock('@/lib/api/accounts', () => ({
  getAccountsOverview: getAccountsOverviewMock,
  listAccounts: vi.fn(),
  getAccount: vi.fn(),
  createAccount: vi.fn(),
  deleteAccount: vi.fn(),
  connectAccount: vi.fn(),
  disconnectAccount: vi.fn(),
  reconnectAccount: vi.fn(),
  getAccountEvents: vi.fn().mockResolvedValue([]),
}));

vi.mock('@/lib/hooks/useHealth', () => ({
  useHealth: () => ({ health: { status: 'ok', database: 'ok' }, isDown: false, isLoading: false }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/accounts',
}));

function makeAccount(overrides: Partial<Account> = {}): Account {
  return {
    id: 'acc-1',
    owner_user_id: 'user-1',
    label: 'Main Account',
    linked_email: null,
    app_uid: 'uid-123',
    profile_uid: null,
    platform: 22,
    device_metadata: {} as Account['device_metadata'],
    linked_at: '2026-01-01T00:00:00Z',
    last_connected_at: null,
    status: 'active',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeStatus(overrides: Partial<SessionStatus> = {}): SessionStatus {
  return { account_id: 'acc-1', db_status: 'active', live: null, ...overrides };
}

beforeEach(() => {
  getAccountsOverviewMock.mockReset();
});

describe('AccountsPage', () => {
  it('shows a loading state before data resolves', async () => {
    let resolveAccounts: (value: Array<{ account: Account; status: SessionStatus }>) => void = () => {};
    getAccountsOverviewMock.mockReturnValue(new Promise((resolve) => { resolveAccounts = resolve; }));

    renderWithProviders(<AccountsPage />);

    // The skeleton rows render immediately, before the fetch resolves.
    expect(document.querySelectorAll('.skeleton').length).toBeGreaterThan(0);

    resolveAccounts([]);
    await waitFor(() => expect(screen.getByText(/no accounts yet/i)).toBeInTheDocument());
  });

  it('renders an empty state when there are no accounts', async () => {
    getAccountsOverviewMock.mockResolvedValue([]);

    renderWithProviders(<AccountsPage />);

    expect(await screen.findByText(/no accounts yet/i)).toBeInTheDocument();
    expect(screen.getAllByText(/add account/i).length).toBeGreaterThan(0);
  });

  it('loads and displays accounts with their live status', async () => {
    getAccountsOverviewMock.mockResolvedValue([{
      account: makeAccount(),
      status: makeStatus({ live: {
        account_id: 'acc-1', label: 'Main Account', state: 'connected', authenticated: true,
        connection_state: 'authenticated', last_error: null, last_connected_at: null,
        started_at: null, retry_count: 0, auth_failure_count: 0,
      } }),
    }]);

    renderWithProviders(<AccountsPage />);

    expect(await screen.findByText('Main Account')).toBeInTheDocument();
    expect(await screen.findByText('Connected')).toBeInTheDocument();
    expect(getAccountsOverviewMock).toHaveBeenCalledOnce();
  });

  it('shows an error state and allows retrying when the accounts fetch fails', async () => {
    getAccountsOverviewMock.mockRejectedValueOnce(new Error('backend unreachable'));
    getAccountsOverviewMock.mockResolvedValueOnce([]);

    renderWithProviders(<AccountsPage />);

    expect(await screen.findByText(/could not load accounts/i)).toBeInTheDocument();

    screen.getByRole('button', { name: /try again/i }).click();

    await waitFor(() => expect(screen.getByText(/no accounts yet/i)).toBeInTheDocument());
  });
});
