import Link from 'next/link';
import { ArrowLeft, Network, ShieldCheck } from 'lucide-react';
import { MarketingBackdrop } from '@/components/marketing/MarketingBackdrop';

export interface LegalSection {
  title: string;
  body: React.ReactNode;
}

export function MarketingLegalPage({
  eyebrow,
  title,
  intro,
  sections,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  sections: LegalSection[];
}) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#03050b] text-white">
      <MarketingBackdrop />
      <div className="landing-grid pointer-events-none fixed inset-0 z-0 opacity-45" />
      <div className="landing-orbit landing-orbit-a pointer-events-none fixed z-0 opacity-50" />

      <header className="relative z-20 border-b border-white/[0.06] bg-[#03050b]/55 backdrop-blur-2xl">
        <div className="mx-auto flex h-[72px] max-w-[1180px] items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-3">
            <span className="landing-logo relative flex h-9 w-9 items-center justify-center overflow-hidden rounded-xl border border-violet-400/30 bg-violet-400/10 text-violet-200">
              <Network className="h-4 w-4" />
              <span className="absolute inset-x-1 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
            </span>
            <span>
              <span className="block text-sm font-bold tracking-[-0.03em] text-white">battlen0de</span>
              <span className="block font-mono text-[9px] font-bold uppercase tracking-[0.22em] text-violet-300">Warpath AIO Command Hub</span>
            </span>
          </Link>

          <Link href="/" className="inline-flex items-center gap-2 rounded-xl border border-white/[0.075] bg-white/[0.025] px-3 py-2 text-xs font-semibold text-slate-300 transition hover:border-violet-300/20 hover:text-white">
            <ArrowLeft className="h-3.5 w-3.5" /> Back to site
          </Link>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-[1040px] px-4 pb-28 pt-16 sm:px-6 sm:pt-20">
        <div className="max-w-3xl">
          <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-violet-300">{eyebrow}</p>
          <h1 className="mt-4 text-4xl font-semibold tracking-[-0.06em] text-white sm:text-6xl">{title}</h1>
          <p className="mt-5 max-w-2xl text-sm leading-7 text-slate-400">{intro}</p>
          <div className="mt-5 flex items-center gap-2 text-[10px] font-medium uppercase tracking-[0.12em] text-slate-600">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />
            Last updated 28 September 2026
          </div>
        </div>

        <div className="mt-12 space-y-3">
          {sections.map((section, index) => (
            <section key={section.title} className="marketing-legal-panel relative overflow-hidden rounded-2xl p-5 sm:p-6">
              <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-violet-400 via-cyan-300 to-transparent opacity-55" />
              <div className="grid gap-4 sm:grid-cols-[56px_1fr]">
                <span className="font-mono text-[10px] font-bold tracking-[0.16em] text-violet-300">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <div>
                  <h2 className="text-lg font-semibold tracking-[-0.025em] text-slate-100">{section.title}</h2>
                  <div className="mt-3 space-y-3 text-sm leading-7 text-slate-400">{section.body}</div>
                </div>
              </div>
            </section>
          ))}
        </div>

        <div className="mt-10 flex flex-wrap gap-4 text-xs text-slate-500">
          <Link href="/terms" className="transition hover:text-white">Terms</Link>
          <Link href="/privacy" className="transition hover:text-white">Privacy</Link>
          <Link href="/refunds" className="transition hover:text-white">Refunds</Link>
        </div>
      </main>
    </div>
  );
}
