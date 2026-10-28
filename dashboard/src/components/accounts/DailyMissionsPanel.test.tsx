import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { DailyMissionsPanel } from './DailyMissionsPanel';

const {
  useDailyMissionsMock,
  useDailyMissionPlanMock,
  setDailyMissionMapperBaselineMock,
  getDailyMissionMapperDiffMock,
  confirmDailyMissionMappingMock,
  clearDailyMissionMappingMock,
} = vi.hoisted(() => ({
  useDailyMissionsMock: vi.fn(),
  useDailyMissionPlanMock: vi.fn(),
  setDailyMissionMapperBaselineMock: vi.fn(),
  getDailyMissionMapperDiffMock: vi.fn(),
  confirmDailyMissionMappingMock: vi.fn(),
  clearDailyMissionMappingMock: vi.fn(),
}));

vi.mock('@/lib/hooks/useIntel', () => ({
  useDailyMissions: useDailyMissionsMock,
  useDailyMissionPlan: useDailyMissionPlanMock,
}));

vi.mock('@/components/accounts/DailyAssistSection', () => ({
  DailyAssistSection: () => null,
}));

vi.mock('@/lib/api', () => ({
  setDailyMissionMapperBaseline: setDailyMissionMapperBaselineMock,
  getDailyMissionMapperDiff: getDailyMissionMapperDiffMock,
  confirmDailyMissionMapping: confirmDailyMissionMappingMock,
  clearDailyMissionMapping: clearDailyMissionMappingMock,
}));

beforeEach(() => {
  setDailyMissionMapperBaselineMock.mockReset().mockResolvedValue({
    baseline_set: true,
    captured_at: 1790607597,
    task_count: 2,
    activition_point: 135,
  });
  getDailyMissionMapperDiffMock.mockReset().mockResolvedValue({
    baseline_captured_at: 1790607597,
    current_captured_at: 1790607600,
    task_changes: [
      {
        id: 9003,
        kind: 'changed',
        changed_fields: ['status', 'num'],
        before: { status: 1, num: 2 },
        after: { status: 2, num: 3 },
      },
    ],
    activation: { before: 135, after: 135, delta: 0 },
    reward_changes: [],
    inventory_observed: { before: true, after: true },
    inventory_changes: [
      {
        item_id: 'officer-exp-proven-id',
        before_quantity: 8,
        after_quantity: 5,
        delta: -3,
      },
    ],
    supply_case_observed: { before: true, after: true },
    supply_case_changes: [
      {
        key: 'campaign-case-raw',
        before_value: 2,
        after_value: 3,
        delta: 1,
      },
    ],
    has_changes: true,
  });
  clearDailyMissionMappingMock.mockReset().mockResolvedValue({
    objective_key: 'use_3_officer_exp',
    cleared: true,
  });
  confirmDailyMissionMappingMock.mockReset().mockResolvedValue({
    objective_key: 'use_3_officer_exp',
    label: 'Use 3 Officer EXP',
    task_id: 9003,
    only_id: 12009,
    mapped_at: 1790607601,
    evidence: {},
  });
  useDailyMissionPlanMock.mockReset().mockReturnValue({
    dailyPlan: {
      observed: true,
      state_source: 'live',
      observed_at: 1790607597,
      mapped_count: 0,
      complete_count: 0,
      total_count: 7,
      objectives: [
        ['rush_material_production_15m', 'Rush material production', 'Use 15 minutes of material-production speedups.'],
        ['kill_5_ravens', 'Kill 5 Ravens', 'Defeat 5 Ravens.'],
        ['use_1_unit_coupon', 'Use 1 Unit Coupon', 'Use exactly 1 Unit Coupon.'],
        ['use_3_officer_exp', 'Use 3 Officer EXP', 'Use exactly 3 Officer EXP items.'],
        ['launch_officer_mission', 'Launch Officer Mission', 'Launch an Officer Mission.'],
        ['upgrade_or_modify_unit', 'Upgrade or modify a unit', 'Perform one qualifying unit upgrade or modification.'],
        ['claim_campaign_resupply_3_and_rush', 'Campaign Resupply', 'Claim Campaign Resupply 3 times and rush it.'],
      ].map(([key, label, requested_goal]) => ({
        key,
        label,
        requested_goal,
        automation_state: key === 'kill_5_ravens' || key === 'claim_campaign_resupply_3_and_rush'
          ? 'observer_only'
          : 'guarded_primitive',
        schema_known: true,
        server_confirmation_known: key !== 'kill_5_ravens' && key !== 'claim_campaign_resupply_3_and_rush',
        execution_exposed: false,
        combat: key === 'kill_5_ravens',
        blockers: key === 'use_1_unit_coupon'
          ? ['The exact Unit Coupon item ID is not proven.']
          : ['Evidence-backed daily task mapping is required.'],
        mapping_state: 'unmapped',
        complete: false,
        task_id: null,
        only_id: null,
        task_status: null,
        task_status_label: null,
        num: null,
        mapped_at: null,
      })),
      limitation: 'Only evidence-confirmed task mappings appear as mapped.',
    },
    error: undefined,
    isLoading: false,
    refresh: vi.fn(),
  });
  useDailyMissionsMock.mockReset().mockReturnValue({
    dailyMissions: {
      observed: true,
      state_source: 'live',
      observed_at: 1790607597,
      activition_point: 135,
      refresh_time: 1790555510,
      tasks: [
        {
          id: 9003,
          status: 3,
          status_label: 'task_reward_taken',
          num: 3,
          only_id: 12009,
          village_obj_id: 0,
          finish_timestamp: 1790555647,
          source: 'playerdata_reply.client_task_data.daily_tasks',
          updated_at: 1790607597,
        },
        {
          id: 9005,
          status: 1,
          status_label: 'task_accepted',
          num: 0,
          only_id: 16001,
          village_obj_id: 0,
          finish_timestamp: 0,
          source: 'playerdata_reply.client_task_data.daily_tasks',
          updated_at: 1790607597,
        },
      ],
      daily_awards: [
        {
          award_index: 1,
          award_status: 3,
          award_status_label: 'reward_taken',
        },
      ],
      supply_cases: [
        {
          key: 'campaign-case-raw',
          value: 3,
        },
      ],
      task_updated_at: 1790607597,
      activation_updated_at: 1790607597,
      supply_case_updated_at: 1790607597,
      activation_source: 'playerdata_reply.daily_activition_data',
      limitation: 'Task IDs must be mapped from live before/after observation.',
    },
    error: undefined,
    isLoading: false,
    refresh: vi.fn(),
  });
});

