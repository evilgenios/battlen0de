import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DevelopmentToolsPanel } from './DevelopmentToolsPanel';
import { MembershipRoleBadge } from '@/components/layout/MembershipRoleBadge';

const { session, mount } = vi.hoisted(() => ({ session: { user: null as null | { role: string; plan?: string } }, mount: vi.fn() }));
vi.mock('@/lib/hooks/useAuthSession', () => ({ useAuthSession: () => session }));
vi.mock('./DailyMissionsPanel', () => ({ DailyMissionsPanel: () => { mount('daily'); return <div>Live daily controls</div>; } }));
vi.mock('./BattleReportAnalyzerPanel', () => ({ BattleReportAnalyzerPanel: () => { mount('battle'); return null; } }));
vi.mock('./ArmyPresetManagerPanel', () => ({ ArmyPresetManagerPanel: () => { mount('army'); return null; } }));
vi.mock('./SupplyCasePanel', () => ({ SupplyCasePanel: () => { mount('supply'); return null; } }));

afterEach(() => { cleanup(); mount.mockClear(); });

describe('development tools availability', () => {
  it.each(['individual', 'alliance'])('shows coming soon without mounting tools for %s members', (plan) => {
    session.user = { role: 'member', plan };
    render(<DevelopmentToolsPanel accountId="a1" connected />);
    expect(screen.getAllByText('Coming soon')).toHaveLength(4);
    expect(mount).not.toHaveBeenCalled();
  });

  it('does not mount tools before identity resolves', () => {
    session.user = null;
    render(<DevelopmentToolsPanel accountId="a1" connected />);
    expect(mount).not.toHaveBeenCalled();
  });

  it('retains all four development panels for administrators', () => {
    session.user = { role: 'admin', plan: 'individual' };
    render(<DevelopmentToolsPanel accountId="a1" connected />);
    expect(screen.queryByText('Coming soon')).not.toBeInTheDocument();
    expect(mount.mock.calls.map(([name]) => name)).toEqual(['daily', 'battle', 'army', 'supply']);
  });

  it.each([['individual', 'Individual Member'], ['alliance', 'Alliance Member']])('labels the %s membership role', (plan, label) => {
    session.user = { role: 'member', plan };
    render(<MembershipRoleBadge />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
