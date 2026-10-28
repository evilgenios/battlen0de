import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { ConnectionControls } from './ConnectionControls';

const { connectMock, disconnectMock, reconnectMock } = vi.hoisted(() => ({
  connectMock: vi.fn(),
  disconnectMock: vi.fn(),
  reconnectMock: vi.fn(),
}));

vi.mock('@/lib/api/accounts', () => ({
  connectAccount: connectMock,
  disconnectAccount: disconnectMock,
  reconnectAccount: reconnectMock,
}));

beforeEach(() => {
  connectMock.mockReset().mockResolvedValue({});
  disconnectMock.mockReset().mockResolvedValue({});
  reconnectMock.mockReset().mockResolvedValue({});
});

describe('ConnectionControls', () => {
  it('only enables Connect when there is no live session yet', () => {
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState={null} />);

    expect(screen.getByRole('button', { name: /^connect$/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /disconnect/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /reconnect/i })).toBeDisabled();
  });

  it('only enables Disconnect and Reconnect when the account is connected', () => {
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState="connected" />);

    expect(screen.getByRole('button', { name: /^connect$/i })).toBeDisabled();
    expect(screen.getByRole('button', { name: /disconnect/i })).toBeEnabled();
    expect(screen.getByRole('button', { name: /reconnect/i })).toBeEnabled();
  });

  it('enables Connect again after the account has stopped/failed/been restricted', () => {
    for (const state of ['stopped', 'failed', 'restricted'] as const) {
      const { unmount } = renderWithProviders(<ConnectionControls accountId="acc-1" liveState={state} />);
      expect(screen.getByRole('button', { name: /^connect$/i })).toBeEnabled();
      unmount();
    }
  });

  it('calls connectAccount when Connect is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState={null} />);

    await user.click(screen.getByRole('button', { name: /^connect$/i }));

    await waitFor(() => expect(connectMock).toHaveBeenCalledWith('acc-1'));
  });

  it('calls disconnectAccount when Disconnect is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState="connected" />);

    await user.click(screen.getByRole('button', { name: /disconnect/i }));

    await waitFor(() => expect(disconnectMock).toHaveBeenCalledWith('acc-1'));
  });

  it('calls reconnectAccount when Reconnect is clicked', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState="connected" />);

    await user.click(screen.getByRole('button', { name: /reconnect/i }));

    await waitFor(() => expect(reconnectMock).toHaveBeenCalledWith('acc-1'));
  });

  it('shows an error toast and stays usable when a connect call fails', async () => {
    connectMock.mockRejectedValue(new Error('max_concurrent_sessions reached'));
    const user = userEvent.setup();
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState={null} />);

    await user.click(screen.getByRole('button', { name: /^connect$/i }));

    expect(await screen.findByText(/connect failed/i)).toBeInTheDocument();
    expect(await screen.findByText(/max_concurrent_sessions reached/i)).toBeInTheDocument();
  });

  it('prevents duplicate submissions while an action is in flight', async () => {
    let resolveConnect: (value: unknown) => void = () => {};
    connectMock.mockReturnValue(new Promise((resolve) => { resolveConnect = resolve; }));
    const user = userEvent.setup();
    renderWithProviders(<ConnectionControls accountId="acc-1" liveState={null} />);

    const connectButton = screen.getByRole('button', { name: /^connect$/i });
    await user.click(connectButton);
    await user.click(connectButton);
    await user.click(connectButton);

    resolveConnect({});
    await waitFor(() => expect(connectMock).toHaveBeenCalledTimes(1));
  });
});
