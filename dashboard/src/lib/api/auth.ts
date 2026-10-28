import { apiRequest } from './client';
import type { DashboardUserInfo, LoginParams, MeResponse, MfaSetup, MfaStatus } from './types';

export function login(params: LoginParams): Promise<DashboardUserInfo> {
  return apiRequest<DashboardUserInfo>('/auth/login', { method: 'POST', body: params });
}

export function logout(): Promise<void> {
  return apiRequest<void>('/auth/logout', { method: 'POST' });
}

export function getMe(): Promise<MeResponse> {
  return apiRequest<MeResponse>('/auth/me');
}


export function getMfaStatus(): Promise<MfaStatus> {
  return apiRequest<MfaStatus>('/auth/mfa');
}

export function beginMfaSetup(): Promise<MfaSetup> {
  return apiRequest<MfaSetup>('/auth/mfa/setup', { method: 'POST' });
}

export function enableMfa(code: string): Promise<void> {
  return apiRequest<void>('/auth/mfa/enable', { method: 'POST', body: { code } });
}

export function disableMfa(code: string): Promise<void> {
  return apiRequest<void>('/auth/mfa/disable', { method: 'POST', body: { code } });
}

export function issueGrant(email: string, kind: 'invite' | 'recovery') {
  return apiRequest<{ token: string; expires_at: string; kind: string }>('/auth/pilot/grants', {
    method: 'POST',
    body: { email, kind },
  });
}
