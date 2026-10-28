'use client';

import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { DailyMissionsPanel } from './DailyMissionsPanel';
import { BattleReportAnalyzerPanel } from './BattleReportAnalyzerPanel';
import { ArmyPresetManagerPanel } from './ArmyPresetManagerPanel';
import { SupplyCasePanel } from './SupplyCasePanel';
import { UpcomingToolsPanel } from './UpcomingToolsPanel';

export function DevelopmentToolsPanel({ accountId, connected }: { accountId: string; connected: boolean }) {
  const { user } = useAuthSession();
  // Do not mount development panels or start their requests for members.
  if (user?.role !== 'admin') return <UpcomingToolsPanel />;
  return (
    <>
      <DailyMissionsPanel accountId={accountId} connected={connected} canMap />
      <BattleReportAnalyzerPanel accountId={accountId} connected={connected} />
      <ArmyPresetManagerPanel accountId={accountId} connected={connected} />
      <SupplyCasePanel accountId={accountId} />
    </>
  );
}
