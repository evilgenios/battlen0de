'use client';

import { usePathname } from 'next/navigation';
import { AppShell } from '@/components/layout/AppShell';
import { AuthSessionProvider } from '@/components/layout/AuthSessionProvider';

const PUBLIC_ROUTES = new Set(['/', '/terms', '/privacy', '/refunds']);

export function SiteBoundary({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (PUBLIC_ROUTES.has(pathname)) {
    return <>{children}</>;
  }

  if (pathname === '/marketplace' || pathname.startsWith('/marketplace/')) {
    return <AuthSessionProvider>{children}</AuthSessionProvider>;
  }

  return (
    <AuthSessionProvider>
      <AppShell>{children}</AppShell>
    </AuthSessionProvider>
  );
}
