vi.mock('@/lib/hooks/useAuthSession', () => ({ useAuthSession: () => ({ user: { role: 'admin' } }) }));
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { MassDeployControl } from './MassDeployControl';
import { ApiError } from '@/lib/api/client';

const { massDeployMock, massCancelMock } = vi.hoisted(() => ({ massDeployMock: vi.fn(), massCancelMock: vi.fn() }));

vi.mock('@/lib/api/actions', () => ({ massDeploy: massDeployMock, massCancel: massCancelMock }));

beforeEach(() => {
  massDeployMock.mockReset();
  massCancelMock.mockReset().mockResolvedValue({ cancelled: false, detail: 'no mass deployment is currently running' });
});

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/army group id/i), '12345');
  await user.type(screen.getByLabelText(/target player uid/i), '67890');
}

describe('MassDeployControl', () => {
  it('defaults to dry run and sends one request per click', async () => {
    massDeployMock.mockResolvedValue({
      execute: false, ag_id: '12345', player_uid: '67890', army_ids: 'auto', group_type: 'auto',
      results: [{ account_id: 'acc-1', label: 'Acc 1', teleport: 'skipped (dry run)', ag: 'skipped (dry run)', error: null }],
      complete_count: 0, total_count: 1,
    });
    const user = userEvent.setup();
    renderWithProviders(<MassDeployControl accountId="acc-1" connected />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /preview \(dry run\)/i }));

    await waitFor(() => expect(massDeployMock).toHaveBeenCalledTimes(1));
    expect(massDeployMock).toHaveBeenCalledWith(
      expect.objectContaining({ account_ids: ['acc-1'], execute: false, ag_id: '12345', player_uid: '67890' }),
    );
    expect(await screen.findByText(/dry run — no game requests were sent/i)).toBeInTheDocument();
  });

  it('requires an explicit confirmation before execute actually runs', async () => {
    massDeployMock.mockResolvedValue({
      execute: true, ag_id: '12345', player_uid: '67890', army_ids: 'auto', group_type: 'auto',
      results: [{ account_id: 'acc-1', label: 'Acc 1', teleport: 'success', ag: 'success', error: null }],
      complete_count: 1, total_count: 1,
    });
    const user = userEvent.setup();
    renderWithProviders(<MassDeployControl accountId="acc-1" connected />);

    await fillRequiredFields(user);
    await user.click(screen.getByLabelText(/execute/i));
    await user.click(screen.getByRole('button', { name: /^run$/i }));

    // Clicking Run opens a confirmation dialog — the real request must not
    // have fired yet.
    expect(await screen.findByText(/execute mass deploy/i)).toBeInTheDocument();
    expect(massDeployMock).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: /^execute$/i }));

    expect(await screen.findByText(/1\/1 fully completed/i)).toBeInTheDocument();
    expect(screen.getByText(/teleport: success; AG: success/i)).toBeInTheDocument();
    expect(massDeployMock).toHaveBeenCalledTimes(1);
  });

  it('lets a user cancel the confirmation dialog without running anything', async () => {
    const user = userEvent.setup();
    renderWithProviders(<MassDeployControl accountId="acc-1" connected />);

    await fillRequiredFields(user);
    await user.click(screen.getByLabelText(/execute/i));
    await user.click(screen.getByRole('button', { name: /^run$/i }));
    await screen.findByText(/execute mass deploy/i);

    await user.click(screen.getByRole('button', { name: /^cancel$/i }));

    expect(screen.queryByText(/execute mass deploy/i)).not.toBeInTheDocument();
    expect(massDeployMock).not.toHaveBeenCalled();
  });

  it('signals a cancellation request via the Cancel running deployment button', async () => {
    massCancelMock.mockResolvedValue({ cancelled: true, detail: 'cancellation requested; no further accounts will start' });
    const user = userEvent.setup();
    renderWithProviders(<MassDeployControl accountId="acc-1" connected />);

    await user.click(screen.getByRole('button', { name: /cancel running deployment/i }));

    await waitFor(() => expect(massCancelMock).toHaveBeenCalledTimes(1));
  });

  it('renders errors cleanly without crashing', async () => {
    massDeployMock.mockRejectedValue(new ApiError(422, 'ag_id must be a positive whole number.'));
    const user = userEvent.setup();
    renderWithProviders(<MassDeployControl accountId="acc-1" connected />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /preview \(dry run\)/i }));

    expect(await screen.findByText(/ag_id must be a positive whole number/i)).toBeInTheDocument();
  });

  it('is disabled when the account is not connected', () => {
    renderWithProviders(<MassDeployControl accountId="acc-1" connected={false} />);
    expect(screen.getByRole('button', { name: /preview \(dry run\)/i })).toBeDisabled();
  });
});
