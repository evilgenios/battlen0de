import { apiRequest } from './client';
import type {
  AdminAccount,
  AdminAccountEvent,
  AdminAuditEvent,
  AdminSummary,
  AdminUser,
  AdminUserPolicyPatch,
} from './types';

export function getAdminSummary(): Promise<AdminSummary> {
  return apiRequest<AdminSummary>('/admin/summary');
}

export function listAdminUsers(query = ''): Promise<AdminUser[]> {
  const qs = query ? `?q=${encodeURIComponent(query)}` : '';
  return apiRequest<AdminUser[]>(`/admin/users${qs}`);
}

export function updateAdminUser(id: string, body: AdminUserPolicyPatch): Promise<AdminUser> {
  return apiRequest<AdminUser>(`/admin/users/${id}`, { method: 'PATCH', body });
}

export function revokeAdminUserSessions(id: string): Promise<void> {
  return apiRequest<void>(`/admin/users/${id}/revoke-sessions`, { method: 'POST' });
}

export function listAdminAccounts(): Promise<AdminAccount[]> {
  return apiRequest<AdminAccount[]>('/admin/accounts');
}

export function updateAdminAccountStatus(
  id: string,
  status: 'active' | 'disabled' | 'needs_reauth' | 'restricted',
): Promise<AdminAccount> {
  return apiRequest<AdminAccount>(`/admin/accounts/${id}`, { method: 'PATCH', body: { status } });
}

export function disconnectAdminAccount(id: string): Promise<void> {
  return apiRequest<void>(`/admin/accounts/${id}/disconnect`, { method: 'POST' });
}

export function listAdminAudit(limit = 200): Promise<AdminAuditEvent[]> {
  return apiRequest<AdminAuditEvent[]>(`/admin/audit?limit=${limit}`);
}

export function listAdminAccountEvents(limit = 200): Promise<AdminAccountEvent[]> {
  return apiRequest<AdminAccountEvent[]>(`/admin/account-events?limit=${limit}`);
}
