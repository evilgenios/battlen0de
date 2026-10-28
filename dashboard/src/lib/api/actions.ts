/** One function per EXISTING backend action endpoint
 * (service/app/api/actions.py) — no new protocol behavior invented here. */

import { apiRequest } from './client';
import type {
  ActionResult,
  CollectResult,
  FarmParams,
  FarmResult,
  MassCancelResult,
  MassDeployParams,
  MassDeployResult,
  RecallParams,
  RecallResult,
  ScanParams,
  ScoutParams,
} from './types';

export function collect(id: string): Promise<CollectResult> {
  return apiRequest<CollectResult>(`/accounts/${id}/collect`, { method: 'POST' });
}

export function scan(id: string, params: ScanParams = {}): Promise<ActionResult> {
  return apiRequest<ActionResult>(`/accounts/${id}/scan`, { method: 'POST', body: params });
}

export function farm(id: string, params: FarmParams): Promise<FarmResult> {
  return apiRequest<FarmResult>(`/accounts/${id}/farm`, { method: 'POST', body: params });
}

export function recall(id: string, params: RecallParams): Promise<RecallResult> {
  return apiRequest<RecallResult>(`/accounts/${id}/recall`, { method: 'POST', body: params });
}

export function scout(id: string, params: ScoutParams): Promise<ActionResult> {
  return apiRequest<ActionResult>(`/accounts/${id}/scout`, { method: 'POST', body: params });
}

/** Mirrors service/app/api/mass_deploy.py: POST /accounts/mass-deploy.
 * Multi-account: pass explicit account_ids, never "every account". */
export function massDeploy(params: MassDeployParams): Promise<MassDeployResult> {
  return apiRequest<MassDeployResult>('/accounts/mass-deploy', { method: 'POST', body: params });
}

/** Mirrors POST /accounts/mass-deploy/cancel: signals an in-flight
 * deployment to stop; never claims to cancel a request already accepted. */
export function massCancel(): Promise<MassCancelResult> {
  return apiRequest<MassCancelResult>('/accounts/mass-deploy/cancel', { method: 'POST' });
}


/** This GET reads local state only; it never sends a game refresh. */
export function getCommandStatus(id: string): Promise<import('./types').CommandStatus> {
  return apiRequest(`/accounts/${id}/command-status`);
}