describe('DailyMissionsPanel', () => {
  it('shows raw protocol state without inventing mission names', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DailyMissionsPanel accountId="acc-1" connected />);

    const toggle = screen.getByRole('button', { name: /daily missions/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByText('135 activation · 1 claimed tasks · 0 finished')).toBeInTheDocument();
    expect(screen.queryByText('#9003')).not.toBeInTheDocument();

    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('#9003')).toBeInTheDocument();
    expect(screen.getByText('12009')).toBeInTheDocument();
    expect(screen.getByText('num 3')).toBeInTheDocument();
    expect(screen.getByText('task_reward_taken')).toBeInTheDocument();
    expect(screen.getByText(/Task IDs must be mapped from live before\/after observation/i)).toBeInTheDocument();
    expect(screen.getByText('Reward 1: reward_taken')).toBeInTheDocument();
    expect(screen.getByText('Campaign / supply-case raw state')).toBeInTheDocument();
    expect(screen.getByText('campaign-case-raw: 3')).toBeInTheDocument();
    expect(screen.getByText(/No key is treated as Campaign Resupply until/i)).toBeInTheDocument();

    expect(screen.getByText('Rush material production')).toBeInTheDocument();
    expect(screen.getByText('Kill 5 Ravens')).toBeInTheDocument();
    expect(screen.getByText('Use 1 Unit Coupon')).toBeInTheDocument();
    expect(screen.getByText('Use 3 Officer EXP')).toBeInTheDocument();
    expect(screen.getByText('Launch Officer Mission')).toBeInTheDocument();
    expect(screen.getByText('Upgrade or modify a unit')).toBeInTheDocument();
    expect(screen.getByText('Campaign Resupply')).toBeInTheDocument();
    expect(screen.getAllByText('unmapped')).toHaveLength(7);
    expect(screen.getAllByText('execution locked')).toHaveLength(7);
    expect(screen.getByText('The exact Unit Coupon item ID is not proven.')).toBeInTheDocument();
    expect(screen.getByText('combat')).toBeInTheDocument();
  });

  it('lets an admin capture a baseline and compare protocol changes', async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <DailyMissionsPanel accountId="acc-1" connected canMap />,
    );

    await user.click(screen.getByRole('button', { name: /daily missions/i }));
    await user.click(screen.getByRole('button', { name: /capture baseline/i }));

    expect(setDailyMissionMapperBaselineMock).toHaveBeenCalledWith('acc-1');
    expect(
      await screen.findByText(/Baseline captured\. Perform one manual action/i),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /^compare$/i }));

    expect(getDailyMissionMapperDiffMock).toHaveBeenCalledWith('acc-1');
    expect(await screen.findByText('Changes detected')).toBeInTheDocument();
    expect(screen.getByText('Task #9003')).toBeInTheDocument();
    expect(screen.getByText('status, num')).toBeInTheDocument();
    expect(screen.getByText('Inventory evidence')).toBeInTheDocument();
    expect(screen.getByText('officer-exp-proven-id')).toBeInTheDocument();
    expect(screen.getByText('8 → 5')).toBeInTheDocument();
    expect(screen.getByText('Δ -3')).toBeInTheDocument();
    expect(screen.getByText('Supply-case evidence')).toBeInTheDocument();
    expect(screen.getByText('campaign-case-raw')).toBeInTheDocument();
    expect(screen.getByText('2 → 3')).toBeInTheDocument();
    expect(screen.getByText('Δ +1')).toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/Daily objective to map/i),
      'use_3_officer_exp',
    );
    await user.click(screen.getByRole('button', { name: /confirm mapping/i }));

    expect(confirmDailyMissionMappingMock).toHaveBeenCalledWith(
      'acc-1',
      'use_3_officer_exp',
    );
    expect(
      await screen.findByText(/Mapped Use 3 Officer EXP to task #9003/i),
    ).toBeInTheDocument();
  });

  it('lets an admin explicitly clear a stored mapping', async () => {
    useDailyMissionPlanMock.mockReturnValue({
      dailyPlan: {
        observed: true,
        state_source: 'live',
        observed_at: 1790607597,
        mapped_count: 1,
        complete_count: 1,
        total_count: 7,
        objectives: [
          {
            key: 'use_3_officer_exp',
            label: 'Use 3 Officer EXP',
            requested_goal: 'Use exactly 3 Officer EXP items.',
            automation_state: 'guarded_primitive',
            schema_known: true,
            server_confirmation_known: true,
            execution_exposed: false,
            combat: false,
            blockers: [
              'Evidence-backed daily task mapping is required.',
              'The exact Officer EXP item ID is not proven.',
            ],
            mapping_state: 'complete',
            complete: true,
            task_id: 9003,
            only_id: 12009,
            task_status: 2,
            task_status_label: 'task_finished',
            num: 3,
            mapped_at: 1790607601,
          },
        ],
        limitation: 'Only evidence-confirmed task mappings appear as mapped.',
      },
      error: undefined,
      isLoading: false,
      refresh: vi.fn(),
    });

    const user = userEvent.setup();
    renderWithProviders(
      <DailyMissionsPanel accountId="acc-1" connected canMap />,
    );

    await user.click(screen.getByRole('button', { name: /daily missions/i }));
    await user.click(screen.getByRole('button', { name: /clear mapping/i }));

    expect(clearDailyMissionMappingMock).toHaveBeenCalledWith(
      'acc-1',
      'use_3_officer_exp',
    );
    expect(
      await screen.findByText(/Cleared mapping for Use 3 Officer EXP/i),
    ).toBeInTheDocument();
  });
});
