'use client';

import { useState } from 'react';
import { ChevronDown, Cloud, Fingerprint, LockKeyhole, ShieldCheck, Smartphone, Users } from 'lucide-react';

const FAQS = [
  {
    icon: Cloud,
    question: 'Do I need to leave my computer or browser running?',
    answer:
      'No. Once a linked account is connected, the live session runs on the hosted BattleN0de backend rather than inside your browser. You can close the page and come back later from another device. Maintenance, server restarts, expired game credentials, or a failed connection can still require you to reconnect.',
  },
  {
    icon: Smartphone,
    question: 'Can I check my account from my phone?',
    answer:
      'Yes. BattleN0de is a responsive web dashboard, so you can sign in from a supported browser on your phone, tablet, or computer and view the state available to your account.',
  },
  {
    icon: ShieldCheck,
    question: 'Can another user see my linked account or settings?',
    answer:
      'Normal members are isolated to accounts they own. Other regular users cannot browse your linked accounts through the dashboard. Authorized service administrators retain operator access where needed for support, security, and platform operations.',
  },
  {
    icon: Fingerprint,
    question: 'Can the same Warpath account be linked to two profiles?',
    answer:
      'No. A valid game identity is treated as one canonical account across BattleN0de. If that identity is already linked, another link attempt is rejected instead of creating a duplicate. If your credentials change, use the relink flow for the existing account.',
  },
  {
    icon: LockKeyhole,
    question: 'Are my game credentials shown back in the dashboard?',
    answer:
      'No. Sensitive account credentials are encrypted before storage and the normal account APIs do not return the saved app token or device ID back to the browser. Relinking replaces credentials without exposing the stored values.',
  },
  {
    icon: Users,
    question: 'What is the difference between an Individual Node and Alliance Node?',
    answer:
      'Individual is one BattleN0de for one linked Warpath Commander. Alliance is the multi-account node for players who need a wider view across several linked Bases. Collaborative alliance-member roles and shared team workspaces are separate capabilities from multi-account access and are not implied by the current plan.',
  },
  {
    icon: Cloud,
    question: 'What happens if my game session disconnects or needs re-authentication?',
    answer:
      'The dashboard reports the connection state instead of pretending the account is still live. If the game credentials are no longer accepted, the account can be marked for re-authentication and game actions remain unavailable until the credentials are refreshed.',
  },
  {
    icon: ShieldCheck,
    question: 'Can the website silently enable automatic game-changing actions?',
    answer:
      'No. The current platform is designed to fail closed. Observation and command state are surfaced explicitly, while game-changing automation is not silently enabled just because an account is connected.',
  },
  {
    icon: LockKeyhole,
    question: 'Is registration open to everyone?',
    answer:
      'Access is currently controlled through operator-issued activation or recovery tokens rather than open public self-service registration. If public checkout or self-service signup is introduced later, the site will state the applicable plan, price, and access terms before purchase.',
  },
  {
    icon: Users,
    question: 'Can I scale an Individual Node into Alliance later?',
    answer:
      'Yes. The account limits behind your access can be raised by an authorized BattleN0de operator, so moving to Alliance does not require creating a new game identity or abandoning the account you already linked. Any price or duration for a paid upgrade must be confirmed through the official sales channel before the change.',
  },
  {
    icon: Cloud,
    question: 'How do access periods, expiry, and renewal work?',
    answer:
      'The current site does not pretend that every account has an automatic recurring subscription. If your access is sold or issued for a fixed period, the duration and renewal terms should be stated through the official purchase or activation channel. When time-based billing is introduced directly in the product, the dashboard will show it explicitly rather than infer it.',
  },
  {
    icon: ShieldCheck,
    question: 'Is BattleN0de affiliated with Lilith Games?',
    answer:
      'No. BattleN0de is an independent third-party tool. It is not affiliated with, sponsored by, endorsed by, or operated by Lilith Games or the publishers of Warpath. Your use of Warpath remains subject to the game publisher’s own terms and rules.',
  },
] as const;

export function MarketingFaq() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section id="faq" className="mx-auto max-w-[1160px] px-4 py-28 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-3xl text-center">
        <p className="font-mono text-[10px] font-bold uppercase tracking-[0.2em] text-cyan-300">Questions before you connect</p>
        <h2 className="mt-4 text-4xl font-semibold tracking-[-0.055em] text-white sm:text-5xl">
          Commander briefings before you link.
        </h2>
        <p className="mx-auto mt-5 max-w-2xl text-sm leading-7 text-slate-400">
          Straight answers about cloud sessions, Base access, Commander identity, Conquest Guard, plan limits and what BattleN0de actually does.
        </p>
      </div>

      <div className="mt-14 space-y-3">
        {FAQS.map(({ icon: Icon, question, answer }, index) => {
          const expanded = open === index;
          return (
            <article
              key={question}
              className="marketing-faq-item overflow-hidden rounded-2xl border border-white/[0.065] bg-white/[0.018]"
            >
              <button
                type="button"
                aria-expanded={expanded}
                onClick={() => setOpen(expanded ? null : index)}
                className="flex w-full items-center gap-4 px-4 py-4 text-left sm:px-5 sm:py-5"
              >
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-violet-300/15 bg-violet-300/[0.055] text-violet-200">
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="font-mono text-[8px] font-semibold uppercase tracking-[0.18em] text-slate-600">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="mt-1 block text-sm font-semibold tracking-[-0.015em] text-slate-100 sm:text-[15px]">
                    {question}
                  </span>
                </span>
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/[0.075] bg-white/[0.025]">
                  <ChevronDown className={`h-4 w-4 text-slate-500 transition-transform duration-300 ${expanded ? 'rotate-180 text-cyan-300' : ''}`} />
                </span>
              </button>

              <div className={`grid transition-[grid-template-rows,opacity] duration-400 ease-out ${expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}>
                <div className="min-h-0 overflow-hidden">
                  <div className="border-t border-white/[0.055] px-4 pb-5 pt-4 sm:px-[5.25rem] sm:pb-6">
                    <p className="text-sm leading-7 text-slate-400">{answer}</p>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
