'use client';

import { useState } from 'react';
import useSWR from 'swr';
import { apiRequest } from '@/lib/api/client';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';

type WebsiteSession = { id: string; current: boolean; created_at: string; last_used_at: string; expires_at: string };

export function IdentitySettings() {
  const { user, clear } = useAuthSession();
  const local = user?.session_key.startsWith('local:');
  const { data, error, mutate } = useSWR<WebsiteSession[]>(local ? null : '/auth/sessions', apiRequest);
  const [failure, setFailure] = useState('');
  const [busy, setBusy] = useState(false);
  async function revoke(session?: WebsiteSession) {
    if (busy) return;
    setBusy(true); setFailure('');
    try {
      await apiRequest(session ? `/auth/sessions/${session.id}` : '/auth/revoke-all', { method: session ? 'DELETE' : 'POST' });
      if (!session || session.current) clear();
      else await mutate();
    } catch (err) { setFailure(err instanceof Error ? err.message : 'Revocation failed.'); }
    finally { setBusy(false); }
  }
  return <>
    {!local && <Card><CardHeader title="Website sessions" description="These browser sessions are separate from your game connections." /><CardContent className="space-y-3">
      {(failure || error) && <p role="alert">{failure || 'Could not load sessions.'}</p>}
      {data?.map(s => <div key={s.id} className="flex items-center justify-between gap-4"><span>{s.current ? 'This browser' : 'Other browser'} · last used {new Date(s.last_used_at).toLocaleString()}</span><Button disabled={busy} onClick={() => void revoke(s)}>Revoke</Button></div>)}
      <Button disabled={busy} onClick={() => void revoke()}>Revoke all website sessions</Button>
    </CardContent></Card>}
    {user?.role === 'admin' && <PilotGrantForm />}
  </>;
}

function PilotGrantForm() {
  const [email, setEmail] = useState('');
  const [kind, setKind] = useState<'invite' | 'recovery'>('invite');
  const [grant, setGrant] = useState<{ token: string; expires_at: string }>();
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setGrant(undefined); setError('');
    try { setGrant(await apiRequest('/auth/pilot/grants', { method: 'POST', body: { email, kind } })); }
    catch (err) { setError(err instanceof Error ? err.message : 'Grant creation failed.'); }
    finally { setBusy(false); }
  }
  return <Card><CardHeader title="Pilot provisioning" description="Verify the recipient yourself. Deliver the token privately; no email is sent." /><CardContent>
    <form onSubmit={submit} className="space-y-3">
      <label className="block">Website email<input type="email" required value={email} onChange={e => { setEmail(e.target.value); setGrant(undefined); }} className="block w-full rounded border border-border bg-surface p-2" /></label>
      <label className="block">Purpose<select value={kind} onChange={e => { setKind(e.target.value as 'invite' | 'recovery'); setGrant(undefined); }} className="block rounded border border-border bg-surface p-2"><option value="invite">Invite new member</option><option value="recovery">Recover existing identity</option></select></label>
      <Button type="submit" loading={busy}>Create one-time token</Button>
      {error && <p role="alert">{error}</p>}
    </form>
    {grant && <div className="mt-4 space-y-2"><label className="block">One-time token<input readOnly value={grant.token} autoComplete="off" className="block w-full rounded border border-border bg-surface p-2" /></label><p>Redeem at /activate before {new Date(grant.expires_at).toLocaleString()}.</p><Button onClick={() => setGrant(undefined)}>Hide token</Button></div>}
  </CardContent></Card>;
}
