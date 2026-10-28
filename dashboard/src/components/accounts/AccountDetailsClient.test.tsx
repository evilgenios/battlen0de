import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { AccountDetailsClient } from './AccountDetailsClient';
import type { Account, AccountEvent, SessionStatus } from '@/lib/api/types';

/**
 * Regression coverage for a live incident: the dashboard kept showing a
 * stale "missing device metadata" 422 error for an account that had
 * actually become connected. The proxy and backend both turned out to be
 * correct once inspected in isolation; what these tests pin down is the
 * frontend's half of the guarantee — that the account detail page's
 * connection state and error box always reflect the LATEST polled
 * /accounts/{id}/status response, never a stale error left over from an
 * earlier failed connect attempt or an earlier poll.
 */

const { getAccountMock, getAccountStatusMock, getAccountEventsMock, connectAccountMock } = vi.hoisted(() => ({
  getAccountMock: vi.fn(),
  getAccountStatusMock: vi.fn(),
  getAccountEventsMock: vi.fn(),
  connectAccountMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/components/accounts/ObservationAccessControl', () => ({
  ObservationAccessControl: () => null,
}));

vi.mock('@/components/accounts/BattleReportAnalyzerPanel', () => ({
  BattleReportAnalyzerPanel: () => null,
}));

vi.mock('@/components/accounts/ArmyPresetManagerPanel', () => ({
  ArmyPresetManagerPanel: () => null,
}));

vi.mock('@/components/accounts/SupplyCasePanel', () => ({
  SupplyCasePanel: () => null,
}));

vi.mock('@/lib/api/accounts', () => ({
  getAccount: getAccountMock,
  getAccountStatus: getAccountStatusMock,
  getAccountEvents: getAccountEventsMock,
  connectAccount: connectAccountMock,
  disconnectAccount: vi.fn(),
  reconnectAccount: vi.fn(),
  deleteAccount: vi.fn(),
}));

const ACCOUNT: Account = {
  id: 'acc-1',
  owner_user_id: 'user-1',
  label: 'Bootstrap Account',
  linked_email: null,
  app_uid: '500000123',
  profile_uid: 500000123,
  platform: 22,
  device_metadata: {} as Account['device_metadata'],
  linked_at: '2026-09-10T00:00:00Z',
  last_connected_at: null,
  status: 'active',
  created_at: '2026-09-10T00:00:00Z',
  updated_at: '2026-09-10T00:00:00Z',
};

const EVENTS: AccountEvent[] = [];

function statusWith(overrides: Partial<SessionStatus['live']>): SessionStatus {
  return {
    account_id: 'acc-1',
    db_status: 'active',
    live: overrides === null ? null : {
      account_id: 'acc-1',
      label: 'Bootstrap Account',
      state: 'idle',
      authenticated: false,
      connection_state: 'disconnected',
      last_error: null,
      last_connected_at: null,
      started_at: null,
      retry_count: 0,
      auth_failure_count: 0,
      ...overrides,
    },
  };
}

const FAILED_STATUS = statusWith({
  state: 'failed',
  last_error: "app_id is not set; pack_name is not set; channel_id is not set; app_version is not set; "
    + "package_version is not set; PC credentials require os_type='win' (or 'pc')",
});
const CONNECTING_STATUS = statusWith({ state: 'connecting' });
const CONNECTED_STATUS = statusWith({ state: 'connected', authenticated: true, connection_state: 'authenticated' });

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  getAccountMock.mockReset().mockResolvedValue(ACCOUNT);
  getAccountEventsMock.mockReset().mockResolvedValue(EVENTS);
  getAccountStatusMock.mockReset();
  connectAccountMock.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('AccountDetailsClient — connection state always reflects the latest poll', () => {
  it('shows the failed state and its error message on initial load', async () => {
    getAccountStatusMock.mockResolvedValue(FAILED_STATUS);
    renderWithProviders(<AccountDetailsClient id="acc-1" />);

    expect(await screen.findByText(/app_id is not set/i)).toBeInTheDocument();
  });

  it('replaces a stale failed/422 error with a newer successful connection after connect + polling', async () => {
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    // First poll (page load): failed, with the exact legacy validation
    // error text from the live incident.
    getAccountStatusMock.mockResolvedValueOnce(FAILED_STATUS);
    renderWithProviders(<AccountDetailsClient id="acc-1" />);
    expect(await screen.findByText(/app_id is not set/i)).toBeInTheDocument();

    // The DB credentials get corrected and the account reconnects
    // successfully (this is what the backend fix in _ensure_registered()
    // guarantees no longer replays the stale 422 forever). Every status
    // poll from here on reports connected/authenticated.
    connectAccountMock.mockResolvedValue(CONNECTED_STATUS);
    getAccountStatusMock.mockResolvedValue(CONNECTED_STATUS);
    await user.click(screen.getByRole('button', { name: /^connect$/i }));
    await waitFor(() => expect(connectAccountMock).toHaveBeenCalledWith('acc-1'));

    // The next scheduled poll tick (useAccountStatus's own 4s
    // refreshInterval) is what the UI actually relies on to pick up the
    // new state — the newest data must win outright; the old failed/422
    // message must never reappear once it does.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(4_000);
    });

    await waitFor(() => expect(screen.getAllByText('Connected').length).toBeGreaterThan(0));
    expect(screen.queryByText('Failed')).not.toBeInTheDocument();
    expect(screen.queryByText(/app_id is not set/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/last error/i)).not.toBeInTheDocument();
  });

  it('does not send a second connect request while one is already in flight', async () => {
    getAccountStatusMock.mockResolvedValue(statusWith({ state: 'idle' }));
    let resolveConnect: (value: SessionStatus) => void = () => {};
    connectAccountMock.mockReturnValue(new Promise((resolve) => { resolveConnect = resolve; }));

    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderWithProviders(<AccountDetailsClient id="acc-1" />);

    const connectButton = await screen.findByRole('button', { name: /^connect$/i });
    await user.click(connectButton);
    await user.click(connectButton);
    await user.click(connectButton);

    resolveConnect(CONNECTING_STATUS);
    await waitFor(() => expect(connectAccountMock).toHaveBeenCalledTimes(1));
  });
});
