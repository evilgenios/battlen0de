import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import AdminPage from './page';

const { state, update } = vi.hoisted(() => ({ state: { scout: {} as Record<string, boolean> }, update: vi.fn().mockResolvedValue({}) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock('@/lib/hooks/useAuthSession', () => ({ useAuthSession: () => ({ user: { role: 'admin' }, refresh: vi.fn() }) }));
vi.mock('@/lib/api/admin', async (original) => ({ ...await original<typeof import('@/lib/api/admin')>(), updateAdminUser: update }));
vi.mock('swr', async (original) => ({ ...await original<typeof import('swr')>(), default: (key: string) => ({
  data: key === 'admin-users' ? [{ id: 'member-1', email: 'member@example.com', role: 'member', status: 'active', plan: 'individual', max_accounts: 1, max_sessions: 5, max_active_accounts: 1, account_count: 0, active_sessions: 0, ...state.scout }] : undefined,
  mutate: vi.fn(),
}) }));

afterEach(() => { cleanup(); update.mockClear(); });

describe('plan assignment across supported backend contracts', () => {
  it.each([false, true])('saves Alliance limits with separate scout policy=%s', async (separate) => {
    state.scout = separate ? { can_player_scout: true } : { player_scout_access: true };
    const user = userEvent.setup();
    renderWithProviders(<AdminPage />);
    await user.click(screen.getByText('Manage customer'));
    await user.selectOptions(screen.getByLabelText('Plan role'), 'alliance');
    await user.click(screen.getByRole('button', { name: 'Save policy' }));
    await waitFor(() => expect(update).toHaveBeenCalledWith('member-1', {
      status: 'active', max_accounts: 10, max_sessions: 5, max_active_accounts: 3,
      ...(separate ? {} : { player_scout_access: true }),
    }));
  });
});
