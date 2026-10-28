'use client';

import Link from 'next/link';
import { ExternalLink } from 'lucide-react';
import { StatusBadge } from '@/components/accounts/StatusBadge';
import { ConnectionControls } from '@/components/accounts/ConnectionControls';
import { DeleteAccountButton } from '@/components/accounts/DeleteAccountButton';
import { Button } from '@/components/ui/Button';
import { formatDateTime } from '@/lib/utils/format';
import type { AccountWithStatus } from '@/lib/hooks/useAccountsOverview';

export function AccountsTable({ rows }: { rows: AccountWithStatus[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border/80 bg-surface-muted/25 text-left font-mono text-[10px] uppercase tracking-[0.13em] text-muted-foreground">
            <th className="px-5 py-3.5 font-semibold">Account</th>
            <th className="px-5 py-3.5 font-semibold">Status</th>
            <th className="px-5 py-3.5 font-semibold">Last activity</th>
            <th className="px-5 py-3.5 font-semibold">Created</th>
            <th className="px-5 py-3.5 font-semibold">Actions</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ account, status }) => {
            const liveState = status?.live?.state ?? null;
            const errorMessage = status?.live?.last_error;
            return (
              <tr key={account.id} className="group border-b border-border/70 last:border-0 transition-colors hover:bg-accent/[0.035]">
                <td className="px-5 py-4">
                  <Link href={`/accounts/${account.id}`} className="font-semibold text-foreground transition hover:text-accent">
                    {account.label}
                  </Link>
                  <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">UID {account.app_uid}</p>
                </td>
                <td className="px-5 py-4">
                  <StatusBadge state={liveState} />
                  {errorMessage && (
                    <p className="mt-1.5 max-w-[220px] truncate text-xs text-danger" title={errorMessage}>{errorMessage}</p>
                  )}
                </td>
                <td className="px-5 py-4 text-xs text-muted-foreground">
                  {status?.live?.last_connected_at
                    ? formatDateTime(new Date(status.live.last_connected_at * 1000).toISOString())
                    : formatDateTime(account.last_connected_at)}
                </td>
                <td className="px-5 py-4 text-xs text-muted-foreground">{formatDateTime(account.created_at)}</td>
                <td className="px-5 py-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <ConnectionControls accountId={account.id} liveState={liveState} />
                    <Link href={`/accounts/${account.id}`}>
                      <Button size="sm" variant="ghost" icon={<ExternalLink className="h-3.5 w-3.5" />}>Details</Button>
                    </Link>
                    <DeleteAccountButton accountId={account.id} accountLabel={account.label} />
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
