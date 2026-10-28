'use client';

import { useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import useSWR from 'swr';
import {
  Activity,
  Ban,
  Database,
  KeyRound,
  RefreshCw,
  Search,
  ShieldCheck,
  ShieldEllipsis,
  UserCog,
  Users,
  WifiOff,
} from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { SkeletonRows } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import {
  disconnectAdminAccount,
  getAdminSummary,
  listAdminAccountEvents,
  listAdminAccounts,
  listAdminAudit,
  listAdminUsers,
  revokeAdminUserSessions,
  updateAdminAccountStatus,
  updateAdminUser,
} from '@/lib/api/admin';
import {
  beginMfaSetup,
  disableMfa,
  enableMfa,
  getMfaStatus,
  issueGrant,
} from '@/lib/api/auth';
import { ApiError } from '@/lib/api/client';
import type {
  AdminAccount,
  AdminAuditEvent,
  AdminUser,
  AdminUserPolicyPatch,
} from '@/lib/api/types';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { formatDateTime } from '@/lib/utils/format';

type Tab = 'customers' | 'accounts' | 'audit' | 'account-events' | 'security';

const inputClass =
  'h-10 rounded-xl border border-border/80 bg-surface/55 px-3 text-sm text-foreground outline-none transition focus:border-accent/45 focus:ring-4 focus:ring-accent/10';

function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : error instanceof Error ? error.message : 'Request failed.';
}

function SummaryCard({ label, value, hint }: { label: string; value: number; hint: string }) {
  return (
    <div className="premium-panel rounded-2xl p-4">
      <p className="font-mono text-[9px] uppercase tracking-[0.13em] text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-foreground">{value}</p>
      <p className="mt-1 text-[10px] text-muted-foreground">{hint}</p>
    </div>
  );
}

