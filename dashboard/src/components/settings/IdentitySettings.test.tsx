import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, test, expect, beforeEach } from 'vitest';
import { SWRConfig } from 'swr';
import { IdentitySettings } from './IdentitySettings';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { apiRequest } from '@/lib/api/client';
vi.mock('@/lib/hooks/useAuthSession');
vi.mock('@/lib/api/client', () => ({ apiRequest: vi.fn() }));
const clear = vi.fn();
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useAuthSession).mockReturnValue({ user: { user_id: 'a', email: 'a@example.com', role: 'member', session_key: 'session-a', active_sessions: 1 }, clear, isLoading: false, isAuthenticated: true, unauthenticated: false, refresh: vi.fn() });
  vi.mocked(apiRequest).mockImplementation(async path => path === '/auth/sessions' ? [{ id: 'session-a', current: true, created_at: '', last_used_at: '2026-09-27T00:00:00Z', expires_at: '' }] : undefined);
});
test('members cannot see provisioning and revoking current session clears private identity', async () => {
  render(<SWRConfig value={{ provider: () => new Map() }}><IdentitySettings /></SWRConfig>);
  expect(screen.queryByText('Pilot provisioning')).not.toBeInTheDocument();
  fireEvent.click(await screen.findByRole('button', { name: /^Revoke$/ }));
  await waitFor(() => expect(clear).toHaveBeenCalledOnce());
  expect(apiRequest).toHaveBeenCalledWith('/auth/sessions/session-a', { method: 'DELETE' });
});
test('failed revocation retains identity and reports the error', async () => {
  vi.mocked(apiRequest).mockRejectedValue(new Error('Unavailable'));
  render(<SWRConfig value={{ provider: () => new Map() }}><IdentitySettings /></SWRConfig>);
  fireEvent.click(screen.getByRole('button', { name: 'Revoke all website sessions' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Unavailable'));
  expect(clear).not.toHaveBeenCalled();
});
