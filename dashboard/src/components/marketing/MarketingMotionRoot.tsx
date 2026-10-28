'use client';

import { useEffect, useRef } from 'react';
import { MarketingBackdrop } from '@/components/marketing/MarketingBackdrop';

export function MarketingMotionRoot({ children }: { children: React.ReactNode }) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return;

    let frame = 0;
    let nextX = 0;
    let nextY = 0;

    const flush = () => {
      frame = 0;
      root.style.setProperty('--landing-x', nextX.toFixed(3));
      root.style.setProperty('--landing-y', nextY.toFixed(3));
    };

    const move = (event: PointerEvent) => {
      const rect = root.getBoundingClientRect();
      nextX = ((event.clientX - rect.left) / rect.width - 0.5) * 2;
      nextY = ((event.clientY - rect.top) / rect.height - 0.5) * 2;
      if (!frame) frame = window.requestAnimationFrame(flush);
    };

    root.addEventListener('pointermove', move, { passive: true });
    return () => {
      root.removeEventListener('pointermove', move);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div ref={rootRef} className="landing-root min-h-screen overflow-hidden bg-[#03050b] text-white">
      <MarketingBackdrop />
      <div className="landing-cursor-glow pointer-events-none fixed inset-0 z-0" />
      <div className="landing-grid pointer-events-none fixed inset-0 z-0 opacity-60" />
      <div className="landing-orbit landing-orbit-a pointer-events-none fixed z-0" />
      <div className="landing-orbit landing-orbit-b pointer-events-none fixed z-0" />
      {children}
    </div>
  );
}
