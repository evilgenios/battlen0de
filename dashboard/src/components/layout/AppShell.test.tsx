import { describe, expect, it, vi, beforeEach } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@testing-library/react';
import { AppShell } from './AppShell';

const { replaceMock, useHealthMock, useAuthSessionMock, pathnameMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  pathnameMock: vi.fn(),
  useHealthMock: vi.fn(),
  useAuthSessionMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  usePathname: pathnameMock,
  useRouter: () => ({ replace: replaceMock, push: vi.fn(), refresh: vi.fn() }),
}));

vi.mock('@/lib/hooks/useHealth', () => ({ useHealth: useHealthMock }));
vi.mock('@/lib/hooks/useAuthSession', () => ({ useAuthSession: useAuthSessionMock }));

beforeEach(() => {
  replaceMock.mockReset();
  pathnameMock.mockReturnValue('/accounts');
  useHealthMock.mockReset();
  useAuthSessionMock.mockReset();
});

describe('AppShell route guard', () => {
  it('does not trust a health hint to bypass authentication', () => {
    useHealthMock.mockReturnValue({ health: { status: 'ok', database: 'ok', auth_required: false }, isLoading: false, isDown: false });
    useAuthSessionMock.mockReturnValue({ isLoading: false, isAuthenticated: false, unauthenticated: true, user: undefined });

    render(<AppShell><div>Protected content</div></AppShell>);

    expect(screen.queryByText('Protected content')).not.toBeInTheDocument();
    expect(replaceMock).toHaveBeenCalledWith('/login');
  });

  it('redirects to /login when auth is required and the visitor has no session', async () => {
    useHealthMock.mockReturnValue({ health: { status: 'ok', database: 'ok', auth_required: true }, isLoading: false, isDown: false });
    useAuthSessionMock.mockReturnValue({ isLoading: false, isAuthenticated: false, unauthenticated: true, user: undefined });

    render(<AppShell><div>Protected content</div></AppShell>);

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith('/login'));
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument();
  });

  it('renders protected content when auth is required and the visitor has a valid session', () => {
    useHealthMock.mockReturnValue({ health: { status: 'ok', database: 'ok', auth_required: true }, isLoading: false, isDown: false });
    useAuthSessionMock.mockReturnValue({ isLoading: false, isAuthenticated: true, unauthenticated: false, user: { email: 'a@example.com', role: 'admin' } });

    render(<AppShell><div>Protected content</div></AppShell>);

    expect(screen.getByText('Protected content')).toBeInTheDocument();
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it('shows nothing (no flash of protected content) while auth state is still loading', () => {
    useHealthMock.mockReturnValue({ health: undefined, isLoading: true, isDown: false });
    useAuthSessionMock.mockReturnValue({ isLoading: true, isAuthenticated: false, unauthenticated: false, user: undefined });

    render(<AppShell><div>Protected content</div></AppShell>);

    expect(screen.queryByText('Protected content')).not.toBeInTheDocument();
  });
});

it('allows anonymous invitation/recovery redemption without protected content', () => {
  pathnameMock.mockReturnValue('/activate');
  useAuthSessionMock.mockReturnValue({ isLoading: false, isAuthenticated: false, unauthenticated: true });
  render(<AppShell><div>Redeem invitation</div></AppShell>);
  expect(screen.getByText('Redeem invitation')).toBeInTheDocument();
  expect(replaceMock).not.toHaveBeenCalled();
});


it('renders the public homepage without requiring a dashboard session', () => {
  pathnameMock.mockReturnValue('/');
  useAuthSessionMock.mockReturnValue({ isLoading: false, isAuthenticated: false, unauthenticated: true, user: undefined });
  render(<AppShell><div>Public product home</div></AppShell>);
  expect(screen.getByText('Public product home')).toBeInTheDocument();
  expect(replaceMock).not.toHaveBeenCalled();
});
