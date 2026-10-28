'use client';

import { useState } from 'react';
import {
  Boxes,
  Command,
  Fingerprint,
  Gauge,
  PackageCheck,
  Radar,
  ShieldCheck,
} from 'lucide-react';

export function InteractiveDashboardDemo() {
  const [view, setView] = useState<'overview' | 'production' | 'actions' | 'account'>('overview');

  const nav = [
    { id: 'overview' as const, icon: Gauge, label: 'Overview' },
    { id: 'production' as const, icon: PackageCheck, label: 'Production' },
    { id: 'actions' as const, icon: Radar, label: 'Actions' },
    { id: 'account' as const, icon: Fingerprint, label: 'Account' },
  ];

  return (
    <div className="landing-console relative mx-auto w-full max-w-[720px]">
      <div className="landing-console-glow absolute inset-10 rounded-[2rem] bg-violet-500/20 blur-[70px]" />
      <div className="landing-float-card landing-float-card-a absolute -left-8 top-20 z-20 hidden w-44 rounded-2xl border border-white/10 bg-[#0b1020]/90 p-3 shadow-2xl backdrop-blur-xl sm:block">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_14px_#34d399]" />
          <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-slate-400">Account live</span>
        </div>
        <p className="mt-2 text-sm font-semibold text-white">Operational</p>
        <p className="mt-1 text-[10px] text-slate-500">BattleN0de session active</p>
      </div>

      <div className="landing-float-card landing-float-card-b absolute -right-6 bottom-24 z-20 hidden w-48 rounded-2xl border border-white/10 bg-[#0b1020]/90 p-3 shadow-2xl backdrop-blur-xl sm:block">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-slate-400">Production</span>
          <PackageCheck className="h-3.5 w-3.5 text-amber-300" />
        </div>
        <p className="mt-2 text-sm font-semibold text-white">3 Production Buildings</p>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/5">
          <div className="landing-progress h-full w-3/4 rounded-full bg-gradient-to-r from-violet-400 via-cyan-300 to-emerald-300" />
        </div>
      </div>

      <div className="relative overflow-hidden rounded-[1.6rem] border border-white/10 bg-[#070b15]/94 shadow-[0_45px_140px_rgba(0,0,0,.58)] backdrop-blur-2xl">
        <div className="flex h-12 items-center justify-between border-b border-white/[0.07] px-4 sm:px-5">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-300/70" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300/70" />
          </div>
          <span className="font-mono text-[8px] uppercase tracking-[0.22em] text-slate-600">interactive product preview</span>
          <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_12px_#6ee7b7]" />
        </div>

        <div className="grid min-h-[410px] grid-cols-[72px_1fr] sm:grid-cols-[150px_1fr]">
          <aside className="border-r border-white/[0.06] bg-white/[0.015] p-2.5 sm:p-3">
            <div className="mb-5 flex h-9 items-center justify-center rounded-xl border border-violet-400/20 bg-violet-400/8 sm:justify-start sm:px-3">
              <Command className="h-4 w-4 text-violet-300" />
              <span className="ml-2 hidden text-[10px] font-semibold text-slate-200 sm:block">BattleN0de</span>
            </div>
            {nav.map(({ id, icon: Icon, label }) => {
              const active = id === view;
              return (
                <button
                  type="button"
                  key={id}
                  onClick={() => setView(id)}
                  aria-pressed={active}
                  className={`mb-1.5 flex h-9 w-full items-center justify-center rounded-lg border transition-all duration-300 sm:justify-start sm:px-2.5 ${
                    active
                      ? 'border-violet-400/20 bg-violet-400/10 text-violet-200 shadow-[0_8px_30px_rgba(124,108,255,.08)]'
                      : 'border-transparent text-slate-600 hover:border-white/[0.06] hover:bg-white/[0.025] hover:text-slate-300'
                  }`}
                >
                  <Icon className="h-3.5 w-3.5" />
                  <span className="ml-2 hidden text-[9px] font-medium sm:block">{label}</span>
                </button>
              );
            })}
          </aside>

          <div className="relative overflow-hidden p-4 sm:p-5">
            <div className="landing-console-scan absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-transparent via-cyan-300/[0.035] to-transparent" />
            <div className="relative z-10">
              <div className="flex items-start justify-between">
                <div>
                  <p className="font-mono text-[8px] uppercase tracking-[0.22em] text-violet-300">Individual Node · demo Commander</p>
                  <h3 className="mt-2 text-base font-semibold tracking-[-0.04em] text-white sm:text-xl">
                    {view === 'overview' && 'Base overview'}
                    {view === 'production' && 'Production Buildings'}
                    {view === 'actions' && 'Field operations'}
                    {view === 'account' && 'Commander identity'}
                  </h3>
                </div>
                <span className="rounded-lg border border-white/[0.08] bg-white/[0.025] px-2.5 py-1 font-mono text-[8px] text-emerald-300">ONLINE</span>
              </div>

              <div key={view} className="motion-safe:animate-[landing-rise_.32s_ease-out]">
                {view === 'overview' && (
                  <>
                    <div className="mt-5 grid grid-cols-2 gap-2.5 lg:grid-cols-4">
                      {[
                        ['Base', '01'],
                        ['Node link', 'LIVE'],
                        ['Actions', '06'],
                        ['Production', '03'],
                      ].map(([label, value], index) => (
                        <div key={label} className="rounded-xl border border-white/[0.07] bg-white/[0.025] p-3">
                          <p className="font-mono text-[7px] uppercase tracking-[0.12em] text-slate-600">{label}</p>
                          <p className={`mt-2 text-lg font-semibold ${index === 1 ? 'text-emerald-300' : 'text-slate-100'}`}>{value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-3 lg:grid-cols-[1.05fr_.95fr]">
                      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3.5">
                        <div className="flex items-center justify-between">
                          <p className="text-[9px] font-semibold text-slate-300">Your Base</p>
                          <span className="font-mono text-[7px] text-emerald-300">CONNECTED</span>
                        </div>
                        <div className="mt-4 space-y-2">
                          {['Production Buildings active', 'Collection Convoy returning', 'Conquest Guard armed'].map((label, i) => (
                            <div key={label} className="flex items-center gap-2 rounded-lg border border-white/[0.055] bg-black/10 px-2.5 py-2">
                              <span className={`h-1.5 w-1.5 rounded-full ${i === 2 ? 'bg-cyan-300' : 'bg-emerald-300'}`} />
                              <span className="text-[8px] text-slate-500">{label}</span>
                              <span className="ml-auto font-mono text-[7px] text-slate-700">{i === 0 ? '24' : i === 1 ? '02:18' : 'ON'}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-3.5">
                        <p className="text-[9px] font-semibold text-slate-300">Activity signal</p>
                        <div className="mt-4 flex h-24 items-end gap-1.5">
                          {[24, 45, 34, 70, 54, 82, 46, 72, 92, 68, 88].map((height, i) => (
                            <span
                              key={i}
                              className="landing-bar flex-1 rounded-t-sm bg-gradient-to-t from-violet-500/30 to-cyan-300/70"
                              style={{ height: `${height}%`, animationDelay: `${i * 90}ms` }}
                            />
                          ))}
                        </div>
                      </div>
                    </div>
                  </>
                )}

                {view === 'production' && (
                  <div className="mt-5 space-y-2.5">
                    {[
                      ['Treasury', 'Military Funds', '82%', '03:14', '82'],
                      ['Steelworks', 'Steel', 'READY', 'Ready', '100'],
                      ['Oil Reserve', 'Crude Oil', '41%', '08:52', '41'],
                      ['Treasury II', 'Military Funds', '67%', '05:06', '67'],
                    ].map(([building, item, state, eta, progress]) => (
                      <div key={building} className="rounded-xl border border-white/[0.065] bg-white/[0.02] p-3">
                        <div className="flex items-center gap-3">
                          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-amber-300/10 bg-amber-300/[0.04]">
                            <Boxes className="h-3.5 w-3.5 text-amber-300" />
                          </span>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-[9px] font-semibold text-slate-300">{building}</p>
                                <p className="mt-0.5 text-[8px] text-slate-600">{item}</p>
                              </div>
                              <div className="text-right">
                                <p className={`font-mono text-[8px] font-semibold ${state === 'READY' ? 'text-emerald-300' : 'text-amber-200'}`}>{state}</p>
                                <p className="mt-0.5 font-mono text-[7px] text-slate-600">{eta}</p>
                              </div>
                            </div>
                            <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/5">
                              <div className="landing-progress h-full rounded-full bg-gradient-to-r from-amber-400/60 to-cyan-300/70" style={{ width: `${progress}%` }} />
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {view === 'actions' && (
                  <div className="mt-5 space-y-2.5">
                    {[
                      ['Collection Convoy #1', 'Gathering', 'Oil Reserve', '12:42', 'emerald'],
                      ['Collection Convoy #2', 'Returning', 'Base', '02:18', 'cyan'],
                      ['Scout Plane', 'Recon', 'World Map', '00:47', 'violet'],
                      ['Conquest Guard', 'Armed', 'Main Base', 'Standby', 'amber'],
                    ].map(([name, action, target, eta, tone], i) => (
                      <div key={name} className="group rounded-xl border border-white/[0.065] bg-white/[0.02] p-3 transition hover:border-violet-300/15 hover:bg-white/[0.03]">
                        <div className="flex items-center gap-3">
                          <span className={`h-2 w-2 rounded-full ${tone === 'emerald' ? 'bg-emerald-300' : tone === 'cyan' ? 'bg-cyan-300' : tone === 'violet' ? 'bg-violet-300' : 'bg-amber-300'} shadow-[0_0_12px_currentColor]`} />
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center justify-between">
                              <p className="text-[9px] font-semibold text-slate-300">{name}</p>
                              <span className="font-mono text-[8px] text-slate-500">{eta}</span>
                            </div>
                            <p className="mt-1 text-[8px] text-slate-600">{action} · {target}</p>
                            <div className="mt-2 h-px overflow-hidden bg-white/5">
                              <div className="landing-progress h-full bg-gradient-to-r from-violet-400/50 to-cyan-300/60" style={{ width: `${45 + i * 12}%` }} />
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {view === 'account' && (
                  <div className="mt-5">
                    <div className="rounded-xl border border-white/[0.07] bg-white/[0.02] p-4">
                      <div className="flex items-center gap-3">
                        <span className="flex h-11 w-11 items-center justify-center rounded-xl border border-violet-300/15 bg-violet-300/[0.055]">
                          <Fingerprint className="h-5 w-5 text-violet-200" />
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-slate-200">Demo Commander</p>
                          <p className="mt-1 font-mono text-[8px] uppercase tracking-[0.12em] text-slate-600">UID 5097091 · BattleN0de linked</p>
                        </div>
                      </div>

                      <div className="mt-5 grid gap-2 sm:grid-cols-2">
                        {[
                          ['Commander identity', 'Linked'],
                          ['Node credentials', 'Encrypted'],
                          ['Base access', 'Owner isolated'],
                          ['Cloud link', 'Authenticated'],
                        ].map(([label, value]) => (
                          <div key={label} className="rounded-lg border border-white/[0.055] bg-black/10 p-3">
                            <p className="font-mono text-[7px] uppercase tracking-[0.1em] text-slate-700">{label}</p>
                            <p className="mt-1.5 text-[9px] font-semibold text-slate-300">{value}</p>
                          </div>
                        ))}
                      </div>

                      <div className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-300/10 bg-emerald-300/[0.025] px-3 py-2.5">
                        <ShieldCheck className="h-3.5 w-3.5 text-emerald-300" />
                        <p className="text-[8px] text-slate-500">Stored game credentials are not exposed back through normal dashboard APIs.</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <p className="mt-3 text-center font-mono text-[8px] uppercase tracking-[0.16em] text-slate-700">
        Interactive preview · sample data
      </p>
    </div>
  );
}

