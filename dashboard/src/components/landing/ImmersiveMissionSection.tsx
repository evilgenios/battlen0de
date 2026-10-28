import {
  Boxes,
  Crosshair,
  Plane,
  RadioTower,
  ShieldAlert,
  ShieldCheck,
  TimerReset,
  Truck,
  Wifi,
} from 'lucide-react';

const STAGES = [
  {
    id: 'observe',
    label: 'Observe',
    eyebrow: '01 · BASE ONLINE',
    title: 'Bring your Base onto one command node.',
    body: 'Connection state, Commander identity, active movements and account health surface in one place while your Warpath session runs in the cloud.',
  },
  {
    id: 'operate',
    label: 'Operate',
    eyebrow: '02 · FIELD OPS',
    title: 'Production, Convoys and scouting become one picture.',
    body: 'Track your Production Buildings, Collection Convoys and Scout Plane activity without bouncing between screens just to understand what your Base is doing.',
  },
  {
    id: 'protect',
    label: 'Protect',
    eyebrow: '03 · THEATER OF CONQUEST',
    title: 'Conquest Guard watches the Base.',
    body: 'When enabled, the account-scoped guard watches for a main-Base attack and can leave Theater of Conquest automatically while the account is connected.',
  },
] as const;

function StageNav({ active }: { active: string }) {
  return (
    <nav aria-label="BattleN0de experience stages" className="flex flex-wrap gap-2">
      {STAGES.map((item) => (
        <a
          key={item.id}
          href={`#experience-${item.id}`}
          aria-current={active === item.id ? 'step' : undefined}
          className={`group flex items-center gap-2 rounded-full border px-3 py-2 font-mono text-[8px] uppercase tracking-[0.13em] transition-all ${
            active === item.id
              ? 'border-cyan-300/25 bg-cyan-300/[0.07] text-cyan-200'
              : 'border-white/[0.07] bg-black/10 text-slate-600 hover:border-white/[0.13] hover:text-slate-300'
          }`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${active === item.id ? 'bg-cyan-300 shadow-[0_0_10px_currentColor]' : 'bg-slate-700'}`} />
          {item.label}
        </a>
      ))}
    </nav>
  );
}

function ObservePanel() {
  return (
    <div className="immersive-hud-card immersive-card-primary">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-cyan-300">Base telemetry</span>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300/15 bg-emerald-300/[0.055] px-2.5 py-1 font-mono text-[8px] text-emerald-300">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_12px_currentColor]" />
          LINK LIVE
        </span>
      </div>
      <div className="mt-5 flex items-center gap-4">
        <span className="flex h-12 w-12 items-center justify-center rounded-xl border border-cyan-300/15 bg-cyan-300/[0.055] text-cyan-200">
          <Wifi className="h-5 w-5" />
        </span>
        <div>
          <p className="text-sm font-semibold text-white">Commander Node</p>
          <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.12em] text-slate-500">UID 5097091 · Base authenticated</p>
        </div>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2">
        {[
          ['Base link', 'Stable'],
          ['Convoys', '02'],
          ['Scout Plane', 'Ready'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-white/[0.07] bg-black/10 p-3">
            <p className="font-mono text-[7px] uppercase tracking-[0.1em] text-slate-600">{label}</p>
            <p className="mt-2 text-xs font-semibold text-slate-200">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function OperatePanel() {
  return (
    <div className="immersive-hud-card immersive-card-primary">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-amber-300">Production Buildings</span>
        <Boxes className="h-4 w-4 text-amber-300" />
      </div>
      <div className="mt-4 space-y-2">
        {[
          ['Treasury', 'Military Funds', 82, '03:14'],
          ['Steelworks', 'Steel', 100, 'READY'],
          ['Oil Reserve', 'Crude Oil', 41, '08:52'],
        ].map(([building, item, progress, eta]) => (
          <div key={String(building)} className="rounded-xl border border-white/[0.065] bg-black/10 p-3">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-[9px] font-semibold text-slate-300">{building}</p>
                <p className="mt-0.5 text-[8px] text-slate-600">{item}</p>
              </div>
              <span className="font-mono text-[8px] text-amber-200">{eta}</span>
            </div>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/5">
              <div
                className="h-full rounded-full bg-gradient-to-r from-amber-400/70 via-violet-400/60 to-cyan-300/70"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="flex items-center gap-2 rounded-xl border border-violet-300/10 bg-violet-300/[0.035] px-3 py-2.5">
          <Truck className="h-3.5 w-3.5 text-violet-300" />
          <span className="text-[8px] text-slate-500">2 Collection Convoys active</span>
        </div>
        <div className="flex items-center gap-2 rounded-xl border border-cyan-300/10 bg-cyan-300/[0.035] px-3 py-2.5">
          <Plane className="h-3.5 w-3.5 text-cyan-300" />
          <span className="text-[8px] text-slate-500">Scout Plane ready</span>
        </div>
      </div>
    </div>
  );
}

function ProtectPanel() {
  return (
    <div className="immersive-hud-card immersive-guard-card">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[9px] uppercase tracking-[0.18em] text-cyan-300">Theater of Conquest protocol</span>
        <span className="immersive-guard-pulse inline-flex items-center gap-1.5 rounded-full border border-emerald-300/20 bg-emerald-300/[0.07] px-2.5 py-1 font-mono text-[8px] text-emerald-300">
          <ShieldCheck className="h-3 w-3" />
          ARMED
        </span>
      </div>
      <div className="mt-6 flex items-center gap-5">
        <div className="immersive-shield-core relative flex h-20 w-20 shrink-0 items-center justify-center rounded-full border border-cyan-300/20 bg-cyan-300/[0.045]">
          <ShieldAlert className="h-8 w-8 text-cyan-200" />
          <span className="absolute inset-[-8px] rounded-full border border-cyan-300/10" />
          <span className="absolute inset-[-18px] rounded-full border border-violet-300/[0.07]" />
        </div>
        <div>
          <p className="text-lg font-semibold tracking-[-0.03em] text-white">Conquest Guard</p>
          <p className="mt-2 max-w-sm text-xs leading-5 text-slate-500">
            Account-specific protection watching your main Base while the Warpath session remains connected.
          </p>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-2">
        {[
          ['Base attack', 'None'],
          ['Exit pending', 'No'],
          ['Attempts', '0'],
          ['Guard state', 'Standby'],
        ].map(([label, value]) => (
          <div key={label} className="rounded-xl border border-white/[0.065] bg-black/10 p-3">
            <p className="font-mono text-[7px] uppercase tracking-[0.1em] text-slate-600">{label}</p>
            <p className="mt-1.5 text-[10px] font-semibold text-slate-300">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

const PANELS = {
  observe: ObservePanel,
  operate: OperatePanel,
  protect: ProtectPanel,
} as const;

export function ImmersiveMissionSection() {
  return (
    <section id="experience" className="immersive-section relative z-10 border-y border-white/[0.055]">
      <div className="sticky top-[72px] z-20 border-b border-white/[0.055] bg-[#03050b]/72 px-4 py-3 backdrop-blur-xl sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-[1420px] items-center justify-between gap-4">
          <p className="hidden font-mono text-[9px] font-bold uppercase tracking-[0.22em] text-violet-300 sm:block">
            BattleN0de field interface
          </p>
          <StageNav active="" />
        </div>
      </div>

      {STAGES.map((stage) => {
        const Panel = PANELS[stage.id];
        return (
          <article
            key={stage.id}
            id={`experience-${stage.id}`}
            className="relative flex min-h-[92vh] scroll-mt-[132px] items-center overflow-hidden px-4 py-20 sm:px-6 lg:px-8"
          >
            <div className="immersive-room-glow pointer-events-none absolute inset-0" />
            <div className="immersive-crosshair pointer-events-none absolute left-[72%] top-1/2 h-[38rem] w-[38rem] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-300/[0.045]" />
            <div className="immersive-sweep pointer-events-none absolute inset-y-0 left-0 w-[34%]" />

            <div className="relative mx-auto grid w-full max-w-[1420px] gap-10 lg:grid-cols-[.78fr_1.22fr] lg:items-center">
              <div>
                <p className="font-mono text-[9px] font-bold uppercase tracking-[0.22em] text-violet-300">BattleN0de field interface</p>
                <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.18em] text-cyan-300">{stage.eyebrow}</p>
                <h2 className="mt-4 max-w-xl text-4xl font-semibold leading-[1.02] tracking-[-0.06em] text-white sm:text-6xl">
                  {stage.title}
                </h2>
                <p className="mt-5 max-w-lg text-sm leading-7 text-slate-400">{stage.body}</p>
                <div className="mt-9">
                  <StageNav active={stage.id} />
                </div>
              </div>

              <div className="relative min-h-[480px]">
                <div className="absolute inset-x-0 top-1/2 -translate-y-1/2">
                  <Panel />
                </div>

                <div className="immersive-side-node absolute -right-2 top-12 hidden rounded-xl border border-white/[0.07] bg-[#070b15]/75 p-3 backdrop-blur-xl sm:block">
                  <Crosshair className="h-4 w-4 text-violet-300" />
                  <p className="mt-2 font-mono text-[7px] uppercase tracking-[0.14em] text-slate-600">Field state</p>
                  <p className="mt-1 text-[9px] font-semibold text-slate-300">Synced</p>
                </div>

                <div className="immersive-side-node absolute -left-5 bottom-16 hidden rounded-xl border border-white/[0.07] bg-[#070b15]/75 p-3 backdrop-blur-xl md:block">
                  <RadioTower className="h-4 w-4 text-cyan-300" />
                  <p className="mt-2 font-mono text-[7px] uppercase tracking-[0.14em] text-slate-600">Cloud session</p>
                  <p className="mt-1 text-[9px] font-semibold text-emerald-300">ONLINE</p>
                </div>

                <div className="immersive-side-node absolute right-10 bottom-4 hidden rounded-xl border border-white/[0.07] bg-[#070b15]/75 p-3 backdrop-blur-xl lg:block">
                  <TimerReset className="h-4 w-4 text-amber-300" />
                  <p className="mt-2 font-mono text-[7px] uppercase tracking-[0.14em] text-slate-600">Next production</p>
                  <p className="mt-1 font-mono text-[9px] font-semibold text-slate-300">03:14</p>
                </div>
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}
