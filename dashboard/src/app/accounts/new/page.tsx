import Link from 'next/link';
import { ArrowLeft, Fingerprint, Link2 } from 'lucide-react';
import { AccountLinkGate } from '@/components/accounts/AccountLinkGate';

export default function NewAccountPage() {
  return (
    <div className="mx-auto max-w-2xl space-y-5 sm:space-y-7">
      <Link href="/accounts" className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition hover:text-foreground">
        <ArrowLeft className="h-4 w-4" />
        Back to account fleet
      </Link>

      <section className="command-hero premium-panel rounded-[1.5rem] p-6 sm:p-8">
        <div className="relative z-10">
          <span className="command-eyebrow"><span className="command-dot text-accent" /> Identity link</span>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-foreground">Add a Warpath account</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
            Link through the owner-bound verification flow. Credentials remain server-side and the canonical game identity is globally unique.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground"><Link2 className="h-3.5 w-3.5 text-info" /> owner-bound challenge</span>
            <span className="data-chip inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted-foreground"><Fingerprint className="h-3.5 w-3.5 text-accent" /> canonical identity</span>
          </div>
        </div>
      </section>

      <AccountLinkGate />
    </div>
  );
}
