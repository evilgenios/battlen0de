import { apiRequest } from './client';
import type {
  Account,
  AccountCreateRequest,
  AccountEvent,
  AccountEventWithLabelResponse,
  AccountOverviewResponse,
  PilotActivationStatus,
  SessionStatus,
} from './types';

export function listAccounts(): Promise<Account[]> {
  return apiRequest<Account[]>('/accounts');
}

export function getAccountsOverview(): Promise<AccountOverviewResponse[]> {
  return apiRequest<AccountOverviewResponse[]>('/accounts/overview');
}

export function getAccount(id: string): Promise<Account> {
  return apiRequest<Account>(`/accounts/${id}`);
}

export function createAccount(body: AccountCreateRequest): Promise<Account> {
  return apiRequest<Account>('/accounts', { method: 'POST', body });
}

export function deleteAccount(id: string): Promise<void> {
  return apiRequest<void>(`/accounts/${id}`, { method: 'DELETE' });
}

export function getAccountStatus(id: string): Promise<SessionStatus> {
  return apiRequest<SessionStatus>(`/accounts/${id}/status`);
}

export function connectAccount(id: string): Promise<SessionStatus> {
  return apiRequest<SessionStatus>(`/accounts/${id}/connect`, { method: 'POST' });
}

export function disconnectAccount(id: string): Promise<SessionStatus> {
  return apiRequest<SessionStatus>(`/accounts/${id}/disconnect`, { method: 'POST' });
}

export function reconnectAccount(id: string): Promise<SessionStatus> {
  return apiRequest<SessionStatus>(`/accounts/${id}/reconnect`, { method: 'POST' });
}

export function getPilotActivation(id: string): Promise<PilotActivationStatus> {
  return apiRequest<PilotActivationStatus>(`/accounts/${id}/pilot-activation`);
}

export function authorizeObservation(id: string, minutes: 15 | 60): Promise<PilotActivationStatus> {
  return apiRequest<PilotActivationStatus>(`/accounts/${id}/pilot-activation`, {
    method: 'POST',
    body: { mode: 'observe', minutes },
  });
}

export function pauseObservation(id: string): Promise<PilotActivationStatus> {
  return apiRequest<PilotActivationStatus>(`/accounts/${id}/pilot-pause`, { method: 'POST' });
}

export function getAccountEvents(id: string, limit = 50): Promise<AccountEvent[]> {
  return apiRequest<AccountEvent[]>(`/accounts/${id}/events?limit=${limit}`);
}


export function getAllEvents(limit = 100): Promise<AccountEventWithLabelResponse[]> {
  return apiRequest<AccountEventWithLabelResponse[]>(`/events?limit=${limit}`);
}
