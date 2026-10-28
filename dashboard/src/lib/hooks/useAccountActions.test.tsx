import { act, renderHook } from '@testing-library/react';
import { beforeEach, expect, it, vi } from 'vitest';
import { useAccountActions } from './useAccountActions';

const mocks = vi.hoisted(() => ({ collect: vi.fn(), farm: vi.fn(), success: vi.fn(), info: vi.fn(), error: vi.fn(), mutate: vi.fn() }));
vi.mock('@/lib/api/actions', () => ({ collect: mocks.collect, farm: mocks.farm }));
vi.mock('@/components/ui/Toast', () => ({ useToast: () => mocks }));
vi.mock('swr', () => ({ useSWRConfig: () => ({ mutate: mocks.mutate }) }));
beforeEach(() => vi.clearAllMocks());

it.each(['partial', 'uncertain', 'rejected'])('never reports %s collection as empty or successful', async (status) => {
  mocks.collect.mockResolvedValue({ status, detail: 'timeout', buildings_requested: 2, buildings_replied: status === 'partial' ? 1 : 0, items_gained: 0, unconfirmed_building_ids: [107] });
  const { result } = renderHook(() => useAccountActions('account-a'));
  await act(async () => { await result.current.collect(); });
  expect(mocks.success).not.toHaveBeenCalled();
  expect(mocks.info).toHaveBeenCalledWith(expect.stringContaining(`Collection ${status}`));
  expect(mocks.info).not.toHaveBeenCalledWith(expect.stringContaining('Nothing ready'));
  expect(mocks.mutate).toHaveBeenCalledWith(['vehicles', 'account-a']);
  expect(mocks.mutate).toHaveBeenCalledWith(['active-actions', 'account-a']);
});

it('reports empty only when every building is confirmed', async () => {
  mocks.collect.mockResolvedValue({ status: 'confirmed', detail: 'complete', buildings_requested: 2, buildings_replied: 2, items_gained: 0, unconfirmed_building_ids: [] });
  const { result } = renderHook(() => useAccountActions('account-a'));
  await act(async () => { await result.current.collect(); });
  expect(mocks.info).toHaveBeenCalledWith('Nothing ready to collect yet (all buildings confirmed)');
});

it.each(['uncertain', 'confirmed'])('shows %s farming outcome without inventing success', async (status) => {
  mocks.farm.mockResolvedValue({ status, dispatched: status === 'confirmed', detail: 'Dispatch not confirmed; truck reserved', vehicle_id: 9, mine_id: 555 });
  const { result } = renderHook(() => useAccountActions('account-a'));
  await act(async () => { await result.current.farm({ resource: 'gold', level: 3 }); });
  if (status === 'confirmed') expect(mocks.success).toHaveBeenCalledWith('Vehicle 9 dispatched to mine 555');
  else {
    expect(mocks.success).not.toHaveBeenCalled();
    expect(mocks.info).toHaveBeenCalledWith(expect.stringContaining('truck reserved'));
  }
});
