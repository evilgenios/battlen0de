'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Network, Fingerprint, LogIn, RadioTower, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { ApiError } from '@/lib/api/client';
import { login } from '@/lib/api/auth';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

const inputClass =
  'w-full rounded-xl border border-border/80 bg-surface/60 px-3.5 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground/50 focus:border-accent/50 focus:ring-4 focus:ring-accent/10';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [mfaCode, setMfaCode] = useState('');
  const [mfaRequired, setMfaRequired] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();
  const { refresh } = useAuthSession();

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;
    setError(null);
    if (!email.trim() || !password.trim()) {
      setError('Email and password are required.');
      return;
    }
    setPending(true);
    try {
      await login({ email, password, ...(mfaCode ? { mfa_code: mfaCode } : {}) });
      await refresh();
      router.push('/dashboard');
    } catch (err) {
      if (err instanceof ApiError && err.message === 'mfa required') {
        setMfaRequired(true);
        setError('Enter the 6-digit code from your authenticator app.');
      } else {
        setError(err instanceof ApiError ? err.message : 'Could not reach the dashboard server.');
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-8 sm:px-6">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_10%,color-mix(in_srgb,var(--color-accent)_16%,transparent),transparent_30rem),radial-gradient(circle_at_90%_80%,color-mix(in_srgb,var(--color-info)_10%,transparent),transparent_32rem)]" />

      <div className="relative grid w-full max-w-6xl overflow-hidden rounded-[1.75rem] border border-border/80 bg-surface/55 shadow-[0_40px_120px_rgba(0,0,0,.22)] backdrop-blur-2xl lg:grid-cols-[1.08fr_.92fr]">
        <section className="command-hero relative hidden min-h-[42rem] overflow-hidden border-r border-border/70 p-10 lg:flex lg:flex-col lg:justify-between">
          <div className="scan-line" />
          <div className="relative z-10">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent shadow-[0_0_34px_color-mix(in_srgb,var(--color-accent)_20%,transparent)]">
                <Network className="h-5 w-5" />
              </span>
              <div>
                <p className="text-sm font-bold tracking-[-0.02em] text-foreground">battlen0de</p>
                <p className="font-mono text-[9px] font-bold uppercase tracking-[0.22em] text-accent">Warpath AIO Command Hub</p>
              </div>
            </div>

            <h1 className="mt-16 max-w-lg text-5xl font-semibold leading-[0.98] tracking-[-0.065em] text-foreground">
              Your Base. One BattleN0de.
            </h1>
            <p className="mt-5 max-w-md text-sm leading-6 text-muted-foreground">
              One Warpath command node for Base status, Production Buildings, Collection Convoys, Conquest Guard and account operations.
            </p>
          </div>

          <div className="relative z-10 grid gap-3">
            {[
              { icon: RadioTower, title: 'Base command view', body: 'Base state and field operations refresh in one surface.' },
              { icon: ShieldCheck, title: 'Conquest-safe controls', body: 'Commands surface confirmed state and Conquest Guard stays explicit.' },
              { icon: Fingerprint, title: 'Commander identity', body: 'One Warpath identity maps to one BattleN0de.' },
            ].map(({ icon: Icon, title, body }) => (
              <div key={title} className="data-chip flex items-center gap-3 rounded-xl p-3.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-accent/20 bg-accent/8 text-accent">
                  <Icon className="h-4 w-4" />
                </span>
                <div>
                  <p className="text-xs font-semibold text-foreground">{title}</p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{body}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="flex min-h-[36rem] items-center p-6 sm:p-10 lg:p-12">
          <div className="mx-auto w-full max-w-sm">
            <div className="mb-8 lg:hidden">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 text-accent">
                <Network className="h-5 w-5" />
              </span>
            </div>

            <span className="command-eyebrow"><span className="command-dot text-success" /> Secure access</span>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground">Welcome back</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">Sign in to enter your BattleN0de.</p>

            <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-foreground">Email</span>
                <input
                  className={inputClass}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  required
                  placeholder="operator@example.com"
                />
              </label>
              <label className="block">
                <span className="mb-1.5 block text-xs font-semibold text-foreground">Password</span>
                <input
                  className={inputClass}
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  required
                  placeholder="••••••••••••"
                />
              </label>

              {mfaRequired && (
                <label className="block">
                  <span className="mb-1.5 block text-xs font-semibold text-foreground">Authenticator code</span>
                  <input
                    className={inputClass}
                    type="text"
                    inputMode="numeric"
                    pattern="[0-9]{6}"
                    maxLength={6}
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                    autoComplete="one-time-code"
                    required
                    placeholder="123456"
                  />
                  <span className="mt-1.5 block text-[10px] leading-4 text-muted-foreground">
                    Required for administrator identities with MFA enabled.
                  </span>
                </label>
              )}

              {error && (
                <div className="rounded-xl border border-danger/30 bg-danger/8 px-3.5 py-2.5 text-sm text-danger">{error}</div>
              )}

              <Button type="submit" variant="primary" icon={<LogIn className="h-4 w-4" />} className="mt-2 w-full" loading={pending}>
                Sign in to command center
              </Button>
            </form>

            <div className="mt-6 flex items-center gap-2 text-[11px] leading-5 text-muted-foreground">
              <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-success" />
              Password sessions, CSRF protection, and role checks are enforced by the API.
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
