import { apiRequest } from './client';
import type { Account, LinkRequestParams, LinkRequestResult, LinkVerifyParams } from './types';

export function requestLinkCode(params: LinkRequestParams): Promise<LinkRequestResult> {
  return apiRequest<LinkRequestResult>('/accounts/link/request', { method: 'POST', body: params });
}

export function verifyLinkCode(params: LinkVerifyParams): Promise<Account> {
  return apiRequest<Account>('/accounts/link/verify', { method: 'POST', body: params });
}
