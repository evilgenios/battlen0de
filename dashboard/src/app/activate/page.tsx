'use client';

import { useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, KeyRound, ShieldCheck } from 'lucide-react';
import { apiRequest } from '@/lib/api/client';
import { Button } from '@/components/ui/Button';

const inputClass =
  'mt-1.5 block w-full rounded-xl border border-border/80 bg-surface/60 px-3.5 py-2.5 text-sm text-foreground outline-none transition focus:border-accent/50 focus:ring-4 focus:ring-accent/10';

export default function ActivatePage() {
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (password !== confirm) {
      setError('Passwords must match.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      await apiRequest('/auth/pilot/redeem', { method: 'POST', body: { token: token.trim(), password } });
      setToken('');
      setPassword('');
      setConfirm('');
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not redeem access token.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_15%,color-mix(in_srgb,var(--color-accent)_14%,transparent),transparent_28rem),radial-gradient(circle_at_80%_85%,color-mix(in_srgb,var(--color-info)_8%,transparent),transparent_30rem)]" />
      <div className="premium-panel premium-glass relative w-full max-w-lg rounded-[1.5rem] p-6 shadow-[0_30px_100px_rgba(0,0,0,.2)] sm:p-8">
        <span className="command-eyebrow"><span className="command-dot text-success" /> Identity activation</span>
        <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground">Pilot access / recovery</h1>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">
          Use the one-time token supplied by your BattleN0de operator. Tokens are never placed in URLs.
        </p>

        {done ? (
          <div className="mt-8 rounded-2xl border border-success/25 bg-success/8 p-5">
            <CheckCircle2 className="h-6 w-6 text-success" />
            <p className="mt-3 text-sm font-semibold text-foreground">Password saved</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">Existing sessions were revoked. Sign in again with your new password.</p>
            <Link href="/login" className="mt-4 inline-flex text-sm font-semibold text-accent hover:text-info">Sign in</Link>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-8 space-y-4">
            <label className="block text-xs font-semibold text-foreground">
              Access token
              <input type="password" required autoComplete="off" maxLength={128} value={token} onChange={(e) => setToken(e.target.value)} className={inputClass} />
            </label>
            <label className="block text-xs font-semibold text-foreground">
              New password
              <input type="password" required autoComplete="new-password" minLength={12} maxLength={256} value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} />
            </label>
            <label className="block text-xs font-semibold text-foreground">
              Confirm password
              <input type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputClass} />
            </label>
            {error && <p role="alert" className="rounded-xl border border-danger/25 bg-danger/8 p-3 text-sm text-danger">{error}</p>}
            <Button type="submit" loading={busy} variant="primary" icon={<KeyRound className="h-4 w-4" />} className="w-full">
              Set password
            </Button>
          </form>
        )}

        <div className="mt-6 flex gap-2 text-[11px] leading-5 text-muted-foreground">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" />
          Redemption is one-time and revokes existing website sessions as part of the identity flow.
        </div>
      </div>
    </main>
  );
}
