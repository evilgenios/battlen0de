'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { MembershipRoleBadge } from './MembershipRoleBadge';
import { UpcomingToolsPanel } from '@/components/accounts/UpcomingToolsPanel';
import { Menu } from 'lucide-react';
import { DesktopSidebar, MobileSidebar } from '@/components/layout/Sidebar';
import { ThemeToggle } from '@/components/layout/ThemeToggle';
import { HealthIndicator } from '@/components/layout/HealthIndicator';
import { useAuthSession } from '@/lib/hooks/useAuthSession';
import { WarpathBackground } from '@/components/layout/WarpathBackground';

function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { isLoading: sessionLoading, isAuthenticated, unauthenticated } = useAuthSession();
  const isLoginPage = pathname === '/login';
  const isActivationPage = pathname === '/activate';
  const isLoading = sessionLoading;
  const mustLogIn = unauthenticated;

  useEffect(() => {
    if (isLoading) return;
    if (mustLogIn && !isLoginPage && !isActivationPage) router.replace('/login');
    if (isAuthenticated && isLoginPage) router.replace('/dashboard');
  }, [isLoading, mustLogIn, isAuthenticated, isLoginPage, isActivationPage, router]);

  if (isLoginPage || isActivationPage) return <>{children}</>;
  if (isLoading) return null;
  if (!isAuthenticated) return null;
  return <>{children}</>;
}

const SECTION_LABELS: Record<string, string> = {
  '/dashboard': 'Individual BattleN0de',
  '/alliance': 'Alliance BattleN0de',
  '/operations': 'Field operations',
  '/accounts': 'Linked Bases',
  '/events': 'Command activity',
  '/settings': 'Node settings',
  '/admin': 'Site administration',
};

function sectionLabel(pathname: string): string {
  if (SECTION_LABELS[pathname]) return SECTION_LABELS[pathname];
  if (pathname.startsWith('/accounts/')) return 'Base detail';
  return 'BattleN0de';
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user } = useAuthSession();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const pathname = usePathname();

  if (['/', '/terms', '/privacy', '/refunds'].includes(pathname)) return <>{children}</>;

  if (pathname === '/login' || pathname === '/activate') {
    return (
      <AuthGate>
        <WarpathBackground />
        {children}
      </AuthGate>
    );
  }

  return (
    <AuthGate>
      <WarpathBackground />
      <div className="flex min-h-screen">
        <DesktopSidebar />
        <MobileSidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} />

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="premium-glass sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border/70 px-4 sm:px-6 lg:px-8">
            <div className="flex min-w-0 items-center gap-3">
              <button
                type="button"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation"
                className="rounded-xl border border-border/70 bg-surface-muted/50 p-2 text-muted-foreground hover:text-foreground lg:hidden"
              >
                <Menu className="h-5 w-5" />
              </button>
              <div className="hidden min-w-0 sm:block">
                <p className="font-mono text-[9px] font-bold uppercase tracking-[0.22em] text-accent">BATTLE // N0DE</p>
                <p className="truncate text-xs font-medium text-muted-foreground">{sectionLabel(pathname)}</p>
              </div>
            </div>

            <div className="flex items-center gap-2 sm:gap-3">
              <MembershipRoleBadge />
              <HealthIndicator />
              <div className="h-5 w-px bg-border/80" />
              <ThemeToggle />
            </div>
          </header>

          <main className="flex-1 px-4 py-5 sm:px-6 sm:py-7 lg:px-8">
            <div className="mx-auto w-full max-w-[1440px] space-y-5 sm:space-y-7">
              {children}
              {user?.role === 'member' && ['/dashboard', '/alliance'].includes(pathname) && <UpcomingToolsPanel />}
            </div>
          </main>
        </div>
      </div>
    </AuthGate>
  );
}

