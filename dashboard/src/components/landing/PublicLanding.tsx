import Link from 'next/link';
import {
  Activity,
  ArrowRight,
  Boxes,
  ChevronRight,
  Network,
  Fingerprint,
  Gauge,
  LockKeyhole,
  PackageCheck,
  Radar,
  RadioTower,
  ShieldCheck,
  Sparkles,
  Users,
  Zap,
} from 'lucide-react';
import { MarketingFaq } from '@/components/marketing/MarketingFaq';
import { MarketingMotionRoot } from '@/components/marketing/MarketingMotionRoot';
import { InteractiveDashboardDemo } from '@/components/landing/InteractiveDashboardDemo';
import { ImmersiveMissionSection } from '@/components/landing/ImmersiveMissionSection';

const FEATURE_CARDS = [
  {
    icon: Gauge,
    eyebrow: 'Base command',
    title: 'Your Base, always in view.',
    body: 'Connection state, Commander identity, active movements and account health live inside one BattleN0de instead of being scattered across separate screens.',
  },
  {
    icon: PackageCheck,
    eyebrow: 'Production Buildings',
    title: 'Treasury. Steelworks. Oil Reserve. One queue view.',
    body: 'Track the Production Buildings that generate Military Funds, Steel and Crude Oil, with grouped status, progress and collection visibility.',
  },
  {
    icon: Radar,
    eyebrow: 'Field operations',
    title: 'Collection Convoys and Scout Plane telemetry without the clutter.',
    body: 'See active movement and Scout Plane telemetry from the same command deck. Game-changing controls only appear when the server has explicitly verified and enabled them.',
  },
  {
    icon: ShieldCheck,
    eyebrow: 'Conquest Guard',
    title: 'Theater of Conquest protection state, without false success claims.',
    body: 'Keep Conquest Guard state account-scoped and visible. Automatic protection remains safety-gated until its upstream command evidence is verified.',
  },
  {
    icon: Fingerprint,
    eyebrow: 'Commander identity',
    title: 'One Warpath identity maps to one secure node.',
    body: 'Owner-bound linking and canonical game identity keep linked accounts isolated while the cloud session stays server-side.',
  },
  {
    icon: Users,
    eyebrow: 'Alliance node',
    title: 'Need multiple accounts? Scale the node.',
    body: 'Alliance is the separate multi-account control surface for players who need fleet-wide visibility across several linked Warpath accounts.',
  },
] as const;

const FLOW = [
  { number: '01', title: 'Link your Commander', body: 'Bind one Warpath account to your BattleN0de through the owner-bound verification flow.', icon: Fingerprint },
  { number: '02', title: 'Run the Base', body: 'Watch Production Buildings, Collection Convoys, Scout Plane activity, connection telemetry and events from one node.', icon: RadioTower },
  { number: '03', title: 'Scale to Alliance', body: 'Move into the Alliance node when you need a multi-account control surface instead of a single-Base cockpit.', icon: Users },
] as const;

function BrandMark({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <span className={`landing-logo relative flex ${compact ? 'h-9 w-9' : 'h-11 w-11'} items-center justify-center overflow-hidden rounded-xl border border-violet-400/30 bg-violet-400/10 text-violet-200`}>
        <Network className={compact ? 'h-4 w-4' : 'h-5 w-5'} />
        <span className="absolute inset-x-1 bottom-0 h-px bg-gradient-to-r from-transparent via-cyan-300 to-transparent" />
      </span>
      <span>
        <span className="block text-sm font-bold tracking-[-0.03em] text-white">battlen0de</span>
        <span className="block font-mono text-[9px] font-bold uppercase tracking-[0.24em] text-violet-300">Warpath AIO Command Hub</span>
      </span>
    </div>
  );
}


