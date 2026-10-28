'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Activity, Network, LayoutDashboard, Radar, Settings, ShieldCheck, ShieldEllipsis, Store, Users, X } from 'lucide-react';
import { cn } from '@/lib/utils/cn';
import { useAuthSession } from '@/lib/hooks/useAuthSession';

const NAV_ITEMS = [
  { href: '/dashboard', label: 'Individual', icon: LayoutDashboard, hint: '1 Base' },
  { href: '/alliance', label: 'Alliance', icon: Users, hint: 'Multi-Base' },
  { href: '/operations', label: 'Field Ops', icon: Radar, hint: 'Live movements' },
  { href: '/marketplace', label: 'Marketplace', icon: Store, hint: 'Commander discovery' },
  { href: '/accounts', label: 'Linked Bases', icon: Users, hint: 'Commander roster' },
  { href: '/events', label: 'Activity', icon: Activity, hint: 'Command log' },
  { href: '/settings', label: 'Node Settings', icon: Settings, hint: 'System' },
] as const;

const ADMIN_ITEM = { href: '/admin', label: 'Site Admin', icon: ShieldEllipsis, hint: 'Customers & security' } as const;

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function SidebarNav() {
  const pathname = usePathname();
  const { user } = useAuthSession();
  const items = user?.role === 'admin' ? [...NAV_ITEMS, ADMIN_ITEM] : NAV_ITEMS;

  return (
    <nav className="flex flex-1 flex-col gap-1.5 px-3 py-5">
      <p className="px-3 pb-2 font-mono text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/70">
        BattleN0de modules
      </p>
      {items.map(({ href, label, icon: Icon, hint }) => {
        const active = isActive(pathname, href);
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'group relative flex items-center gap-3 overflow-hidden rounded-xl border px-3 py-2.5 transition-all duration-200',
              active
                ? 'border-accent/25 bg-accent/10 text-foreground shadow-[0_8px_28px_color-mix(in_srgb,var(--color-accent)_10%,transparent)]'
                : 'border-transparent text-muted-foreground hover:border-border/70 hover:bg-surface-muted/60 hover:text-foreground',
            )}
          >
            {active && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-gradient-to-b from-info to-accent shadow-[0_0_14px_var(--color-accent)]" />}
            <span
              className={cn(
                'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors',
                active
                  ? 'border-accent/25 bg-accent/12 text-accent'
                  : 'border-border/70 bg-surface/40 text-muted-foreground group-hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold tracking-[-0.01em]">{label}</span>
              <span className="block text-[10px] text-muted-foreground/75">{hint}</span>
            </span>
          </Link>
        );
      })}
    </nav>
  );
}

export function SidebarBrand() {
  return (
    <div className="border-b border-border/70 px-4 py-4">
      <div className="flex items-center gap-3">
        <div className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl border border-accent/30 bg-accent/10 text-accent shadow-[0_0_32px_color-mix(in_srgb,var(--color-accent)_18%,transparent)]">
          <Network className="h-5 w-5" />
          <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-info to-transparent" />
        </div>
        <div className="min-w-0">
          <p className="truncate text-sm font-bold tracking-[-0.02em] text-foreground">battlen0de</p>
          <p className="font-mono text-[9px] font-semibold uppercase tracking-[0.2em] text-accent">Warpath AIO Command Hub</p>
        </div>
      </div>
    </div>
  );
}

function SidebarFooter() {
  return (
    <div className="m-3 rounded-xl border border-border/70 bg-surface-muted/45 p-3">
      <div className="flex items-center gap-2">
        <span className="live-dot h-2 w-2 rounded-full bg-success" />
        <span className="text-xs font-semibold text-foreground">BattleN0de online</span>
      </div>
      <div className="mt-2 flex items-center gap-2 text-[10px] text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5 text-success" />
        Authenticated session
      </div>
    </div>
  );
}

export function DesktopSidebar() {
  return (
    <aside className="premium-glass hidden w-72 shrink-0 flex-col border-r border-border/70 lg:flex">
      <SidebarBrand />
      <SidebarNav />
      <SidebarFooter />
    </aside>
  );
}

export function MobileSidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 lg:hidden">
      <div className="absolute inset-0 bg-[#02040a]/75 backdrop-blur-sm" onClick={onClose} aria-hidden="true" />
      <div className="premium-glass relative flex h-full w-[19rem] max-w-[86vw] flex-col border-r border-border shadow-2xl">
        <div className="flex items-start justify-between">
          <SidebarBrand />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="mr-3 mt-4 rounded-xl border border-border/70 bg-surface-muted/60 p-2 text-muted-foreground transition hover:text-foreground"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div onClick={onClose} className="flex flex-1 flex-col">
          <SidebarNav />
          <SidebarFooter />
        </div>
      </div>
    </div>
  );
}
