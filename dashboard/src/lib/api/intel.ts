/** One function per EXISTING backend intel/conquest-guard/diagnostics
 * endpoint (service/app/api/intel.py, conquest_guard.py, diagnostics.py) —
 * no new protocol behavior invented here. */

import { apiRequest } from './client';
import type {
  AccountSummaryInfo,
  ActionResult,
  ActiveActionInfo,
  ArmyGroupInfo,
  ArmyInfo,
  ConquestGuardStatus,
  DebugCaptureStartResult,
  DebugCaptureStopResult,
  DailyMissionObserverResponse,
  DailyMissionMapperBaselineResult,
  DailyMissionMapperDiffResult,
  DailyMissionMappingClearResult,
  DailyMissionMappingResult,
  DailyMissionPlanResponse,
  JoinArmyGroupResult,
  LeaveArmyGroupResult,
  MainbasePosition,
  ProductionLineInfo,
  MapObjectInfo,
  ProfileInfo,
  RawSnapshotResult,
  RefreshResult,
  SkinsResult,
  VehicleInfo,
} from './types';

export function getAccountSummary(id: string): Promise<AccountSummaryInfo> {
  return apiRequest<AccountSummaryInfo>(`/accounts/${id}/summary`);
}

export function getDailyMissions(id: string): Promise<DailyMissionObserverResponse> {
  return apiRequest<DailyMissionObserverResponse>(`/accounts/${id}/daily-missions`);
}

export function getDailyMissionPlan(id: string): Promise<DailyMissionPlanResponse> {
  return apiRequest<DailyMissionPlanResponse>(`/accounts/${id}/daily-missions/plan`);
}

export function setDailyMissionMapperBaseline(id: string): Promise<DailyMissionMapperBaselineResult> {
  return apiRequest<DailyMissionMapperBaselineResult>(
    `/accounts/${id}/daily-missions/mapper/baseline`,
    { method: 'POST' },
  );
}

export function getDailyMissionMapperDiff(id: string): Promise<DailyMissionMapperDiffResult> {
  return apiRequest<DailyMissionMapperDiffResult>(
    `/accounts/${id}/daily-missions/mapper/diff`,
  );
}

export function confirmDailyMissionMapping(
  id: string,
  objectiveKey: string,
): Promise<DailyMissionMappingResult> {
  return apiRequest<DailyMissionMappingResult>(
    `/accounts/${id}/daily-missions/mapper/confirm/${encodeURIComponent(objectiveKey)}`,
    { method: 'POST' },
  );
}

export function clearDailyMissionMapping(
  id: string,
  objectiveKey: string,
): Promise<DailyMissionMappingClearResult> {
  return apiRequest<DailyMissionMappingClearResult>(
    `/accounts/${id}/daily-missions/mapper/mapping/${encodeURIComponent(objectiveKey)}`,
    { method: 'DELETE' },
  );
}

export function getVehicles(id: string): Promise<VehicleInfo[]> {
  return apiRequest<VehicleInfo[]>(`/accounts/${id}/vehicles`);
}

export function getActiveActions(id: string): Promise<ActiveActionInfo[]> {
  return apiRequest<ActiveActionInfo[]>(`/accounts/${id}/active-actions`);
}

export function getProduction(id: string): Promise<ProductionLineInfo[]> {
  return apiRequest<ProductionLineInfo[]>(`/accounts/${id}/production`);
}

export function getArmies(id: string): Promise<ArmyInfo[]> {
  return apiRequest<ArmyInfo[]>(`/accounts/${id}/armies`);
}

export function getArmyGroups(id: string): Promise<ArmyGroupInfo[]> {
  return apiRequest<ArmyGroupInfo[]>(`/accounts/${id}/army-groups`);
}

export function refreshArmyGroups(id: string): Promise<ActionResult> {
  return apiRequest<ActionResult>(`/accounts/${id}/army-groups/refresh`, { method: 'POST' });
}

export function joinArmyGroup(id: string, agId: number, params: { army_ids?: string; group_type?: string }): Promise<JoinArmyGroupResult> {
  return apiRequest<JoinArmyGroupResult>(`/accounts/${id}/army-groups/${agId}/join`, { method: 'POST', body: params });
}

export function leaveArmyGroup(id: string, armyId: number): Promise<LeaveArmyGroupResult> {
  return apiRequest<LeaveArmyGroupResult>(`/accounts/${id}/army-groups/leave`, { method: 'POST', body: { army_id: armyId } });
}

export function getProfile(id: string, uid: number): Promise<ProfileInfo> {
  return apiRequest<ProfileInfo>(`/accounts/${id}/profile/${uid}`);
}

export function refreshProfile(id: string, uid: number): Promise<ActionResult> {
  return apiRequest<ActionResult>(`/accounts/${id}/profile/${uid}/refresh`, { method: 'POST' });
}

export function getSkins(id: string): Promise<SkinsResult> {
  return apiRequest<SkinsResult>(`/accounts/${id}/skins`);
}

export function getMapObjects(id: string): Promise<MapObjectInfo[]> {
  return apiRequest<MapObjectInfo[]>(`/accounts/${id}/map-objects`);
}

