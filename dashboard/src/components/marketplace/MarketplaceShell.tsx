"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import {
  ArrowLeft,
  ArrowRight,
  GitCompareArrows,
  Network,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { useAuthSession } from "@/lib/hooks/useAuthSession";
import { marketplaceApi } from "@/lib/api/marketplace";
import { useMarketplace } from "./MarketplaceProvider";

export function MarketplaceShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, isAuthenticated } = useAuthSession();
  const { config, configError, comparison } = useMarketplace();
  const { data } = useSWR(
    isAuthenticated ? "marketplace-dashboard" : null,
    marketplaceApi.dashboard,
  );
  const moderator =
    user?.role === "admin" ||
    ["moderator", "marketplace_admin", "owner"].includes(
      data?.profile.staff_role ?? "",
    );
  const links = [
    ["/marketplace", "Discover"],
    ["/marketplace/favorites", "Saved listings"],
    ["/marketplace/dashboard", "Seller dashboard"],
    ["/marketplace/inbox", "Messages"],
    ...(moderator ? [["/marketplace/admin", "Review center"]] : []),
  ];
  return (
    <div className="marketplace min-h-screen">
      <header className="mp-header">
        <div className="mp-container flex h-20 items-center justify-between gap-3">
          <Link
            href="/"
            className="flex items-center gap-3"
            aria-label="BattleN0de home"
          >
            <span className="mp-brand-mark">
              <Network size={22} />
            </span>
            <span>
              <strong className="block text-lg tracking-[-0.06em]">
                battlen0de<span className="text-accent">.</span>
              </strong>
              <span className="mp-kicker !text-[8px]">
                Commander marketplace
              </span>
            </span>
          </Link>
          <div className="flex items-center gap-2 sm:gap-4">
            <Link
              href={isAuthenticated ? "/dashboard" : "/login"}
              className="mp-back-link hidden sm:inline-flex"
            >
              <ArrowLeft size={14} />{" "}
              {isAuthenticated ? "Command hub" : "Sign in"}
            </Link>
            <ThemeToggle />
            <Link
              href="/marketplace/sell"
              className="mp-button mp-button-primary"
            >
              <Plus size={16} /> Create listing
            </Link>
          </div>
        </div>
      </header>
      <div className="border-b border-border/70 bg-surface/50">
        <div className="mp-container flex items-center justify-between gap-6">
          <nav aria-label="Marketplace navigation" className="mp-tabs">
            {links.map(([href, label]) => (
              <Link
                key={href}
                href={href}
                aria-current={
                  (
                    href === "/marketplace"
                      ? pathname === href
                      : pathname.startsWith(href)
                  )
                    ? "page"
                    : undefined
                }
              >
                {label}
              </Link>
            ))}
          </nav>
          <span className="mp-status hidden shrink-0 sm:inline-flex">
            <span />
            {config?.mode === "live" ? "Marketplace live" : "Preview edition"}
          </span>
        </div>
      </div>
      <main id="marketplace-main" className="mp-container py-8 sm:py-11">
        {children}
      </main>
      <footer className="mp-container mp-footer">
        <div className="flex items-center gap-2">
          <ShieldCheck size={16} className="text-accent" />
          <span>One identity. A dedicated marketplace.</span>
        </div>
        <div className="flex flex-wrap gap-5">
          <Link href="/terms">Terms</Link>
          <Link href="/privacy">Privacy</Link>
          <Link href="/">
            BattleN0de home <ArrowRight size={12} className="inline" />
          </Link>
        </div>
      </footer>
      {comparison.length > 0 && pathname !== "/marketplace/compare" && (
        <div className="mp-compare-tray" role="status">
          <GitCompareArrows size={20} />
          <span>
            <strong>{comparison.length} of 3</strong> commanders selected
          </span>
          <Link
            href="/marketplace/compare"
            className="mp-button mp-button-primary"
          >
            Compare <ArrowRight size={14} />
          </Link>
        </div>
      )}
      {configError && (
        <div className="mp-connection-note" role="status">
          Marketplace service unavailable. You can explore the sample catalog.
        </div>
      )}
    </div>
  );
}

export function MemberOnly({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated } = useAuthSession();
  if (isLoading)
    return (
      <div className="mp-empty" role="status">
        Checking your session…
      </div>
    );
  if (!isAuthenticated)
    return (
      <div className="mp-panel mp-empty">
        <ShieldCheck size={32} className="text-accent" />
        <p className="mp-kicker mt-5">Your BattleN0de identity</p>
        <h1>Sign in to your marketplace workspace.</h1>
        <p>
          Use your existing account to manage listings and private
          conversations.
        </p>
        <Link href="/login" className="mp-button mp-button-primary mt-5">
          Sign in <ArrowRight size={16} />
        </Link>
        <Link
          href="/marketplace"
          className="mt-4 text-sm text-muted-foreground"
        >
          Back to the marketplace
        </Link>
      </div>
    );
  return <>{children}</>;
}

export function MarketplaceError({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  return (
    <div role="alert" className="mp-error">
      <p>
        {error instanceof Error
          ? error.message
          : "Something went wrong. Please try again."}
      </p>
      {retry && (
        <button type="button" className="mt-2 underline" onClick={retry}>
          Try again
        </button>
      )}
    </div>
  );
}