function UserPolicyEditor({
  user,
  onSaved,
}: {
  user: AdminUser;
  onSaved: () => Promise<void> | void;
}) {
  const toast = useToast();
  const separateScoutPolicy = 'can_player_scout' in user;
  const [status, setStatus] = useState<'active' | 'disabled'>(user.status === 'disabled' ? 'disabled' : 'active');
  const [plan, setPlan] = useState<'individual' | 'alliance'>(user.plan);
  const [maxAccounts, setMaxAccounts] = useState(user.max_accounts);
  const [maxSessions, setMaxSessions] = useState(user.max_sessions);
  const [maxActive, setMaxActive] = useState(user.max_active_accounts);
  const [playerScoutAccess, setPlayerScoutAccess] = useState(user.role === 'admin' ? true : separateScoutPolicy ? Boolean(user.can_player_scout) : user.player_scout_access);
  const [pending, setPending] = useState(false);

  async function save() {
    setPending(true);
    try {
      const body: AdminUserPolicyPatch = {
        status,
        max_accounts: plan === 'individual' ? 1 : Math.max(2, maxAccounts),
        max_sessions: maxSessions,
        max_active_accounts: plan === 'individual' ? 1 : Math.min(maxAccounts, maxActive),
        ...(separateScoutPolicy ? {} : { player_scout_access: playerScoutAccess }),
      };
      await updateAdminUser(user.id, body);
      toast.success('Customer policy updated', user.email);
      await onSaved();
    } catch (error) {
      toast.error('Could not update customer', errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  async function revokeSessions() {
    setPending(true);
    try {
      await revokeAdminUserSessions(user.id);
      toast.success('Sessions revoked', user.email);
      await onSaved();
    } catch (error) {
      toast.error('Could not revoke sessions', errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <details className="group border-t border-border/60 pt-3">
      <summary className="cursor-pointer list-none text-[11px] font-semibold text-accent">
        Manage customer
      </summary>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <label className="text-[10px] text-muted-foreground">
          Status
          <select className={`${inputClass} mt-1 w-full`} value={status} onChange={(e) => setStatus(e.target.value as 'active' | 'disabled')}>
            <option value="active">Active</option>
            <option value="disabled">Disabled</option>
          </select>
        </label>
        <label className="text-[10px] text-muted-foreground">
          Plan role
          <select className={`${inputClass} mt-1 w-full`} value={plan} onChange={(e) => {
            const nextPlan = e.target.value as 'individual' | 'alliance';
            setPlan(nextPlan);
            setMaxAccounts(nextPlan === 'individual' ? 1 : Math.max(10, maxAccounts));
            setMaxActive(nextPlan === 'individual' ? 1 : Math.max(3, maxActive));
          }}>
            <option value="individual">Individual Member</option>
            <option value="alliance">Alliance Member</option>
          </select>
        </label>
        <label className="text-[10px] text-muted-foreground">
          Linked Bases
          <input className={`${inputClass} mt-1 w-full`} type="number" min={plan === 'individual' ? 1 : 2} max={100} disabled={plan === 'individual'} value={maxAccounts} onChange={(e) => setMaxAccounts(Math.max(2, Number(e.target.value) || 2))} />
        </label>
        <label className="text-[10px] text-muted-foreground">
          Web sessions
          <input className={`${inputClass} mt-1 w-full`} type="number" min={1} max={20} value={maxSessions} onChange={(e) => setMaxSessions(Number(e.target.value) || 1)} />
        </label>
        <label className="text-[10px] text-muted-foreground">
          Active Bases
          <input className={`${inputClass} mt-1 w-full`} type="number" min={1} max={Math.min(20, maxAccounts)} disabled={plan === 'individual'} value={maxActive} onChange={(e) => setMaxActive(Number(e.target.value) || 1)} />
        </label>
        <label className="text-[10px] text-muted-foreground">
          Player Scout
          <span className="mt-1 flex h-10 items-center gap-2 rounded-xl border border-border/80 bg-surface/55 px-3 text-xs text-foreground">
            <input
              type="checkbox"
              checked={playerScoutAccess}
              disabled={user.role === 'admin' || separateScoutPolicy}
              onChange={(e) => setPlayerScoutAccess(e.target.checked)}
              aria-label="Player Scout access"
            />
            {user.role === 'admin' ? 'Always allowed' : separateScoutPolicy ? (playerScoutAccess ? 'Granted · managed separately' : 'Restricted · managed separately') : playerScoutAccess ? 'Granted' : 'Restricted'}
          </span>
        </label>
      </div>
      <p className="mt-3 text-xs text-muted-foreground">Plan roles follow linked-base limits: Individual has one base; Alliance has multiple bases. Administrator access is managed separately. Saving signs this customer out and disconnects their bases.</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="primary" loading={pending} onClick={save}>Save policy</Button>
        <Button size="sm" variant="outline" disabled={pending} onClick={revokeSessions}>Revoke sessions</Button>
      </div>
    </details>
  );
}

function CustomersTab({ users, refresh }: { users: AdminUser[]; refresh: () => Promise<void> }) {
  const [query, setQuery] = useState('');
  const filtered = useMemo(
    () => users.filter((user) => user.email.toLowerCase().includes(query.trim().toLowerCase())),
    [query, users],
  );

  return (
    <Card>
      <CardHeader
        title="Customers"
        description="Plans, account/session limits and privileged feature access. Passwords and saved game credentials are never exposed here."
        action={
          <label className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input className={`${inputClass} w-56 pl-9`} value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search email" />
          </label>
        }
      />
      <CardContent className="p-0">
        <div className="divide-y divide-border/70">
          {filtered.map((user) => (
            <div key={user.id} className="px-5 py-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-semibold text-foreground">{user.email}</p>
                    <Badge tone={user.status === 'active' ? 'success' : 'danger'}>{user.status}</Badge>
                    <Badge tone={user.plan === 'alliance' ? 'info' : 'neutral'}>{user.plan === 'alliance' ? 'Alliance Member' : 'Individual Member'}</Badge>
                    {user.role === 'admin' && <Badge tone="warning">admin</Badge>}
                    {user.role === 'admin' && <Badge tone={user.mfa_enabled ? 'success' : 'danger'}>{user.mfa_enabled ? 'MFA' : 'MFA off'}</Badge>}
                  </div>
                  <p className="mt-1 font-mono text-[9px] text-muted-foreground">{user.id}</p>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <span className="data-chip rounded-lg px-3 py-2"><b className="block text-xs text-foreground">{user.account_count}</b><span className="text-[9px] text-muted-foreground">Bases</span></span>
                  <span className="data-chip rounded-lg px-3 py-2"><b className="block text-xs text-foreground">{user.active_sessions}</b><span className="text-[9px] text-muted-foreground">Sessions</span></span>
                  <span className="data-chip rounded-lg px-3 py-2"><b className="block text-xs text-foreground">{user.max_active_accounts}</b><span className="text-[9px] text-muted-foreground">Active cap</span></span>
                </div>
              </div>
              <UserPolicyEditor user={user} onSaved={refresh} />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function AccountsTab({ accounts, refresh }: { accounts: AdminAccount[]; refresh: () => Promise<void> }) {
  const toast = useToast();
  const [pending, setPending] = useState<string | null>(null);

  async function changeStatus(account: AdminAccount, status: 'active' | 'disabled' | 'needs_reauth' | 'restricted') {
    setPending(account.id);
    try {
      await updateAdminAccountStatus(account.id, status);
      toast.success('Base status updated', `${account.label} → ${status}`);
      await refresh();
    } catch (error) {
      toast.error('Could not update Base', errorMessage(error));
    } finally {
      setPending(null);
    }
  }

  async function disconnect(account: AdminAccount) {
    setPending(account.id);
    try {
      await disconnectAdminAccount(account.id);
      toast.success('Base disconnected', account.label);
      await refresh();
    } catch (error) {
      toast.error('Could not disconnect Base', errorMessage(error));
    } finally {
      setPending(null);
    }
  }

  return (
    <Card>
      <CardHeader title="Linked Bases" description="All customer Warpath accounts. No app tokens or device IDs are returned by this API." />
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="border-b border-border/80 bg-surface-muted/25 font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
              <tr>
                <th className="px-5 py-3 text-left">Base</th>
                <th className="px-5 py-3 text-left">Customer</th>
                <th className="px-5 py-3 text-left">UID</th>
                <th className="px-5 py-3 text-left">DB status</th>
                <th className="px-5 py-3 text-left">Live state</th>
                <th className="px-5 py-3 text-left">Last connected</th>
                <th className="px-5 py-3 text-right">Controls</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((account) => (
                <tr key={account.id} className="border-b border-border/65 last:border-0">
                  <td className="px-5 py-4"><p className="font-semibold text-foreground">{account.label}</p><p className="mt-1 font-mono text-[9px] text-muted-foreground">{account.id}</p></td>
                  <td className="px-5 py-4 text-xs text-muted-foreground">{account.owner_email}</td>
                  <td className="px-5 py-4 font-mono text-[10px] text-muted-foreground">{account.app_uid}</td>
                  <td className="px-5 py-4"><Badge tone={account.status === 'active' ? 'success' : 'warning'}>{account.status}</Badge></td>
                  <td className="px-5 py-4"><Badge tone={account.authenticated ? 'success' : 'neutral'}>{account.live_state ?? 'offline'}</Badge></td>
                  <td className="px-5 py-4 text-xs text-muted-foreground">{account.last_connected_at ? formatDateTime(account.last_connected_at) : '—'}</td>
                  <td className="px-5 py-4">
                    <div className="flex justify-end gap-2">
                      <select
                        className={`${inputClass} w-36`}
                        value={account.status}
                        disabled={pending === account.id}
                        onChange={(e) => void changeStatus(account, e.target.value as 'active' | 'disabled' | 'needs_reauth' | 'restricted')}
                      >
                        <option value="active">active</option>
                        <option value="disabled">disabled</option>
                        <option value="needs_reauth">needs reauth</option>
                        <option value="restricted">restricted</option>
                      </select>
                      <Button size="sm" variant="outline" disabled={pending === account.id || !account.live_state} onClick={() => void disconnect(account)}>
                        Disconnect
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function AuditTab({ rows }: { rows: AdminAuditEvent[] }) {
  return (
    <Card>
      <CardHeader title="Security audit" description="Detailed administrator/authentication trail. Secrets, passwords, codes and tokens are redacted before persistence." />
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1100px] text-sm">
            <thead className="border-b border-border/80 bg-surface-muted/25 font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Time</th>
                <th className="px-4 py-3 text-left">Outcome</th>
                <th className="px-4 py-3 text-left">Action</th>
                <th className="px-4 py-3 text-left">Actor</th>
                <th className="px-4 py-3 text-left">Target</th>
                <th className="px-4 py-3 text-left">Peer</th>
                <th className="px-4 py-3 text-left">Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} className="border-b border-border/65 align-top last:border-0">
                  <td className="whitespace-nowrap px-4 py-3 font-mono text-[10px] text-muted-foreground">{formatDateTime(row.created_at)}</td>
                  <td className="px-4 py-3"><Badge tone={row.outcome === 'success' ? 'success' : row.outcome === 'failure' ? 'danger' : 'warning'}>{row.outcome}</Badge></td>
                  <td className="px-4 py-3 font-mono text-[10px] text-foreground">{row.action}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{row.actor_email ?? row.actor_user_id ?? 'anonymous'}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{row.target_type}{row.target_id ? `: ${row.target_id}` : ''}</td>
                  <td className="px-4 py-3"><p className="font-mono text-[10px] text-muted-foreground">{row.peer_ip ?? '—'}</p><p className="mt-1 max-w-[220px] truncate text-[9px] text-muted-foreground/70" title={row.user_agent ?? undefined}>{row.user_agent ?? '—'}</p></td>
                  <td className="max-w-[320px] px-4 py-3"><pre className="whitespace-pre-wrap break-words font-mono text-[9px] leading-4 text-muted-foreground">{JSON.stringify(row.detail, null, 2)}</pre></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}

function SecurityTab({ mfaEnabled, refreshAuth }: { mfaEnabled: boolean; refreshAuth: () => Promise<void> }) {
  const toast = useToast();
  const router = useRouter();
  const [setup, setSetup] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState('');
  const [grantEmail, setGrantEmail] = useState('');
  const [grantKind, setGrantKind] = useState<'invite' | 'recovery'>('invite');
  const [grant, setGrant] = useState<{ token: string; expires_at: string } | null>(null);
  const [pending, setPending] = useState(false);

  async function startMfa() {
    setPending(true);
    try {
      setSetup(await beginMfaSetup());
    } catch (error) {
      toast.error('Could not start MFA setup', errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  async function confirmMfa() {
    setPending(true);
    try {
      await enableMfa(code);
      toast.success('Administrator MFA enabled', 'All existing admin sessions were revoked. Sign in again using your authenticator code.');
      await refreshAuth();
      router.replace('/login');
    } catch (error) {
      toast.error('Could not enable MFA', errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  async function turnOffMfa() {
    setPending(true);
    try {
      await disableMfa(code);
      toast.info('Administrator MFA disabled', 'Existing sessions were revoked.');
      await refreshAuth();
      router.replace('/login');
    } catch (error) {
      toast.error('Could not disable MFA', errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  async function createGrant() {
    setPending(true);
    setGrant(null);
    try {
      const result = await issueGrant(grantEmail, grantKind);
      setGrant({ token: result.token, expires_at: result.expires_at });
      toast.success('One-time grant created', `${grantKind} for ${grantEmail}`);
    } catch (error) {
      toast.error('Could not issue grant', errorMessage(error));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="grid gap-5 xl:grid-cols-2">
      <Card>
        <CardHeader title="Administrator MFA" description="TOTP is encrypted at rest. Enabling or disabling MFA revokes existing admin sessions." />
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-border/70 bg-surface-muted/25 p-4">
            <div>
              <p className="text-sm font-semibold text-foreground">Authenticator protection</p>
              <p className="mt-1 text-xs text-muted-foreground">{mfaEnabled ? 'Required at administrator login.' : 'Not enabled yet.'}</p>
            </div>
            <Badge tone={mfaEnabled ? 'success' : 'danger'}>{mfaEnabled ? 'enabled' : 'required setup'}</Badge>
          </div>

          {!mfaEnabled && !setup && (
            <Button variant="primary" icon={<ShieldCheck className="h-4 w-4" />} loading={pending} onClick={startMfa}>
              Set up MFA
            </Button>
          )}

          {setup && !mfaEnabled && (
            <div className="space-y-3 rounded-xl border border-info/20 bg-info/5 p-4">
              <p className="text-xs leading-5 text-muted-foreground">
                Add this secret to 1Password, Authy, Google Authenticator or another TOTP app. The secret is shown only during setup.
              </p>
              <code className="block break-all rounded-lg border border-border/70 bg-background/60 p-3 font-mono text-xs text-foreground">{setup.secret}</code>
              <code className="block break-all rounded-lg border border-border/70 bg-background/60 p-3 font-mono text-[9px] text-muted-foreground">{setup.otpauth_uri}</code>
              <div className="flex gap-2">
                <input className={`${inputClass} flex-1`} inputMode="numeric" maxLength={6} placeholder="6-digit code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} />
                <Button variant="primary" loading={pending} disabled={code.length !== 6} onClick={confirmMfa}>Enable MFA</Button>
              </div>
            </div>
          )}

          {mfaEnabled && (
            <div className="flex gap-2">
              <input className={`${inputClass} flex-1`} inputMode="numeric" maxLength={6} placeholder="Current 6-digit code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} />
              <Button variant="danger" loading={pending} disabled={code.length !== 6} onClick={turnOffMfa}>Disable MFA</Button>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader title="Customer access grants" description="Issue one-time invite or recovery tokens. The plaintext token is only returned at creation time." />
        <CardContent className="space-y-3">
          <input className={`${inputClass} w-full`} type="email" placeholder="customer@example.com" value={grantEmail} onChange={(e) => setGrantEmail(e.target.value)} />
          <div className="flex gap-2">
            <select className={`${inputClass} flex-1`} value={grantKind} onChange={(e) => setGrantKind(e.target.value as 'invite' | 'recovery')}>
              <option value="invite">Invite new customer</option>
              <option value="recovery">Password recovery</option>
            </select>
            <Button variant="primary" loading={pending} disabled={!grantEmail.trim()} icon={<KeyRound className="h-4 w-4" />} onClick={createGrant}>
              Issue grant
            </Button>
          </div>
          {grant && (
            <div className="rounded-xl border border-warning/20 bg-warning/5 p-4">
              <p className="text-xs font-semibold text-warning">Copy this token now</p>
              <code className="mt-2 block break-all rounded-lg bg-background/60 p-3 font-mono text-xs text-foreground">{grant.token}</code>
              <p className="mt-2 text-[10px] text-muted-foreground">Expires {formatDateTime(grant.expires_at)}. BattleN0de does not persist the plaintext token.</p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminPage() {
  const { user, refresh: refreshAuth } = useAuthSession();
  const [tab, setTab] = useState<Tab>('customers');

  const isAdmin = user?.role === 'admin';
  const summary = useSWR(isAdmin ? 'admin-summary' : null, getAdminSummary, { refreshInterval: 10_000 });
  const users = useSWR(isAdmin ? 'admin-users' : null, () => listAdminUsers(), { refreshInterval: 15_000 });
  const accounts = useSWR(isAdmin ? 'admin-accounts' : null, listAdminAccounts, { refreshInterval: 10_000 });
  const audit = useSWR(isAdmin ? 'admin-audit' : null, () => listAdminAudit(250), { refreshInterval: 10_000 });
  const accountEvents = useSWR(isAdmin ? 'admin-account-events' : null, () => listAdminAccountEvents(250), { refreshInterval: 12_000 });
  const mfa = useSWR(isAdmin ? 'admin-mfa' : null, getMfaStatus);

  async function refreshAll() {
    await Promise.all([summary.mutate(), users.mutate(), accounts.mutate(), audit.mutate(), accountEvents.mutate(), mfa.mutate()]);
  }

  if (!isAdmin) {
    return (
      <Card>
        <CardContent className="py-14 text-center">
          <Ban className="mx-auto h-8 w-8 text-danger" />
          <p className="mt-4 text-sm font-semibold text-foreground">Administrator access required</p>
          <p className="mt-2 text-xs text-muted-foreground">This control center is not available to customer accounts.</p>
        </CardContent>
      </Card>
    );
  }

  const firstError = summary.error ?? users.error ?? accounts.error ?? audit.error ?? accountEvents.error ?? mfa.error;
  if (firstError) {
    return <Card><ErrorState error={firstError as Error} onRetry={() => void refreshAll()} title="Could not load admin control center" /></Card>;
  }

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="command-eyebrow"><ShieldEllipsis className="h-3.5 w-3.5" /> Site administration</span>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">BattleN0de Control Center</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
              Customers, linked Bases, sessions, plan limits, access grants and detailed security/audit history.
            </p>
          </div>
          <Button variant="outline" icon={<RefreshCw className="h-4 w-4" />} onClick={() => void refreshAll()}>Refresh all</Button>
        </div>
      </section>

      {summary.data ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryCard label="Customers" value={summary.data.users_total} hint={`${summary.data.users_active} active · ${summary.data.users_disabled} disabled`} />
          <SummaryCard label="Linked Bases" value={summary.data.accounts_total} hint={`${summary.data.accounts_connected} live now`} />
          <SummaryCard label="Web sessions" value={summary.data.active_web_sessions} hint="currently valid website sessions" />
          <SummaryCard label="Plans" value={summary.data.alliance_users} hint={`${summary.data.individual_users} Individual · ${summary.data.alliance_users} Alliance`} />
        </div>
      ) : (
        <SkeletonRows rows={2} />
      )}

      <div className="flex flex-wrap gap-2">
        {([
          ['customers', 'Customers', Users],
          ['accounts', 'Linked Bases', Database],
          ['audit', 'Security Audit', ShieldCheck],
          ['account-events', 'Account Events', Activity],
          ['security', 'Security & Access', UserCog],
        ] as const).map(([value, label, Icon]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value)}
            className={`inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition ${
              tab === value ? 'border-accent/30 bg-accent/10 text-accent' : 'border-border/70 bg-surface-muted/35 text-muted-foreground hover:text-foreground'
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {tab === 'customers' && (users.data ? <CustomersTab users={users.data} refresh={async () => { await users.mutate(); await summary.mutate(); }} /> : <SkeletonRows rows={8} />)}
      {tab === 'accounts' && (accounts.data ? <AccountsTab accounts={accounts.data} refresh={async () => { await accounts.mutate(); await summary.mutate(); await audit.mutate(); }} /> : <SkeletonRows rows={8} />)}
      {tab === 'audit' && (audit.data ? <AuditTab rows={audit.data} /> : <SkeletonRows rows={8} />)}
      {tab === 'account-events' && (
        <Card>
          <CardHeader title="Detailed account events" description="Raw safe event metadata across all customer Bases. This is intentionally more technical than the customer Activity page." />
          <CardContent className="p-0">
            {accountEvents.data ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1000px] text-sm">
                  <thead className="border-b border-border/80 bg-surface-muted/25 font-mono text-[9px] uppercase tracking-[0.12em] text-muted-foreground">
                    <tr><th className="px-4 py-3 text-left">Time</th><th className="px-4 py-3 text-left">Customer</th><th className="px-4 py-3 text-left">Base</th><th className="px-4 py-3 text-left">Type</th><th className="px-4 py-3 text-left">Actor</th><th className="px-4 py-3 text-left">Safe metadata</th></tr>
                  </thead>
                  <tbody>
                    {accountEvents.data.map((event) => (
                      <tr key={event.id} className="border-b border-border/65 align-top last:border-0">
                        <td className="whitespace-nowrap px-4 py-3 font-mono text-[10px] text-muted-foreground">{formatDateTime(event.created_at)}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{event.owner_email ?? '—'}</td>
                        <td className="px-4 py-3 text-xs text-foreground">{event.account_label ?? event.account_id ?? '—'}</td>
                        <td className="px-4 py-3 font-mono text-[10px] text-foreground">{event.event_type}</td>
                        <td className="px-4 py-3 text-xs text-muted-foreground">{event.actor}</td>
                        <td className="max-w-[360px] px-4 py-3"><pre className="whitespace-pre-wrap break-words font-mono text-[9px] leading-4 text-muted-foreground">{JSON.stringify(event.detail, null, 2)}</pre></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <SkeletonRows rows={8} />}
          </CardContent>
        </Card>
      )}
      {tab === 'security' && (
        <SecurityTab mfaEnabled={Boolean(mfa.data?.enabled ?? user?.mfa_enabled)} refreshAuth={refreshAuth} />
      )}

      <div className="premium-panel flex items-start gap-3 rounded-2xl p-4 text-xs leading-5 text-muted-foreground">
        <WifiOff className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        The admin API intentionally never returns saved Warpath app tokens, device IDs, password hashes, MFA secrets, database credentials or website session tokens.
      </div>
    </div>
  );
}

