import { useState } from 'react';
import useSWR from 'swr';
import {
  getAccountSummary,
  getActiveActions,
  getDailyMissionPlan,
  getDailyMissions,
  getSupplyCases,
  getArmyPresets,
  getBattleReports,
  getDailyMissionAssist,
  getArmies,
  getArmyGroups,
  getConquestGuard,
  getMapObjects,
  getProduction,
  getSkins,
  getVehicles,
} from '@/lib/api';

const REFRESH_INTERVAL_MS = 8_000;

export function useAccountSummary(id: string | undefined) {
  const { data, isLoading } = useSWR(id ? ['account-summary', id] : null, () => getAccountSummary(id as string), {
    refreshInterval: REFRESH_INTERVAL_MS,
  });
  return { summary: data, isLoading };
}

export function useDailyMissions(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['daily-missions', id] : null,
    () => getDailyMissions(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { dailyMissions: data, error, isLoading, refresh: mutate };
}

export function useDailyMissionPlan(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['daily-missions-plan', id] : null,
    () => getDailyMissionPlan(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { dailyPlan: data, error, isLoading, refresh: mutate };
}

export function useVehicles(id: string | undefined, enabled = true) {
  const { data, isLoading, mutate } = useSWR(
    id && enabled ? ['vehicles', id] : null, () => getVehicles(id as string), { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { vehicles: data ?? [], isLoading, refresh: mutate };
}

export function useActiveActions(id: string | undefined, enabled = true) {
  // A real client-side fact ("when did we last hear back from the
  // backend"), tracked via SWR's own success/error callbacks rather than a
  // generic effect — there's no per-activity "last updated" field on the
  // wire to show instead.
  const [lastSyncedAt, setLastSyncedAt] = useState<number | null>(null);
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['active-actions', id] : null, () => getActiveActions(id as string), {
      refreshInterval: REFRESH_INTERVAL_MS,
      onSuccess: () => setLastSyncedAt(Date.now()),
      onError: () => setLastSyncedAt(Date.now()),
    },
  );
  // error is surfaced deliberately: a bad response here must show as a
  // visible error, not silently render as "no activity in progress" — see
  // ActiveActionsPanel.tsx.
  return { activities: data ?? [], error, isLoading, lastSyncedAt, refresh: mutate };
}

export function useProduction(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['production', id] : null, () => getProduction(id as string), { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { lines: data ?? [], error, isLoading, refresh: mutate };
}

export function useArmies(id: string | undefined, enabled = true) {
  const { data, isLoading, mutate } = useSWR(
    id && enabled ? ['armies', id] : null, () => getArmies(id as string), { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { armies: data ?? [], isLoading, refresh: mutate };
}

export function useArmyGroups(id: string | undefined, enabled = true) {
  const { data, isLoading, mutate } = useSWR(
    id && enabled ? ['army-groups', id] : null, () => getArmyGroups(id as string), { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { armyGroups: data ?? [], isLoading, refresh: mutate };
}

export function useMapObjects(id: string | undefined, enabled = true) {
  const { data, isLoading, mutate } = useSWR(
    id && enabled ? ['map-objects', id] : null, () => getMapObjects(id as string), { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { mapObjects: data ?? [], isLoading, refresh: mutate };
}

export function useSkins(id: string | undefined, enabled = true) {
  const { data, isLoading, mutate } = useSWR(
    id && enabled ? ['skins', id] : null, () => getSkins(id as string), { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { skins: data?.categories ?? {}, isLoading, refresh: mutate };
}

export function useConquestGuard(id: string | undefined) {
  const { data, isLoading, mutate } = useSWR(
    id ? ['conquest-guard', id] : null, () => getConquestGuard(id as string), { refreshInterval: 5_000 },
  );
  return { status: data, isLoading, refresh: mutate };
}


export function useDailyMissionAssist(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['daily-missions-assist', id] : null,
    () => getDailyMissionAssist(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { assist: data, error, isLoading, refresh: mutate };
}


export function useBattleReports(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['battle-reports', id] : null,
    () => getBattleReports(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { reports: data, error, isLoading, refresh: mutate };
}


export function useArmyPresets(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['army-presets', id] : null,
    () => getArmyPresets(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { presets: data, error, isLoading, refresh: mutate };
}


export function useSupplyCases(id: string | undefined, enabled = true) {
  const { data, error, isLoading, mutate } = useSWR(
    id && enabled ? ['supply-cases', id] : null,
    () => getSupplyCases(id as string),
    { refreshInterval: REFRESH_INTERVAL_MS },
  );
  return { supply: data, error, isLoading, refresh: mutate };
}
