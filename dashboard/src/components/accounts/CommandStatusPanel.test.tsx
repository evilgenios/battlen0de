import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { CommandStatusPanel } from './CommandStatusPanel';
import { renderWithProviders } from '@/test/test-utils';
import { AuthSessionProvider } from '@/components/layout/AuthSessionProvider';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import type { CommandStatus, MeResponse } from '@/lib/api/types';

const mocks = vi.hoisted(() => ({ report: vi.fn(), me: vi.fn(), farm: vi.fn(), collect: vi.fn() }));
vi.mock('@/lib/api/actions', () => ({ getCommandStatus: mocks.report, farm: mocks.farm, collect: mocks.collect }));
vi.mock('@/lib/api/auth', () => ({ getMe: mocks.me }));
const alice: MeResponse = { user_id: 'alice', session_key: 'a', email: 'alice@example.test', role: 'member', active_sessions: 1 };
const bob: MeResponse = { ...alice, user_id: 'bob', session_key: 'b', email: 'bob@example.test' };
const empty: CommandStatus = { history_scope: 'current_connection_only', history_complete: false, upstream_evidence: 'unverified', observation_id: 'epoch-1', tracking_started_at: 1000, connected: true, active: [], recent: [], recent_dropped: 0, tracked_requests: 0, tracking_limit: 1024 };
function uncertain(truck = 9): CommandStatus {
  return { ...empty, tracked_requests: 1, active: [{ operation_id: 'op-1', kind: 'gather', status: 'uncertain', reason: 'timeout', reservation: 'truck', created_at: 1001, age_seconds: 12, vehicle_id: truck, building_id: null, mine_id: 555 }] };
}
beforeEach(() => { vi.resetAllMocks(); mocks.report.mockResolvedValue(uncertain()); mocks.me.mockResolvedValue(alice); });

it('shows unresolved reservations and updates the read-only report without sending actions', async () => {
  renderWithProviders(<CommandStatusPanel accountId="account-a" />);
  await screen.findByText(/Gather — uncertain · truck 9/);
  expect(screen.getByText(/truck reservation held/)).toBeInTheDocument();
  expect(screen.getByText(/Do not retry an uncertain command/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Update report' }));
  await waitFor(() => expect(mocks.report).toHaveBeenCalledTimes(2));
  expect(mocks.report).toHaveBeenCalledWith('account-a');
  expect(mocks.farm).not.toHaveBeenCalled(); expect(mocks.collect).not.toHaveBeenCalled();
});

it('shows late confirmation while keeping the truck reserved', async () => {
  renderWithProviders(<CommandStatusPanel accountId="account-a" />);
  await screen.findByText(/Gather — uncertain/);
  const confirmed = uncertain(); confirmed.active[0].status = 'confirmed'; confirmed.active[0].reason = 'awaiting_idle_observation';
  mocks.report.mockResolvedValue(confirmed);
  fireEvent.click(screen.getByText('Update report'));
  await screen.findByText(/Gather — confirmed/);
  expect(screen.getByText(/truck held until a subsequent idle observation/)).toBeInTheDocument();
  expect(screen.getByText(/truck reservation held/)).toBeInTheDocument();
});

it('reports lost history after reconnect without claiming earlier commands succeeded', async () => {
  renderWithProviders(<CommandStatusPanel accountId="account-a" />);
  await screen.findByText(/truck reservation held/);
  mocks.report.mockResolvedValue({ ...empty, observation_id: 'epoch-2', connected: false });
  fireEvent.click(screen.getByText('Update report'));
  await screen.findByText('No active reservations observed in this connection.');
  expect(screen.getByText(/Empty results do not establish the outcome of earlier commands/)).toBeInTheDocument();
  expect(screen.queryByText(/truck reservation held/)).not.toBeInTheDocument();
});

it('does not present stale data as current when reporting fails', async () => {
  renderWithProviders(<CommandStatusPanel accountId="account-a" />);
  await screen.findByText(/Gather — uncertain/);
  mocks.report.mockRejectedValue(new Error('report unavailable'));
  fireEvent.click(screen.getByText('Update report'));
  await screen.findByText('Command report unavailable');
  expect(screen.queryByText(/Gather — uncertain/)).not.toBeInTheDocument();
});

it('shows tracking exhaustion and unavailable history explicitly', async () => {
  mocks.report.mockResolvedValue({ ...empty, observation_id: null, tracked_requests: 1024, recent_dropped: 10 });
  renderWithProviders(<CommandStatusPanel accountId="account-a" />);
  await screen.findByText('No connection history is available.');
  expect(screen.getByRole('alert')).toHaveTextContent('Tracking capacity reached');
  expect(screen.getByText(/10 older completed observations omitted/)).toBeInTheDocument();
});

function IdentityHarness() {
  const { user, refresh, clear } = useAuthSession();
  return <><button onClick={() => void refresh()}>Change identity</button><button onClick={clear}>Clear identity</button>
    {user && <CommandStatusPanel accountId="same-account-key" />}</>;
}
it('uses private session caches and ignores late reports from the previous identity', async () => {
  let finish!: (value: CommandStatus) => void;
  mocks.report.mockImplementationOnce(() => new Promise<CommandStatus>(resolve => { finish = resolve; }));
  render(<AuthSessionProvider><IdentityHarness /></AuthSessionProvider>);
  await waitFor(() => expect(mocks.report).toHaveBeenCalledOnce());
  mocks.me.mockResolvedValue(bob); mocks.report.mockResolvedValue(uncertain(22));
  fireEvent.click(screen.getByText('Change identity'));
  await screen.findByText(/truck 22/);
  await act(async () => finish(uncertain(9)));
  expect(screen.queryByText(/truck 9/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByText('Clear identity'));
  expect(screen.queryByText(/truck 22/)).not.toBeInTheDocument();
});
