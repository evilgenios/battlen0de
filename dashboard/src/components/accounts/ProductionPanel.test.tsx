import { beforeEach, describe, expect, it, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderWithProviders } from '@/test/test-utils';
import { ProductionPanel } from './ProductionPanel';

const { useProductionMock } = vi.hoisted(() => ({
  useProductionMock: vi.fn(),
}));

vi.mock('@/lib/hooks/useIntel', () => ({
  useProduction: useProductionMock,
}));

beforeEach(() => {
  const future = Math.floor(Date.now() / 1000) + 3600;
  const later = future + 1800;

  useProductionMock.mockReset().mockReturnValue({
    lines: [
      {
        building_id: 108,
        line_id: 1,
        item_type_id: 'Concrete',
        quantity: null,
        start_time: null,
        end_time: null,
        status: 'finished',
      },
      {
        building_id: 108,
        line_id: 1,
        item_type_id: 'Concrete',
        quantity: null,
        start_time: null,
        end_time: null,
        status: 'finished',
      },
      {
        building_id: 108,
        line_id: 1,
        item_type_id: 'Concrete',
        quantity: null,
        start_time: null,
        end_time: null,
        status: 'finished',
      },
      {
        building_id: 108,
        line_id: 1,
        item_type_id: 'Wood',
        quantity: 2,
        start_time: future - 1800,
        end_time: future,
        status: 'in_progress',
      },
      {
        building_id: 108,
        line_id: 1,
        item_type_id: 'Wood',
        quantity: 5,
        start_time: future - 1200,
        end_time: later,
        status: 'in_progress',
      },
      {
        building_id: 204,
        line_id: 2,
        item_type_id: 'Steel',
        quantity: 40,
        start_time: null,
        end_time: null,
        status: 'finished',
      },
    ],
    error: undefined,
    isLoading: false,
    refresh: vi.fn(),
  });
});

describe('ProductionPanel', () => {
  it('groups repeated produce cells by line and item instead of rendering duplicates', async () => {
    const user = userEvent.setup();
    renderWithProviders(<ProductionPanel accountId="acc-1" connected />);

    const toggle = screen.getByRole('button', { name: /production/i });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByText('2 lines')).toBeInTheDocument();

    await user.click(toggle);

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('Line 1')).toBeInTheDocument();
    expect(screen.getByText('Line 2')).toBeInTheDocument();
    expect(screen.getByText('Building #108')).toBeInTheDocument();
    expect(screen.getByText('Building #204')).toBeInTheDocument();

    // Three quantity-less Concrete cells are one summarized row, not three
    // duplicated rows pretending the quantity is known.
    expect(screen.getAllByText('Concrete')).toHaveLength(1);
    expect(screen.getByText('3 queue entries')).toBeInTheDocument();
    expect(screen.getByText('3 queue entries ready to claim')).toBeInTheDocument();

    // Explicit quantities are summed and rendered as actual quantities.
    expect(screen.getAllByText('Wood')).toHaveLength(1);
    expect(screen.getByText('7×')).toBeInTheDocument();
    expect(screen.getByText('7× producing')).toBeInTheDocument();
    expect(screen.getByText(/Next ready/i)).toBeInTheDocument();
    expect(screen.getByText(/Queue clear/i)).toBeInTheDocument();

    expect(screen.getByText('40×')).toBeInTheDocument();
    expect(screen.getByText('40× ready to claim')).toBeInTheDocument();
  });
});
