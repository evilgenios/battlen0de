vi.mock('@/lib/hooks/useAuthSession', () => ({ useAuthSession: () => ({ user: { role: 'admin' } }) }));
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { AccountForm } from './AccountForm';

const { createAccountMock, pushMock } = vi.hoisted(() => ({
  createAccountMock: vi.fn(),
  pushMock: vi.fn(),
}));

vi.mock('@/lib/api/accounts', () => ({
  createAccount: createAccountMock,
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

async function fillRequiredFields(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/^label/i), 'Main Account');
  await user.type(screen.getByLabelText(/^app uid/i), 'uid-123');
  await user.type(screen.getByLabelText(/^app token/i), 'super-secret-token');
  await user.type(screen.getByLabelText(/^device id/i), 'device-abc');
  await user.type(screen.getByLabelText(/^app id/i), 'app-id-1');
  await user.type(screen.getByLabelText(/^pack name/i), 'pack-1');
  await user.type(screen.getByLabelText(/^channel id/i), 'channel-1');
  await user.type(screen.getByLabelText(/^app version/i), '1.0.0');
  await user.type(screen.getByLabelText(/^package version/i), '1.0.0');
}

beforeEach(() => {
  createAccountMock.mockReset();
  pushMock.mockReset();
});

describe('AccountForm', () => {
  it('shows validation errors and does not submit when required fields are missing', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AccountForm />);

    await user.click(screen.getByRole('button', { name: /add account/i }));

    expect(await screen.findAllByText('Required')).not.toHaveLength(0);
    expect(createAccountMock).not.toHaveBeenCalled();
  });

  it('creates the account and redirects to its details page on success', async () => {
    createAccountMock.mockResolvedValue({ id: 'new-account-id', label: 'Main Account' });
    const user = userEvent.setup();
    renderWithProviders(<AccountForm />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /add account/i }));

    await waitFor(() => expect(createAccountMock).toHaveBeenCalledTimes(1));
    const payload = createAccountMock.mock.calls[0][0];
    expect(payload).toMatchObject({
      label: 'Main Account',
      app_uid: 'uid-123',
      app_token: 'super-secret-token',
      device_id: 'device-abc',
    });

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/accounts/new-account-id'));
  });

  it('never re-displays submitted credentials after a successful submission', async () => {
    createAccountMock.mockResolvedValue({ id: 'new-account-id', label: 'Main Account' });
    const user = userEvent.setup();
    const { container } = renderWithProviders(<AccountForm />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /add account/i }));

    await waitFor(() => expect(pushMock).toHaveBeenCalled());
    // The success toast/redirect path must not echo the secret anywhere in the DOM.
    expect(container.textContent).not.toContain('super-secret-token');
  });

  it('shows an error message and does not redirect when account creation fails', async () => {
    createAccountMock.mockRejectedValue(new Error('label already in use'));
    const user = userEvent.setup();
    renderWithProviders(<AccountForm />);

    await fillRequiredFields(user);
    await user.click(screen.getByRole('button', { name: /add account/i }));

    expect(await screen.findByText(/could not create account/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('rejects platform-22 accounts whose OS type is not win/pc', async () => {
    const user = userEvent.setup();
    renderWithProviders(<AccountForm />);
    await fillRequiredFields(user);

    await user.click(screen.getByRole('button', { name: /advanced connection settings/i }));
    const osType = screen.getByLabelText(/^os type/i);
    await user.clear(osType);
    await user.type(osType, 'mac');

    await user.click(screen.getByRole('button', { name: /add account/i }));

    expect(await screen.findByText(/require 'win'/i)).toBeInTheDocument();
    expect(createAccountMock).not.toHaveBeenCalled();
  });
});
