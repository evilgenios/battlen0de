function seededRandom(seed: number): number {
  const value = Math.sin(seed * 12.9898) * 43758.5453;
  return value - Math.floor(value);
}

const STAR_COUNT = 78;
const STARS = Array.from({ length: STAR_COUNT }, (_, i) => ({
  left: seededRandom(i * 3 + 1) * 100,
  top: seededRandom(i * 3 + 2) * 100,
  size: seededRandom(i * 3 + 3) > 0.86 ? 2 : 1,
  delay: seededRandom(i * 7 + 5) * 7,
  duration: 3.4 + seededRandom(i * 11 + 9) * 4.5,
}));

const PARTICLE_COUNT = 7;
const PARTICLES = Array.from({ length: PARTICLE_COUNT }, (_, i) => ({
  left: seededRandom(i * 17 + 31) * 100,
  duration: 44 + seededRandom(i * 23 + 41) * 44,
  delay: seededRandom(i * 29 + 53) * 22,
}));

export function WarpathBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 hidden overflow-hidden dark:block">
      <div className="absolute inset-0 bg-[#050812]" />

      <div className="absolute -left-[18vw] -top-[24vw] h-[58vw] w-[58vw] rounded-full bg-accent/10 blur-[120px] motion-safe:animate-[warpath-aurora_18s_ease-in-out_infinite]" />
      <div className="absolute -bottom-[18vw] -right-[12vw] h-[48vw] w-[48vw] rounded-full bg-info/8 blur-[130px] motion-safe:animate-[warpath-aurora_22s_ease-in-out_infinite_reverse]" />

      <div
        className="absolute inset-[-56px] opacity-[0.055] motion-safe:animate-[warpath-grid-drift_28s_linear_infinite]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(148,163,184,0.8) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.8) 1px, transparent 1px)',
          backgroundSize: '56px 56px',
        }}
      />

      <div
        className="absolute -right-[35vmax] -top-[52vmax] h-[118vmax] w-[118vmax] rounded-full border border-accent/10 opacity-50"
        style={{
          background:
            'radial-gradient(circle, transparent 28%, rgba(124,108,255,.05) 28.2%, transparent 28.8%, transparent 48%, rgba(36,200,255,.04) 48.2%, transparent 48.8%)',
        }}
      />

      <div
        className="absolute -right-1/3 -top-1/3 h-[150vmax] w-[150vmax] rounded-full opacity-[0.055] motion-safe:animate-[warpath-radar-spin_48s_linear_infinite]"
        style={{
          background: 'conic-gradient(from 0deg, rgba(36,200,255,0.72), transparent 10%, transparent 100%)',
        }}
      />

      {STARS.map((star, i) => (
        <div
          key={i}
          className="absolute rounded-full bg-slate-200 motion-safe:animate-[warpath-star-twinkle_var(--dur)_ease-in-out_infinite]"
          style={{
            left: `${star.left}%`,
            top: `${star.top}%`,
            width: star.size,
            height: star.size,
            opacity: 0.35,
            animationDelay: `${star.delay}s`,
            ['--dur' as string]: `${star.duration}s`,
          }}
        />
      ))}

      {PARTICLES.map((particle, i) => (
        <div
          key={i}
          className="absolute bottom-0 h-1 w-1 rounded-full bg-info/35 shadow-[0_0_12px_currentColor] motion-safe:animate-[warpath-particle-drift_var(--dur)_linear_infinite]"
          style={{
            left: `${particle.left}%`,
            animationDelay: `${particle.delay}s`,
            ['--dur' as string]: `${particle.duration}s`,
          }}
        />
      ))}

      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,transparent_15%,rgba(5,8,18,.58)_78%,rgba(5,8,18,.88)_100%)]" />
    </div>
  );
}