export function locateBases(id: string, playerUid?: number): Promise<ActionResult> {
  return apiRequest<ActionResult>(`/accounts/${id}/locate-bases`, { method: 'POST', body: { player_uid: playerUid ?? null } });
}

export function getLocatedBase(id: string, playerUid: number): Promise<MainbasePosition> {
  return apiRequest<MainbasePosition>(`/accounts/${id}/locate-bases/${playerUid}`);
}

export function refreshAccountData(id: string): Promise<RefreshResult> {
  return apiRequest<RefreshResult>(`/accounts/${id}/refresh`, { method: 'POST' });
}

export function sendHeartbeat(id: string): Promise<ActionResult> {
  return apiRequest<ActionResult>(`/accounts/${id}/heartbeat`, { method: 'POST' });
}

export function recallAll(id: string): Promise<{ vehicle_ids: number[] }> {
  return apiRequest<{ vehicle_ids: number[] }>(`/accounts/${id}/recall-all`, { method: 'POST' });
}

export function getConquestGuard(id: string): Promise<ConquestGuardStatus> {
  return apiRequest<ConquestGuardStatus>(`/accounts/${id}/conquest-guard`);
}

export function enableConquestGuard(id: string): Promise<ConquestGuardStatus> {
  return apiRequest<ConquestGuardStatus>(`/accounts/${id}/conquest-guard/enable`, { method: 'POST' });
}

export function disableConquestGuard(id: string): Promise<ConquestGuardStatus> {
  return apiRequest<ConquestGuardStatus>(`/accounts/${id}/conquest-guard/disable`, { method: 'POST' });
}

export function startDebugCapture(id: string, seconds: number): Promise<DebugCaptureStartResult> {
  return apiRequest<DebugCaptureStartResult>(`/accounts/${id}/debug-capture/start`, { method: 'POST', body: { seconds } });
}

export function stopDebugCapture(id: string): Promise<DebugCaptureStopResult> {
  return apiRequest<DebugCaptureStopResult>(`/accounts/${id}/debug-capture/stop`, { method: 'POST' });
}

export function getRawSnapshot(id: string): Promise<RawSnapshotResult> {
  return apiRequest<RawSnapshotResult>(`/accounts/${id}/raw-snapshot`);
}


export function getDailyMissionAssist(id: string): Promise<import('./types').DailyMissionAssistResponse> {
  return apiRequest<import('./types').DailyMissionAssistResponse>(
    `/accounts/${id}/daily-missions/assist`,
  );
}

export function runDailyUnitCouponAssist(id: string): Promise<import('./types').DailyUnitCouponAssistResult> {
  return apiRequest<import('./types').DailyUnitCouponAssistResult>(
    `/accounts/${id}/daily-missions/assist/use-unit-coupon`,
    { method: 'POST', body: { confirm: true } },
  );
}

export function runDailyOfficerExpAssist(
  id: string,
  officerId: string,
): Promise<import('./types').DailyOfficerExpAssistResult> {
  return apiRequest<import('./types').DailyOfficerExpAssistResult>(
    `/accounts/${id}/daily-missions/assist/use-officer-exp`,
    { method: 'POST', body: { confirm: true, officer_id: officerId } },
  );
}

export function runDailyOfficerMissionAssist(
  id: string,
  taskId: string,
  officerIds: string[],
): Promise<import('./types').DailyOfficerMissionAssistResult> {
  return apiRequest<import('./types').DailyOfficerMissionAssistResult>(
    `/accounts/${id}/daily-missions/assist/launch-officer-mission`,
    {
      method: 'POST',
      body: {
        confirm: true,
        task_id: taskId,
        officer_ids: officerIds,
      },
    },
  );
}

export function getBattleReports(id: string): Promise<import('./types').BattleReportAnalyzerResponse> {
  return apiRequest<import('./types').BattleReportAnalyzerResponse>(
    `/accounts/${id}/battle-reports`,
  );
}

export function refreshBattleReports(id: string): Promise<import('./types').BattleReportAnalyzerResponse> {
  return apiRequest<import('./types').BattleReportAnalyzerResponse>(
    `/accounts/${id}/battle-reports/refresh`,
    { method: 'POST' },
  );
}

export function getArmyPresets(id: string): Promise<import('./types').ArmyPresetListResponse> {
  return apiRequest<import('./types').ArmyPresetListResponse>(
    `/accounts/${id}/army-presets`,
  );
}

export function renameArmyPreset(
  id: string,
  presetId: number,
  playType: number,
  name: string,
): Promise<import('./types').ArmyPresetRenameResult> {
  return apiRequest<import('./types').ArmyPresetRenameResult>(
    `/accounts/${id}/army-presets/${presetId}/rename`,
    { method: 'POST', body: { play_type: playType, name } },
  );
}

export function getSupplyCases(id: string): Promise<import('./types').SupplyCaseOverviewResponse> {
  return apiRequest<import('./types').SupplyCaseOverviewResponse>(
    `/accounts/${id}/supply-cases`,
  );
}
