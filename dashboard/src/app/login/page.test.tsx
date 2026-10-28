import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import LoginPage from './page';
import { ApiError } from '@/lib/api/client';

const { loginMock, pushMock, refreshMock, meMock } = vi.hoisted(() => ({
  loginMock: vi.fn(),
  pushMock: vi.fn(),
  refreshMock: vi.fn(),
  meMock: vi.fn(),
}));

vi.mock('@/lib/api/auth', () => ({
  login: loginMock,
  getMe: meMock,
  logout: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock, replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/login',
}));

vi.mock('@/lib/hooks/useAuthSession', () => ({
  useAuthSession: () => ({ refresh: refreshMock, isLoading: false, isAuthenticated: false, unauthenticated: true, user: undefined }),
}));

beforeEach(() => {
  loginMock.mockReset();
  pushMock.mockReset();
  refreshMock.mockReset().mockResolvedValue(undefined);
});

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
  await user.type(screen.getByLabelText(/password/i), 'correct horse battery staple');
  await user.click(screen.getByRole('button', { name: /sign in/i }));
}

describe('LoginPage', () => {
  it('shows a validation-style error on failed login without revealing which field was wrong', async () => {
    loginMock.mockRejectedValue(new ApiError(401, 'invalid email or password'));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(user);

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('redirects to the dashboard on successful login', async () => {
    loginMock.mockResolvedValue({ email: 'admin@example.com', role: 'admin', csrf_token: 'abc' });
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(user);

    await waitFor(() => expect(pushMock).toHaveBeenCalledWith('/dashboard'));
    expect(loginMock).toHaveBeenCalledWith({ email: 'admin@example.com', password: 'correct horse battery staple' });
  });

  it('shows a network-error message when the backend is unreachable', async () => {
    loginMock.mockRejectedValue(new ApiError(0, null, 'Could not reach the dashboard server.'));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(user);

    expect(await screen.findByText(/could not reach the dashboard server/i)).toBeInTheDocument();
  });

  it('prevents duplicate submissions while a login is in flight', async () => {
    let resolveLogin: (value: unknown) => void = () => {};
    loginMock.mockReturnValue(new Promise((resolve) => { resolveLogin = resolve; }));
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.type(screen.getByLabelText(/email/i), 'admin@example.com');
    await user.type(screen.getByLabelText(/password/i), 'correct horse battery staple');
    const button = screen.getByRole('button', { name: /sign in/i });
    await user.click(button);
    await user.click(button);
    await user.click(button);

    resolveLogin({ email: 'admin@example.com', role: 'admin', csrf_token: 'abc' });
    await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(1));
  });

  it('rejects an empty-field submit locally instead of round-tripping to the server', async () => {
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await user.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/email and password are required/i)).toBeInTheDocument();
    expect(loginMock).not.toHaveBeenCalled();
  });

  it('never displays a password field value or leaks it into the DOM as text', async () => {
    const user = userEvent.setup();
    const { container } = renderWithProviders(<LoginPage />);
    await user.type(screen.getByLabelText(/password/i), 'super-secret-password');
    expect(container.textContent).not.toContain('super-secret-password');
  });

  it('prompts for an authenticator code when the backend requires admin MFA', async () => {
    loginMock
      .mockRejectedValueOnce(new ApiError(401, 'mfa required'))
      .mockResolvedValueOnce({ email: 'admin@example.com', role: 'admin', csrf_token: 'abc' });
    const user = userEvent.setup();
    renderWithProviders(<LoginPage />);

    await fillAndSubmit(user);
    expect(await screen.findByLabelText(/authenticator code/i)).toBeInTheDocument();

    await user.type(screen.getByLabelText(/authenticator code/i), '123456');
    await user.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() =>
      expect(loginMock).toHaveBeenLastCalledWith({
        email: 'admin@example.com',
        password: 'correct horse battery staple',
        mfa_code: '123456',
      }),
    );
  });

});
