import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { DailyAssistSection } from './DailyAssistSection';

const {
  useDailyMissionAssistMock,
  runDailyUnitCouponAssistMock,
  runDailyOfficerExpAssistMock,
  runDailyOfficerMissionAssistMock,
} = vi.hoisted(() => ({
  useDailyMissionAssistMock: vi.fn(),
  runDailyUnitCouponAssistMock: vi.fn(),
  runDailyOfficerExpAssistMock: vi.fn(),
  runDailyOfficerMissionAssistMock: vi.fn(),
}));

vi.mock('@/lib/hooks/useIntel', () => ({
  useDailyMissionAssist: useDailyMissionAssistMock,
}));

vi.mock('@/lib/api', () => ({
  runDailyUnitCouponAssist: runDailyUnitCouponAssistMock,
  runDailyOfficerExpAssist: runDailyOfficerExpAssistMock,
  runDailyOfficerMissionAssist: runDailyOfficerMissionAssistMock,
}));

beforeEach(() => {
  vi.restoreAllMocks();
  vi.spyOn(window, 'confirm').mockReturnValue(true);

  runDailyUnitCouponAssistMock.mockReset().mockResolvedValue({
    status: 'confirmed',
    objective_key: 'use_1_unit_coupon',
    item_id: 'coupon-item',
    quantity: 1,
    detail: 'confirmed',
  });
  runDailyOfficerExpAssistMock.mockReset().mockResolvedValue({
    status: 'confirmed',
    objective_key: 'use_3_officer_exp',
    officer_id: 'officer-a',
    item_id: 'exp-item',
    quantity: 3,
    detail: 'confirmed',
  });
  runDailyOfficerMissionAssistMock.mockReset().mockResolvedValue({
    status: 'confirmed',
    objective_key: 'launch_officer_mission',
    task_id: 'f1',
    officer_ids: ['officer-a', 'officer-b'],
    detail: 'confirmed',
  });

  useDailyMissionAssistMock.mockReset().mockReturnValue({
    assist: {
      observed: true,
      state_source: 'live',
      observed_at: 1,
      ready_count: 1,
      complete_count: 0,
      total_count: 7,
      mode: 'assist',
      automatic_execution: false,
      limitation: 'confirmation required',
      objectives: [
        {
          key: 'use_1_unit_coupon',
          label: 'Use 1 Unit Coupon',
          requested_goal: 'Use exactly 1 Unit Coupon.',
          automation_state: 'guarded_primitive',
          schema_known: true,
          server_confirmation_known: true,
          execution_exposed: false,
          combat: false,
          blockers: [],
          mapping_state: 'pending',
          complete: false,
          task_id: 1,
          only_id: 1,
          task_status: 1,
          task_status_label: 'task_accepted',
          num: 0,
          mapped_at: 1,
          assist_state: 'ready',
          action_key: 'use_unit_coupon',
          requires_confirmation: true,
          resolved_parameters: { item_id: 'coupon-item', quantity: 1 },
          assist_reason: 'ready',
        },
        {
          key: 'use_3_officer_exp',
          label: 'Use 3 Officer EXP',
          requested_goal: 'Use exactly 3 Officer EXP items.',
          automation_state: 'guarded_primitive',
          schema_known: true,
          server_confirmation_known: true,
          execution_exposed: false,
          combat: false,
          blockers: [],
          mapping_state: 'pending',
          complete: false,
          task_id: 2,
          only_id: 2,
          task_status: 1,
          task_status_label: 'task_accepted',
          num: 0,
          mapped_at: 1,
          assist_state: 'input_required',
          action_key: 'use_officer_exp',
          requires_confirmation: true,
          resolved_parameters: {
            item_id: 'exp-item',
            quantity: 3,
            officer_options: [
              { officer_id: 'officer-a', exp: 5, level: 10, power: 100 },
              { officer_id: 'officer-b', exp: 7, level: 11, power: 120 },
            ],
          },
          assist_reason: 'choose officer',
        },
        {
          key: 'launch_officer_mission',
          label: 'Launch Officer Mission',
          requested_goal: 'Launch an Officer Mission.',
          automation_state: 'guarded_primitive',
          schema_known: true,
          server_confirmation_known: true,
          execution_exposed: false,
          combat: false,
          blockers: [],
          mapping_state: 'pending',
          complete: false,
          task_id: 3,
          only_id: 3,
          task_status: 1,
          task_status_label: 'task_accepted',
          num: 0,
          mapped_at: 1,
          assist_state: 'input_required',
          action_key: 'launch_officer_mission',
          requires_confirmation: true,
          resolved_parameters: {
            officer_options: [
              { officer_id: 'officer-a', exp: 5, level: 10, power: 100 },
              { officer_id: 'officer-b', exp: 7, level: 11, power: 120 },
            ],
            mission_options: [
              { task_id: 'f1', status: 1, start_time: 0, end_time: 0, officer_ids: [] },
            ],
          },
          assist_reason: 'choose mission and officers',
        },
      ],
    },
    error: undefined,
    isLoading: false,
    refresh: vi.fn().mockResolvedValue(undefined),
  });
});

describe('DailyAssistSection', () => {
  it('uses the exact selected observed officer for Officer EXP', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DailyAssistSection accountId="acc-1" connected />);

    await user.selectOptions(
      screen.getByLabelText('Officer for EXP Assist'),
      'officer-a',
    );
    await user.click(screen.getByRole('button', { name: /confirm 3 officer exp/i }));

    await waitFor(() =>
      expect(runDailyOfficerExpAssistMock).toHaveBeenCalledWith(
        'acc-1',
        'officer-a',
      ),
    );
  });

  it('sends only the selected observed mission and officers', async () => {
    const user = userEvent.setup();
    renderWithProviders(<DailyAssistSection accountId="acc-1" connected />);

    await user.selectOptions(
      screen.getByLabelText('Officer mission for Assist'),
      'f1',
    );
    await user.click(screen.getByRole('button', { name: 'officer-a' }));
    await user.click(screen.getByRole('button', { name: 'officer-b' }));
    await user.click(screen.getByRole('button', { name: /confirm officer mission/i }));

    await waitFor(() =>
      expect(runDailyOfficerMissionAssistMock).toHaveBeenCalledWith(
        'acc-1',
        'f1',
        ['officer-a', 'officer-b'],
      ),
    );
  });
});
