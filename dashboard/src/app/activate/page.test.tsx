import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, test, expect } from 'vitest';
import ActivatePage from './page';
import { apiRequest } from '@/lib/api/client';
vi.mock('@/lib/api/client', () => ({ apiRequest: vi.fn() }));

test('redeems a token without putting it in the URL or logging in', async () => {
  vi.mocked(apiRequest).mockResolvedValue(undefined);
  render(<ActivatePage />);
  fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'synthetic-one-time-token' } });
  fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'synthetic-password' } });
  fireEvent.change(screen.getByLabelText('Confirm password'), { target: { value: 'synthetic-password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Set password' }));
  await waitFor(() => expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login'));
  expect(apiRequest).toHaveBeenCalledWith('/auth/pilot/redeem', { method: 'POST', body: { token: 'synthetic-one-time-token', password: 'synthetic-password' } });
  expect(screen.queryByDisplayValue('synthetic-one-time-token')).not.toBeInTheDocument();
});
