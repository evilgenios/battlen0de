'use client';

import { KeyRound, ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { IdentitySettings } from '@/components/settings/IdentitySettings';
import { Card, CardContent, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { LogoutButton } from '@/components/layout/LogoutButton';
import { useHealth } from '@/lib/hooks/useHealth';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <span className="text-sm text-muted-foreground">{label}</span>
      <div className="text-right text-sm font-medium text-foreground">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const { health, isDown, isLoading } = useHealth();
  const { user, isAuthenticated } = useAuthSession();
  const authRequired = health?.auth_required ?? true;

  return (
    <div className="space-y-5 sm:space-y-7">
      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10">
          <span className="command-eyebrow"><span className="command-dot text-accent" /> System settings</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground sm:text-4xl">Control & identity</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">
            Session identity, pilot access, API health, and local presentation settings in one place.
          </p>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title="Account" action={<KeyRound className="h-4 w-4 text-accent" />} />
          <CardContent className="divide-y divide-border/80">
            <Row label="Signed in as">{isAuthenticated ? user!.email : authRequired ? 'Not signed in' : '—'}</Row>
            <Row label="Role">{isAuthenticated ? <Badge tone="success">{user!.role}</Badge> : <Badge tone="neutral">—</Badge>}</Row>
            <Row label="Plan">
              {isAuthenticated && user?.plan
                ? <Badge tone={user.plan === 'alliance' ? 'info' : 'success'}>{user.plan === 'alliance' ? 'Alliance' : 'Individual'}</Badge>
                : <Badge tone="neutral">Legacy policy</Badge>}
            </Row>
            {isAuthenticated && user?.max_accounts != null && (
              <Row label="Account limits">
                {user.max_accounts} linked · {user.max_active_accounts ?? '—'} active
              </Row>
            )}
            {isAuthenticated && (
              <>
                <Row label="Active sessions">{user!.active_sessions}</Row>
                <div className="flex items-center justify-between py-3">
                  <span className="text-sm text-muted-foreground">Session</span>
                  <LogoutButton />
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader title="Backend / API" action={<ShieldCheck className="h-4 w-4 text-success" />} />
          <CardContent className="divide-y divide-border/80">
            <Row label="Status">
              {isLoading && !health ? <Badge tone="neutral">Checking…</Badge> : isDown ? <Badge tone="danger" dot>Unreachable</Badge> : <Badge tone="success" dot>Online</Badge>}
            </Row>
            <Row label="Database">
              {health?.database === 'ok' ? <Badge tone="success" dot>Connected</Badge> : <Badge tone="neutral">Unknown</Badge>}
            </Row>
            <Row label="Authentication">
              {authRequired ? <Badge tone="success" dot>Session enforced</Badge> : <Badge tone="warning">Local development</Badge>}
            </Row>
          </CardContent>
          {!authRequired && (
            <div className="border-t border-border/80 px-5 py-4 text-xs leading-5 text-muted-foreground sm:px-6">
              Explicit local authentication is enabled. Production requires a password session even before users are provisioned.
            </div>
          )}
        </Card>
      </div>

      <IdentitySettings />

      <Card>
        <CardHeader title="Application" action={<SlidersHorizontal className="h-4 w-4 text-info" />} />
        <CardContent className="divide-y divide-border/80">
          <Row label="Dashboard version">{process.env.NEXT_PUBLIC_APP_VERSION ?? 'dev'}</Row>
          <Row label="Environment">{process.env.NODE_ENV}</Row>
          <Row label="Theme"><ThemeToggle /></Row>
        </CardContent>
      </Card>
    </div>
  );
}
