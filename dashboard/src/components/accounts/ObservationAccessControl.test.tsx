import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { ObservationAccessControl } from './ObservationAccessControl';
import type { PilotActivationStatus } from '@/lib/api/types';

const {
  getPilotActivationMock,
  authorizeObservationMock,
  pauseObservationMock,
} = vi.hoisted(() => ({
  getPilotActivationMock: vi.fn(),
  authorizeObservationMock: vi.fn(),
  pauseObservationMock: vi.fn(),
}));

vi.mock('@/lib/api/accounts', () => ({
  getPilotActivation: getPilotActivationMock,
  authorizeObservation: authorizeObservationMock,
  pauseObservation: pauseObservationMock,
}));

const OFF: PilotActivationStatus = {
  mode: 'off',
  reason: 'expired',
  instance_id: 'instance-1',
  issued_by: 'admin-1',
  issued_at: 100,
  expires_at: 200,
  automatic_actions: false,
  game_actions: false,
  upstream_evidence: 'unverified',
  restart_policy: 'off',
};

function active(): PilotActivationStatus {
  return {
    ...OFF,
    mode: 'observe',
    reason: 'operator_grant',
    issued_at: Date.now() / 1000,
    expires_at: Date.now() / 1000 + 3600,
  };
}

beforeEach(() => {
  getPilotActivationMock.mockReset();
  authorizeObservationMock.mockReset();
  pauseObservationMock.mockReset();
});

describe('ObservationAccessControl', () => {
  it('lets an admin authorize an expired observation grant', async () => {
    const ACTIVE = active();
    getPilotActivationMock
      .mockResolvedValueOnce(OFF)
      .mockResolvedValue(ACTIVE);
    authorizeObservationMock.mockResolvedValue(ACTIVE);

    const user = userEvent.setup();
    renderWithProviders(
      <ObservationAccessControl accountId="acc-1" canAuthorize />,
    );

    expect(await screen.findByText('Observation expired')).toBeInTheDocument();

    await user.click(
      screen.getByRole('button', { name: /authorize 60 min/i }),
    );

    await waitFor(() =>
      expect(authorizeObservationMock).toHaveBeenCalledWith('acc-1', 60),
    );
    expect(await screen.findByText('Observation active')).toBeInTheDocument();
    expect(screen.getByText(/automation disabled; verified manual controls may be available/i)).toBeInTheDocument();
  });

  it('does not offer authorization to non-admin users', async () => {
    getPilotActivationMock.mockResolvedValue(OFF);

    renderWithProviders(
      <ObservationAccessControl accountId="acc-1" canAuthorize={false} />,
    );

    expect(await screen.findByText('Observation expired')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /authorize/i })).not.toBeInTheDocument();
    expect(screen.getByText(/admin must authorize observation/i)).toBeInTheDocument();
  });

  it('can pause an active observation grant', async () => {
    const ACTIVE = active();
    getPilotActivationMock
      .mockResolvedValueOnce(ACTIVE)
      .mockResolvedValue({ ...OFF, reason: 'not_activated' });
    pauseObservationMock.mockResolvedValue({ ...OFF, reason: 'not_activated' });

    const user = userEvent.setup();
    renderWithProviders(
      <ObservationAccessControl accountId="acc-1" canAuthorize />,
    );

    expect(await screen.findByText('Observation active')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /^pause$/i }));

    await waitFor(() =>
      expect(pauseObservationMock).toHaveBeenCalledWith('acc-1'),
    );
    expect(await screen.findByText('Observation required')).toBeInTheDocument();
  });
});
