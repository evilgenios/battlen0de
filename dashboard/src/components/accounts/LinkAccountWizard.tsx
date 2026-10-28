'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, Mail, ShieldCheck } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api/client';
import { requestLinkCode, verifyLinkCode } from '@/lib/api/link';

type Step = 'email' | 'code' | 'success';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/** Client-side mirror of the backend's default resend cooldown
 * (LinkChallengeStore's DEFAULT_RESEND_COOLDOWN_SECONDS) — purely a UX
 * hint (disables the button so a user doesn't immediately hit the real
 * 429), not the actual enforcement, which is server-side and authoritative
 * regardless of what this countdown shows. */
const RESEND_COOLDOWN_HINT_SECONDS = 30;

function describeLinkError(error: unknown, fallback: string): { title: string; detail: string } {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 422:
        return { title: 'Incorrect code', detail: error.message || 'That verification code is not correct.' };
      case 410:
        return { title: 'Code expired', detail: 'This verification code has expired. Request a new one.' };
      case 429:
        return { title: 'Too many attempts', detail: error.message || 'Please slow down and try again shortly.' };
      case 503:
        return { title: 'Service unavailable', detail: error.message || 'Could not reach the Warpath account service.' };
      case 0:
        return { title: 'Network error', detail: 'Could not reach the dashboard server. Check your connection.' };
      default:
        return { title: fallback, detail: error.message };
    }
  }
  return { title: fallback, detail: 'Something went wrong.' };
}

export function LinkAccountWizard({ accountId }: { accountId?: string } = {}) {
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [challengeId, setChallengeId] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<{ title: string; detail: string } | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);
  const cooldownTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  const router = useRouter();
  const toast = useToast();

  useEffect(() => {
    return () => {
      if (cooldownTimer.current) clearInterval(cooldownTimer.current);
    };
  }, []);

  function startCooldown() {
    setResendCooldown(RESEND_COOLDOWN_HINT_SECONDS);
    if (cooldownTimer.current) clearInterval(cooldownTimer.current);
    cooldownTimer.current = setInterval(() => {
      setResendCooldown((seconds) => {
        if (seconds <= 1) {
          if (cooldownTimer.current) clearInterval(cooldownTimer.current);
          return 0;
        }
        return seconds - 1;
      });
    }, 1000);
  }

  async function sendCode(targetEmail: string) {
    if (submitting) return;
    setFormError(null);
    setSubmitting(true);
    try {
      const result = await requestLinkCode({ email: targetEmail, ...(accountId ? { account_id: accountId } : {}), ...(challengeId ? { challenge_id: challengeId } : {}) });
      setChallengeId(result.challenge_id);
      setEmail(result.email);
      setStep('code');
      startCooldown();
    } catch (error) {
      setFormError(describeLinkError(error, 'Could not send the verification code'));
      if (error instanceof ApiError && error.status === 410) setChallengeId(null);
    } finally {
      setSubmitting(false);
    }
  }

  function handleEmailSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = email.trim().toLowerCase();
    if (!EMAIL_PATTERN.test(trimmed)) {
      setEmailError('Enter a valid email address.');
      return;
    }
    setEmailError(null);
    void sendCode(trimmed);
  }

  async function handleVerifySubmit(event: React.FormEvent) {
    event.preventDefault();
    if (submitting || !challengeId) return;
    if (!/^\d{6}$/.test(code)) {
      setFormError({ title: 'Invalid code', detail: 'Enter the 6-digit code from your email.' });
      return;
    }
    setFormError(null);
    setSubmitting(true);
    try {
      const account = await verifyLinkCode({ challenge_id: challengeId, code });
      setStep('success');
      toast.success('Account linked', `${account.label} is ready to connect.`);
      setTimeout(() => router.push(`/accounts/${account.id}`), 1200);
    } catch (error) {
      const described = describeLinkError(error, 'Verification failed');
      setFormError(described);
      if (error instanceof ApiError && error.status === 410) {
        // The challenge itself is gone server-side — starting over is the
        // only path forward, so don't leave the user stuck re-typing a
        // code that can never succeed.
        setChallengeId(null);
      }
    } finally {
      setSubmitting(false);
    }
  }

  function handleResend() {
    if (resendCooldown > 0) return;
    void sendCode(email);
  }

  function handleChangeEmail() {
    setStep('email');
    setChallengeId(null);
    setCode('');
    setFormError(null);
    if (cooldownTimer.current) clearInterval(cooldownTimer.current);
    setResendCooldown(0);
  }

  if (step === 'success') {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/15">
            <CheckCircle2 className="h-6 w-6 text-success" />
          </div>
          <p className="text-sm font-medium text-foreground">Account linked</p>
          <p className="text-sm text-muted-foreground">Taking you to the account…</p>
        </CardContent>
      </Card>
    );
  }

  if (step === 'code') {
    return (
      <Card>
        <CardHeader
          title="Check your email"
          description={
            <>
              We sent a verification code to <span className="font-medium text-foreground">{email}</span>.
            </>
          }
        />
        <CardContent>
          <form onSubmit={handleVerifySubmit} className="space-y-4" noValidate>
            <label className="block">
              <span className="mb-1.5 block text-sm font-medium text-foreground">Verification code</span>
              <input
                className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-center text-lg tracking-[0.4em] text-foreground placeholder:tracking-normal placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                value={code}
                onChange={(event) => setCode(event.target.value.replace(/\D/g, '').slice(0, 6))}
                placeholder="000000"
                inputMode="numeric"
                autoComplete="one-time-code"
                autoFocus
                maxLength={6}
              />
            </label>

            {formError && (
              <div className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
                <p className="font-medium">{formError.title}</p>
                <p className="text-xs opacity-90">{formError.detail}</p>
              </div>
            )}

            <Button type="submit" variant="primary" className="w-full" loading={submitting} disabled={code.length !== 6}>
              Verify &amp; Link Account
            </Button>

            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <button type="button" onClick={handleChangeEmail} className="hover:text-foreground hover:underline">
                Use a different email
              </button>
              <button
                type="button"
                onClick={handleResend}
                disabled={resendCooldown > 0 || submitting}
                className="hover:text-foreground hover:underline disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:no-underline"
              >
                {resendCooldown > 0 ? `Resend code (${resendCooldown}s)` : 'Resend code'}
              </button>
            </div>
          </form>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Link a Warpath Account" description="Enter the email for the Warpath account you want to add." />
      <CardContent>
        <form onSubmit={handleEmailSubmit} className="space-y-4" noValidate>
          <label className="block">
            <span className="mb-1.5 block text-sm font-medium text-foreground">Email</span>
            <div className="relative">
              <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                className="w-full rounded-lg border border-border bg-surface py-2 pl-9 pr-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                autoFocus
              />
            </div>
            {emailError && <span className="mt-1 block text-xs text-danger">{emailError}</span>}
          </label>

          {formError && (
            <div className="rounded-lg border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger">
              <p className="font-medium">{formError.title}</p>
              <p className="text-xs opacity-90">{formError.detail}</p>
            </div>
          )}

          <Button type="submit" variant="primary" icon={<ShieldCheck className="h-4 w-4" />} className="w-full" loading={submitting}>
            Send Verification Code
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
