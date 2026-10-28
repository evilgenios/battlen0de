'use client';

import '@/app/marketing.css';

export function MarketingBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 z-0 overflow-hidden bg-[#03050b]">
      <video
        className="landing-video absolute inset-0 h-full w-full object-cover"
        autoPlay
        muted
        loop
        playsInline
        preload="auto"
      >
        <source src="/media/cyber-room-loop.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-[linear-gradient(180deg,rgba(3,5,11,.22),rgba(3,5,11,.38)_48%,rgba(3,5,11,.66))]" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,transparent_0%,rgba(3,5,11,.05)_38%,rgba(3,5,11,.50)_100%)]" />
      <div className="landing-video-scan absolute inset-0 opacity-30" />
    </div>
  );
}
