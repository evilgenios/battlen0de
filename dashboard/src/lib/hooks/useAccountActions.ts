'use client';

import { useState } from 'react';
import { useSWRConfig } from 'swr';
import {
  connectAccount,
  deleteAccount,
  disconnectAccount,
  reconnectAccount,
} from '@/lib/api/accounts';
import { collect, farm, recall, scan, scout } from '@/lib/api/actions';
import { recallAll, refreshAccountData, sendHeartbeat } from '@/lib/api/intel';
import type { CollectResult, FarmParams, FarmResult, RecallParams, RecallResult, ScanParams, ScoutParams } from '@/lib/api/types';
import { describeError } from '@/components/ui/ErrorState';
import { useToast } from '@/components/ui/Toast';

export type AccountActionName =
  | 'connect'
  | 'disconnect'
  | 'reconnect'
  | 'delete'
  | 'collect'
  | 'scan'
  | 'farm'
  | 'recall'
  | 'recallAll'
  | 'scout'
  | 'refresh'
  | 'heartbeat';

/** Revalidates every SWR cache entry this account's state can appear in.
 * Uses the current session's provider; global mutate cannot reach it. */
function revalidateAccount(id: string, mutate: ReturnType<typeof useSWRConfig>['mutate']) {
  mutate('accounts-overview');
  mutate('accounts');
  mutate(['account', id]);
  mutate(['account-status', id]);
  for (const key of ['vehicles', 'active-actions', 'account-summary', 'production', 'command-status']) {
    mutate([key, id]);
  }
  mutate((key) => Array.isArray(key) && key[0] === 'account-events' && key[1] === id);
  mutate((key) => Array.isArray(key) && key[0] === 'all-events');
}

/** Discriminated result rather than `T | null`: deleteAccount() (204 No
 * Content) legitimately resolves to `null` on SUCCESS, so a bare `T | null`
 * return made "did this fail?" indistinguishable from "did this succeed
 * with no content?" — found live when DeleteAccountButton's
 * `result !== null` check silently never redirected after a real,
 * successful delete. `ok` is the only thing callers should branch on. */
export type ActionOutcome<T> = { ok: true; value: T } | { ok: false };

/** One in-flight action per account at a time — prevents duplicate
 * submissions (e.g. double-clicking Connect) without needing to disable
 * every button in the UI individually. */
export function useAccountActions(accountId: string) {
  const [pending, setPending] = useState<AccountActionName | null>(null);
  const toast = useToast();
  const { mutate } = useSWRConfig();

  async function run<T>(
    name: AccountActionName,
    action: () => Promise<T>,
    // A plain string always shows as a success toast, same as before. A
    // function reads the REAL result instead — needed once /collect,
    // /farm, and /recall started waiting for and returning the server's
    // actual reply: a static "Farm dispatched" string used to show even
    // when nothing was dispatched (no mine found, no idle vehicle), which
    // is exactly the "reports success but nothing happened" gap this was
    // meant to fix on the backend — showing it here too closes the loop.
    successMessage?: string | ((value: T) => { title: string; variant?: 'success' | 'info' }),
  ): Promise<ActionOutcome<T>> {
    if (pending) return { ok: false };
    setPending(name);
    try {
      const value = await action();
      if (typeof successMessage === 'function') {
        const { title, variant = 'success' } = successMessage(value);
        toast[variant](title);
      } else if (successMessage) {
        toast.success(successMessage);
      }
      revalidateAccount(accountId, mutate);
      return { ok: true, value };
    } catch (error) {
      toast.error(`${name[0].toUpperCase()}${name.slice(1)} failed`, describeError(error));
      return { ok: false };
    } finally {
      setPending(null);
    }
  }

  return {
    pending,
    connect: () => run('connect', () => connectAccount(accountId), 'Connecting…'),
    disconnect: () => run('disconnect', () => disconnectAccount(accountId), 'Disconnected'),
    reconnect: () => run('reconnect', () => reconnectAccount(accountId), 'Reconnecting…'),
    remove: () => run('delete', () => deleteAccount(accountId), 'Account deleted'),
    collect: () =>
      run('collect', () => collect(accountId), (value: CollectResult) => ({
        title:
          value.status !== 'confirmed'
            ? `Collection ${value.status}: ${value.buildings_replied}/${value.buildings_requested} building(s) confirmed; ${value.items_gained} reward entries confirmed. ${value.detail}`
            : value.items_gained > 0
              ? `Collected ${value.items_gained} reward entries from ${value.buildings_replied} building(s)`
              : 'Nothing ready to collect yet (all buildings confirmed)',
        variant: value.status === 'confirmed' && value.items_gained > 0 ? 'success' : 'info',
      })),
    scan: (params?: ScanParams) => run('scan', () => scan(accountId, params), 'Scan requested'),
    farm: (params: FarmParams) =>
      run('farm', () => farm(accountId, params), (value: FarmResult) => ({
        title: value.status === 'confirmed' && value.dispatched ? `Vehicle ${value.vehicle_id} dispatched to mine ${value.mine_id}` : value.detail,
        variant: value.status === 'confirmed' && value.dispatched ? 'success' : 'info',
      })),
    recall: (params: RecallParams) =>
      run('recall', () => recall(accountId, params), (value: RecallResult) => ({
        title: `Vehicle ${value.vehicle_id} recalled`,
      })),
    recallAll: () => run('recallAll', () => recallAll(accountId), 'Recall requested for all traveling/gathering vehicles'),
    scout: (params: ScoutParams) => run('scout', () => scout(accountId, params), 'Scout dispatched'),
    refresh: () => run('refresh', () => refreshAccountData(accountId), 'Data refresh requested'),
    heartbeat: () => run('heartbeat', () => sendHeartbeat(accountId), 'Heartbeat sent'),
  };
}
