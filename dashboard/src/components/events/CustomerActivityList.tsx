import Link from 'next/link';
import {
  Activity,
  AlertTriangle,
  Link2,
  LogIn,
  PackageCheck,
  RadioTower,
  RefreshCw,
  ShieldCheck,
  Truck,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { EmptyState } from '@/components/ui/EmptyState';
import { formatDateTime } from '@/lib/utils/format';
import type { AccountEvent } from '@/lib/api/types';

export interface CustomerActivityRow {
  event: AccountEvent;
  accountLabel?: string | null;
}

function activityCopy(event: AccountEvent): {
  title: string;
  description: string;
  tone: 'success' | 'info' | 'warning' | 'danger' | 'neutral';
  icon: typeof Activity;
} {
  const action = typeof event.detail.action === 'string' ? event.detail.action : null;
  switch (event.event_type) {
    case 'account_connected':
      return { title: 'Base connected', description: 'BattleN0de established a live Warpath session.', tone: 'success', icon: RadioTower };
    case 'account_disconnected':
    case 'account_stopped':
      return { title: 'Base disconnected', description: 'The live Warpath session ended.', tone: 'neutral', icon: RadioTower };
    case 'account_reconnect_started':
    case 'account_reconnect_requested':
      return { title: 'Reconnecting Base', description: 'BattleN0de is restoring the Warpath session.', tone: 'info', icon: RefreshCw };
    case 'account_connect_requested':
      return { title: 'Connection requested', description: 'A Warpath session was requested for this Base.', tone: 'info', icon: LogIn };
    case 'account_auth_failed':
      return { title: 'Connection needs attention', description: 'Warpath authentication failed. Relink the account if this continues.', tone: 'danger', icon: AlertTriangle };
    case 'account_restricted':
      return { title: 'Base restricted', description: 'BattleN0de stopped game actions for this account.', tone: 'danger', icon: AlertTriangle };
    case 'account_created':
      return { title: 'Base linked', description: 'This Warpath account was added to your BattleN0de.', tone: 'success', icon: Link2 };
    case 'account_relinked':
      return { title: 'Base relinked', description: 'The saved Warpath credentials were refreshed successfully.', tone: 'success', icon: Link2 };
    case 'account_deleted':
      return { title: 'Base removed', description: 'The linked account was removed from your BattleN0de.', tone: 'warning', icon: Link2 };
    case 'conquest_guard_enabled':
      return { title: 'Conquest Guard armed', description: 'Theater of Conquest protection is active for this Base.', tone: 'success', icon: ShieldCheck };
    case 'conquest_guard_disabled':
      return { title: 'Conquest Guard disarmed', description: 'Theater of Conquest protection was turned off.', tone: 'warning', icon: ShieldCheck };
    case 'action_requested':
      if (action === 'collect') return { title: 'Production collected', description: 'A Production Building collection command was sent.', tone: 'info', icon: PackageCheck };
      if (action === 'farm') return { title: 'Collection Convoy dispatched', description: 'A Convoy command was sent toward a resource target.', tone: 'info', icon: Truck };
      if (action === 'recall' || action === 'recall_all') return { title: 'Collection Convoy recalled', description: 'A recall command was sent to one or more Convoys.', tone: 'info', icon: Truck };
      return { title: 'Command sent', description: action ? `${action.replaceAll('_', ' ')} was requested.` : 'A BattleN0de command was requested.', tone: 'info', icon: Activity };
    case 'action_failed':
      return { title: 'Command failed', description: action ? `${action.replaceAll('_', ' ')} could not be completed.` : 'A BattleN0de command could not be completed.', tone: 'danger', icon: AlertTriangle };
    case 'account_status_changed':
      return { title: 'Base status updated', description: `Account status is now ${String(event.detail.status ?? 'updated')}.`, tone: 'info', icon: Activity };
    default:
      return {
        title: event.event_type.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase()),
        description: 'BattleN0de recorded account activity.',
        tone: 'neutral',
        icon: Activity,
      };
  }
}

export function CustomerActivityList({ rows }: { rows: CustomerActivityRow[] }) {
  if (rows.length === 0) {
    return <EmptyState icon={Activity} title="No activity yet" description="Important Base and command activity will appear here." />;
  }

  return (
    <div className="divide-y divide-border/70">
      {rows.map(({ event, accountLabel }) => {
        const copy = activityCopy(event);
        const Icon = copy.icon;
        return (
          <div key={event.id} className="flex gap-4 px-4 py-4 transition hover:bg-accent/[0.025] sm:px-5">
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-border/70 bg-surface-muted/45">
              <Icon className="h-4 w-4 text-accent" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-sm font-semibold text-foreground">{copy.title}</p>
                <Badge tone={copy.tone}>{copy.tone === 'danger' ? 'attention' : copy.tone}</Badge>
              </div>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{copy.description}</p>
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[9px] uppercase tracking-[0.09em] text-muted-foreground/75">
                <span>{formatDateTime(event.created_at)}</span>
                {event.account_id && accountLabel && (
                  <Link href={`/accounts/${event.account_id}`} className="transition hover:text-accent">
                    {accountLabel}
                  </Link>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
