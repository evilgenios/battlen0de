import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { DeleteAccountButton } from './DeleteAccountButton';

const { deleteAccountMock, pushMock } = vi.hoisted(() => ({
  deleteAccountMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock('@/lib/api/accounts', () => ({
  deleteAccount: deleteAccountMock,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

beforeEach(() => {
  // Matches deleteAccount()'s REAL resolved value for a 204 No Content
  // response (see apiRequest<void> in lib/api/client.ts) — using
  // `undefined` here instead of `null` would have hidden the regression
  // where a successful delete was indistinguishable from a failed one.
  deleteAccountMock.mockReset().mockResolvedValue(null);
  pushMock.mockReset();
});

describe('DeleteAccountButton', () => {
  it('does not delete immediately — a confirmation dialog appears first', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DeleteAccountButton accountId="acc-1" accountLabel="Main Account" />);

    await user.click(screen.getByRole('button', { name: /delete/i }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText(/permanently delete/i)).toBeInTheDocument();
    expect(deleteAccountMock).not.toHaveBeenCalled();
  });

  it('does not delete when the dialog is cancelled', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DeleteAccountButton accountId="acc-1" accountLabel="Main Account" />);

    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(screen.getByRole('button', { name: /^cancel$/i }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(deleteAccountMock).not.toHaveBeenCalled();
  });

  it('deletes the account only after the dialog is confirmed', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DeleteAccountButton accountId="acc-1" accountLabel="Main Account" />);

    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(screen.getByRole('button', { name: /delete account/i }));

    await waitFor(() => expect(deleteAccountMock).toHaveBeenCalledWith('acc-1'));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });

  it('redirects to /accounts after deleting when redirectAfterDelete is set', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <DeleteAccountButton accountId="acc-1" accountLabel="Main Account" redirectAfterDelete />,
    );

    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(screen.getByRole('button', { name: /delete account/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/accounts'));
  });

  it('does not redirect when deletion fails', async () => {
    deleteAccountMock.mockRejectedValue(new Error('account not found'));
    const user = userEvent.setup();
    renderWithProviders(
      <DeleteAccountButton accountId="acc-1" accountLabel="Main Account" redirectAfterDelete />,
    );

    await user.click(screen.getByRole('button', { name: /delete/i }));
    await user.click(screen.getByRole('button', { name: /delete account/i }));

    expect(await screen.findByText(/delete failed/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });
});