export function PublicLanding() {
  return (
    <MarketingMotionRoot>

      <header className="landing-nav fixed inset-x-0 top-0 z-50 border-b border-white/[0.06] bg-[#03050b]/55 backdrop-blur-2xl">
        <div className="mx-auto flex h-[72px] max-w-[1420px] items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" aria-label="BattleN0de home">
            <BrandMark compact />
          </Link>

          <nav className="hidden items-center gap-7 md:flex">
            <a href="#experience" className="text-xs font-medium text-slate-400 transition hover:text-white">Experience</a>
            <a href="#platform" className="text-xs font-medium text-slate-400 transition hover:text-white">Platform</a>
            <a href="#features" className="text-xs font-medium text-slate-400 transition hover:text-white">Features</a>
            <a href="#plans" className="text-xs font-medium text-slate-400 transition hover:text-white">Plans</a>
            <Link href="/marketplace" className="text-xs font-medium text-violet-300 transition hover:text-white">Marketplace</Link>
            <a href="#workflow" className="text-xs font-medium text-slate-400 transition hover:text-white">How it works</a>
            <a href="#faq" className="text-xs font-medium text-slate-400 transition hover:text-white">FAQ</a>
          </nav>

          <div className="flex items-center gap-2">
            <Link href="/login" className="rounded-xl px-3 py-2 text-xs font-semibold text-slate-300 transition hover:bg-white/[0.04] hover:text-white">
              Sign in
            </Link>
            <Link
              href="/activate"
              className="landing-cta inline-flex items-center gap-2 rounded-xl border border-violet-300/25 bg-violet-400/10 px-3.5 py-2 text-xs font-semibold text-violet-100 shadow-[0_0_30px_rgba(124,108,255,.12)] transition hover:border-violet-200/45 hover:bg-violet-400/15"
            >
              Activate your node <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      <main className="relative z-10">
        <section className="relative mx-auto flex min-h-[940px] max-w-[1500px] flex-col items-center px-4 pb-24 pt-36 sm:px-6 lg:px-8 lg:pt-40">
          <div className="landing-beam pointer-events-none absolute left-1/2 top-[12%] h-[620px] w-[1100px] -translate-x-1/2 rounded-full" />
          <div className="landing-hero-copy relative z-10 mx-auto max-w-5xl text-center">
            <div className="landing-pill mx-auto inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.035] px-3.5 py-2 shadow-[0_0_40px_rgba(124,108,255,.08)] backdrop-blur-xl">
              <Sparkles className="h-3.5 w-3.5 text-violet-300" />
              <span className="font-mono text-[9px] font-bold uppercase tracking-[0.18em] text-slate-300">PUBLIC BETA · INVITE ACCESS</span>
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_12px_#6ee7b7]" />
            </div>

            <h1 className="landing-title mt-7 text-[3.1rem] font-semibold leading-[0.92] tracking-[-0.075em] text-white sm:text-[4.9rem] lg:text-[6.2rem]">
              Your Base.
              <span className="landing-gradient-text block">One BattleN0de.</span>
            </h1>

            <p className="landing-copy mx-auto mt-7 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
              Track Production Buildings, Collection Convoys, Scout Plane telemetry and live connection state from one cloud node. BattleN0de stays fail-closed when an in-game command has not been verified safe.
            </p>

            <div className="landing-actions mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href="/activate"
                className="landing-primary-button group inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-violet-300/30 bg-gradient-to-r from-violet-500 to-indigo-500 px-5 text-sm font-semibold text-white shadow-[0_16px_60px_rgba(109,86,255,.24)] transition hover:-translate-y-0.5 hover:shadow-[0_20px_70px_rgba(109,86,255,.34)]"
              >
                Activate Individual access
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <a
                href="#platform"
                className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/[0.09] bg-white/[0.035] px-5 text-sm font-semibold text-slate-200 backdrop-blur-xl transition hover:border-white/[0.16] hover:bg-white/[0.055]"
              >
                See how it works
                <Radar className="h-4 w-4 text-slate-500" />
              </a>
            </div>
          </div>

          <div className="landing-console-wrap relative z-10 mt-20 w-full">
            <InteractiveDashboardDemo />
          </div>

          <div className="landing-marquee-shell absolute inset-x-0 bottom-0 overflow-hidden border-y border-white/[0.055] bg-white/[0.012] py-3">
            <div className="landing-marquee flex w-max items-center gap-10 pr-10 font-mono text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-600">
              {[0, 1].map((copy) => (
                <div key={copy} className="flex items-center gap-10">
                  <span>Individual · 1 account</span><span className="text-violet-500">◆</span>
                  <span>Personal live telemetry</span><span className="text-cyan-500">◆</span>
                  <span>Production queues</span><span className="text-amber-400">◆</span>
                  <span>Secure account identity</span><span className="text-emerald-400">◆</span>
                  <span>Account activity</span><span className="text-violet-500">◆</span>
                  <span>Alliance upgrade path</span><span className="text-cyan-500">◆</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <ImmersiveMissionSection />

        <section id="platform" className="mx-auto max-w-[1420px] px-4 py-28 sm:px-6 lg:px-8">
          <div className="grid gap-16 lg:grid-cols-[.8fr_1.2fr] lg:items-center">
            <div className="landing-reveal">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-violet-300">Warpath command layer</p>
              <h2 className="mt-4 max-w-lg text-4xl font-semibold leading-[1.02] tracking-[-0.055em] text-white sm:text-5xl">
                Built around your Base, not a generic admin panel.
              </h2>
              <p className="mt-5 max-w-lg text-sm leading-7 text-slate-400">
                BattleN0de turns one Warpath account into a focused cloud node: Base state, Production Buildings, Collection Convoys, Scout Plane telemetry, connection state and event history, with command features enabled only behind server-side evidence gates.
              </p>
              <div className="mt-8 space-y-3">
                {[
                  ['01', 'One Commander identity'],
                  ['02', 'One Base operations picture'],
                  ['03', 'One command history'],
                ].map(([n, text]) => (
                  <div key={n} className="flex items-center gap-3 border-b border-white/[0.055] pb-3">
                    <span className="font-mono text-[9px] text-violet-400">{n}</span>
                    <span className="text-sm font-medium text-slate-200">{text}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="landing-reveal landing-stack relative min-h-[500px]">
              <div className="landing-stack-card landing-stack-card-back absolute inset-x-12 top-8 h-[360px] rounded-[1.6rem] border border-white/[0.06] bg-white/[0.018]" />
              <div className="landing-stack-card landing-stack-card-mid absolute inset-x-6 top-16 h-[360px] rounded-[1.6rem] border border-white/[0.07] bg-[#070b15]/90 shadow-2xl" />
              <div className="landing-stack-card landing-stack-card-front absolute inset-x-0 top-24 rounded-[1.6rem] border border-white/[0.09] bg-[#090e1a]/95 p-5 shadow-[0_35px_100px_rgba(0,0,0,.38)]">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-mono text-[9px] uppercase tracking-[0.15em] text-violet-300">Account command</p>
                    <p className="mt-2 text-xl font-semibold tracking-[-0.04em] text-white">Live detail surface</p>
                  </div>
                  <span className="rounded-lg border border-emerald-300/15 bg-emerald-300/[0.06] px-2.5 py-1 font-mono text-[8px] text-emerald-300">CONNECTED</span>
                </div>
                <div className="mt-6 grid grid-cols-3 gap-2">
                  {['Actions', 'Production', 'Events'].map((label, i) => (
                    <div key={label} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
                      <p className="font-mono text-[7px] uppercase tracking-[0.12em] text-slate-600">{label}</p>
                      <div className={`mt-3 h-2 rounded-full ${i === 1 ? 'bg-amber-300/50' : 'bg-violet-300/25'}`} />
                    </div>
                  ))}
                </div>
                <div className="mt-3 rounded-xl border border-amber-300/10 bg-amber-300/[0.025]">
                  <div className="flex items-center gap-3 px-4 py-3">
                    <Boxes className="h-4 w-4 text-amber-300" />
                    <div className="flex-1">
                      <p className="text-xs font-semibold text-slate-200">Production</p>
                      <p className="mt-0.5 text-[10px] text-slate-500">Grouped queue · expandable</p>
                    </div>
                    <ChevronRight className="h-4 w-4 text-slate-600" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section id="features" className="relative border-y border-white/[0.055] bg-white/[0.012]">
          <div className="landing-feature-orb pointer-events-none absolute left-1/2 top-1/2 h-[680px] w-[680px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-violet-500/[0.05] blur-[120px]" />
          <div className="relative mx-auto max-w-[1420px] px-4 py-28 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-3xl text-center">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">BattleN0de systems</p>
              <h2 className="mt-4 text-4xl font-semibold tracking-[-0.055em] text-white sm:text-5xl">Built around Warpath systems players already know.</h2>
              <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-slate-400">
                No generic CRM language. The interface follows the game: Base, Production Buildings, Convoys, Scout Plane, Alliance scale and Theater of Conquest protection.
              </p>
            </div>

            <div className="mt-14 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {FEATURE_CARDS.map(({ icon: Icon, eyebrow, title, body }, index) => (
                <article key={title} className="landing-feature-card group relative overflow-hidden rounded-[1.4rem] border border-white/[0.065] bg-white/[0.022] p-5 sm:p-6">
                  <div className="landing-feature-sheen absolute inset-0 opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
                  <div className="relative">
                    <div className="flex items-start justify-between">
                      <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-violet-300/15 bg-violet-300/[0.055] text-violet-200">
                        <Icon className="h-[18px] w-[18px]" />
                      </span>
                      <span className="font-mono text-[8px] text-slate-700">0{index + 1}</span>
                    </div>
                    <p className="mt-7 font-mono text-[9px] font-semibold uppercase tracking-[0.16em] text-violet-300">{eyebrow}</p>
                    <h3 className="mt-2 text-lg font-semibold leading-6 tracking-[-0.025em] text-white">{title}</h3>
                    <p className="mt-3 text-xs leading-6 text-slate-500">{body}</p>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section id="security" className="mx-auto max-w-[1420px] px-4 py-24 sm:px-6 lg:px-8">
          <div className="marketing-legal-panel relative overflow-hidden rounded-[2rem] p-6 sm:p-8 lg:p-10">
            <div className="landing-feature-sheen absolute inset-0 opacity-60" />
            <div className="relative grid gap-10 lg:grid-cols-[.78fr_1.22fr] lg:items-center">
              <div>
                <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-300">Built around account boundaries</p>
                <h2 className="mt-4 text-3xl font-semibold leading-[1.02] tracking-[-0.05em] text-white sm:text-4xl">
                  Your credentials are infrastructure, not decoration.
                </h2>
                <p className="mt-5 text-sm leading-7 text-slate-400">
                  Warpath Control keeps sensitive game credentials server-side, isolates regular members to accounts they own, and reports uncertain command state instead of presenting guesses as success.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                {[
                  {
                    icon: LockKeyhole,
                    title: 'Encrypted at rest',
                    body: 'Saved app tokens and device IDs are encrypted before storage and are not returned by normal account APIs.',
                  },
                  {
                    icon: Fingerprint,
                    title: 'Owner isolated',
                    body: 'Member access is scoped to owned accounts. Duplicate canonical game identities are rejected platform-wide.',
                  },
                  {
                    icon: ShieldCheck,
                    title: 'Fail-closed state',
                    body: 'Connection failures and uncertain operations remain visible instead of being silently treated as completed actions.',
                  },
                ].map(({ icon: Icon, title, body }) => (
                  <div key={title} className="rounded-2xl border border-white/[0.065] bg-black/15 p-4">
                    <Icon className="h-4 w-4 text-emerald-300" />
                    <p className="mt-4 text-sm font-semibold text-slate-100">{title}</p>
                    <p className="mt-2 text-xs leading-5 text-slate-500">{body}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section id="plans" className="mx-auto max-w-[1420px] px-4 py-28 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-3xl text-center">
            <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-violet-300">Choose your node</p>
            <h2 className="mt-4 text-4xl font-semibold tracking-[-0.055em] text-white sm:text-5xl">Start with one Base. Scale when you need it.</h2>
            <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-slate-400">
              Most players only need one account. That is the primary product. Alliance exists for operators and power users who manage multiple linked accounts.
            </p>
          </div>

          <div className="mt-14 grid gap-5 lg:grid-cols-[1.15fr_.85fr]">
            <article className="landing-plan-primary group relative overflow-hidden rounded-[1.7rem] border border-violet-300/20 bg-gradient-to-br from-violet-500/[0.13] via-white/[0.025] to-cyan-400/[0.055] p-6 shadow-[0_30px_100px_rgba(91,76,255,.12)] sm:p-8">
              <div className="landing-feature-sheen absolute inset-0 opacity-80" />
              <div className="relative">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <span className="inline-flex items-center gap-2 rounded-full border border-violet-300/20 bg-violet-300/[0.08] px-3 py-1.5 font-mono text-[9px] font-bold uppercase tracking-[0.16em] text-violet-200">
                      <Sparkles className="h-3.5 w-3.5" /> Primary plan
                    </span>
                    <h3 className="mt-5 text-3xl font-semibold tracking-[-0.05em] text-white">Individual</h3>
                    <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.16em] text-cyan-300">1 Warpath account</p>
                  </div>
                  <Gauge className="h-7 w-7 text-violet-200" />
                </div>

                <p className="mt-6 max-w-xl text-sm leading-7 text-slate-300">
                  A dedicated personal dashboard for one linked account with secure connection controls, production telemetry, account intelligence and activity history.
                </p>

                <div className="mt-7 grid gap-2 sm:grid-cols-2">
                  {[
                    'Dedicated Base command node',
                    'Treasury / Steelworks / Oil Reserve view',
                    'Collection Convoys and live Base state',
                    'Scout Plane telemetry and evidence-gated controls',
                    'Conquest Guard protection module',
                    'Commander activity and diagnostics',
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-black/10 px-3 py-2.5 text-xs text-slate-300">
                      <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
                      {item}
                    </div>
                  ))}
                </div>

                <div className="mt-8 flex flex-wrap items-center gap-3">
                  <Link href="/activate" className="landing-primary-button inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-semibold text-[#050812] transition hover:-translate-y-0.5">
                    Activate Individual <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link href="/activate" className="inline-flex h-12 items-center justify-center gap-2 rounded-xl border border-white/[0.09] bg-white/[0.035] px-5 text-sm font-semibold text-slate-200 transition hover:bg-white/[0.06]">
                    Activate access <LockKeyhole className="h-4 w-4 text-slate-500" />
                  </Link>
                </div>
              </div>
            </article>

            <article className="landing-feature-card group relative overflow-hidden rounded-[1.7rem] border border-cyan-300/10 bg-white/[0.018] p-6 sm:p-8">
              <div className="relative">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="font-mono text-[9px] font-bold uppercase tracking-[0.16em] text-cyan-300">Alliance node</span>
                    <h3 className="mt-3 text-2xl font-semibold tracking-[-0.045em] text-white">Alliance</h3>
                    <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">Multi-account command</p>
                  </div>
                  <Users className="h-6 w-6 text-cyan-300" />
                </div>

                <p className="mt-6 text-sm leading-7 text-slate-400">
                  The fleet-wide dashboard for players, account managers, and power users managing multiple linked accounts.
                </p>

                <div className="mt-6 space-y-2 text-xs text-slate-400">
                  {[
                    'Aggregate Base health',
                    'Cross-account field operations',
                    'Cross-account event feed',
                    'Linked Commander roster',
                    'Alliance command node',
                  ].map((item) => (
                    <div key={item} className="flex items-center gap-2 border-b border-white/[0.055] pb-2.5">
                      <ChevronRight className="h-3.5 w-3.5 text-cyan-400" />
                      {item}
                    </div>
                  ))}
                </div>

                <Link href="/alliance" className="mt-8 inline-flex items-center gap-2 text-sm font-semibold text-cyan-300 transition hover:text-white">
                  Open Alliance dashboard <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </article>
          </div>
        </section>

        <section id="workflow" className="mx-auto max-w-[1420px] px-4 py-28 sm:px-6 lg:px-8">
          <div className="grid gap-14 lg:grid-cols-[.82fr_1.18fr] lg:items-start">
            <div className="lg:sticky lg:top-28">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-emerald-300">Commander flow</p>
              <h2 className="mt-4 text-4xl font-semibold leading-[1.02] tracking-[-0.055em] text-white sm:text-5xl">
                Link your Commander. Bring the Base online.
              </h2>
              <p className="mt-5 max-w-lg text-sm leading-7 text-slate-400">
                BattleN0de keeps one Base focused. If you begin managing several Warpath accounts, the Alliance node gives you the wider operational picture without bloating the Individual node.
              </p>
              <Link href="/activate" className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-violet-300 transition hover:text-cyan-300">
                Activate your BattleN0de <ArrowRight className="h-4 w-4" />
              </Link>
            </div>

            <div className="space-y-3">
              {FLOW.map(({ number, title, body, icon: Icon }) => (
                <div key={number} className="landing-flow-card group relative overflow-hidden rounded-2xl border border-white/[0.065] bg-white/[0.018] p-5 sm:p-6">
                  <div className="absolute inset-y-0 left-0 w-px bg-gradient-to-b from-violet-400 via-cyan-300 to-transparent opacity-50" />
                  <div className="flex gap-5">
                    <div className="font-mono text-[10px] text-violet-300">{number}</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between gap-4">
                        <h3 className="text-lg font-semibold tracking-[-0.03em] text-white">{title}</h3>
                        <Icon className="h-4 w-4 text-slate-700 transition group-hover:text-violet-300" />
                      </div>
                      <p className="mt-2 text-xs leading-6 text-slate-500">{body}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <MarketingFaq />

        <section className="mx-auto max-w-[1420px] px-4 pb-28 sm:px-6 lg:px-8">
          <div className="landing-final relative overflow-hidden rounded-[2rem] border border-white/[0.075] bg-gradient-to-br from-violet-500/[0.09] via-white/[0.02] to-cyan-400/[0.055] px-6 py-16 text-center shadow-[0_35px_120px_rgba(0,0,0,.3)] sm:px-10 sm:py-20">
            <div className="landing-final-ring pointer-events-none absolute left-1/2 top-1/2 h-[620px] w-[620px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-violet-300/[0.08]" />
            <div className="relative z-10 mx-auto max-w-3xl">
              <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-violet-300">BATTLE/N0DE</p>
              <h2 className="mt-4 text-4xl font-semibold leading-[1] tracking-[-0.06em] text-white sm:text-6xl">
                Your Base deserves a real command node.
              </h2>
              <p className="mx-auto mt-5 max-w-xl text-sm leading-7 text-slate-400">
                Start with one linked Commander. Move to the Alliance node when your Warpath operation grows beyond a single Base.
              </p>
              <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                <Link href="/activate" className="landing-primary-button inline-flex h-12 items-center justify-center gap-2 rounded-xl bg-white px-5 text-sm font-semibold text-[#050812] transition hover:-translate-y-0.5">
                  Activate Individual <ArrowRight className="h-4 w-4" />
                </Link>
                <Link href="/login" className="inline-flex h-12 items-center justify-center rounded-xl border border-white/[0.09] bg-black/10 px-5 text-sm font-semibold text-slate-200 transition hover:bg-white/[0.04]">
                  Sign in
                </Link>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="relative z-10 border-t border-white/[0.055]">
        <div className="mx-auto max-w-[1420px] px-4 py-8 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <BrandMark compact />
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-slate-600">
              <Link href="/login" className="transition hover:text-slate-300">Sign in</Link>
              <Link href="/activate" className="transition hover:text-slate-300">Activate access</Link>
              <Link href="/terms" className="transition hover:text-slate-300">Terms</Link>
              <Link href="/privacy" className="transition hover:text-slate-300">Privacy</Link>
              <Link href="/refunds" className="transition hover:text-slate-300">Refunds</Link>
            </div>
          </div>
          <p className="mt-6 max-w-3xl text-[10px] leading-5 text-slate-700">
            BattleN0de is an independent third-party service for Warpath: Ace Shooter players and is not affiliated with, endorsed by, sponsored by, or operated by Lilith Games or the publishers of Warpath.
          </p>
        </div>
      </footer>
    </MarketingMotionRoot>
  );
}
