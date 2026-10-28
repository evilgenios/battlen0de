import { describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/test-utils';
import { AccountForm } from './AccountForm';
import { DiagnosticsPanel } from './DiagnosticsPanel';
import { MassDeployControl } from './MassDeployControl';

const auth = vi.hoisted(() => ({ role: 'member' as string | undefined }));
vi.mock('@/lib/hooks/useAuthSession', () => ({ useAuthSession: () => ({ user: { role: auth.role } }) }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));

describe('internal tool visibility', () => {
  it.each(['member', undefined, 'viewer'])('hides manual import, diagnostics and mass deploy for %s', (role) => {
    auth.role = role;
    const { container } = renderWithProviders(<><AccountForm /><DiagnosticsPanel accountId="fake" connected /><MassDeployControl accountId="fake" connected /></>);
    expect(container.querySelector('form')).toBeNull();
    expect(screen.queryByText('Diagnostics')).not.toBeInTheDocument();
    expect(container.querySelector('button')).toBeNull();
  });
  it('keeps diagnostics visible for an explicit admin', () => {
    auth.role = 'admin';
    renderWithProviders(<DiagnosticsPanel accountId="fake" connected={false} />);
    expect(screen.getByText('Diagnostics')).toBeInTheDocument();
  });
});
