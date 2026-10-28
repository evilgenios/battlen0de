import { render, type RenderOptions } from '@testing-library/react';
import { SWRConfig } from 'swr';
import { ToastProvider } from '@/components/ui/Toast';

/** Wraps every test render in a FRESH SWR cache (a plain Map, discarded
 * per-render) so one test's cached data can never leak into another's —
 * SWR's default cache is a module-level singleton otherwise — plus the
 * ToastProvider every action-triggering component under test needs. */
export function renderWithProviders(ui: React.ReactElement, options?: RenderOptions) {
  return render(
    <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0 }}>
      <ToastProvider>{ui}</ToastProvider>
    </SWRConfig>,
    options,
  );
}

export * from '@testing-library/react';
