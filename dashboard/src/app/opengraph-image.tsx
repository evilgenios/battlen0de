import { ImageResponse } from 'next/og';

export const alt = 'BattleN0de — Your Warpath AIO Command Hub.';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          padding: '72px 78px',
          color: '#f8fafc',
          background:
            'radial-gradient(circle at 18% 0%, rgba(124,108,255,.32), transparent 42%), radial-gradient(circle at 100% 90%, rgba(34,211,238,.18), transparent 38%), #03050b',
          fontFamily: 'sans-serif',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
          <div
            style={{
              width: 58,
              height: 58,
              borderRadius: 15,
              border: '1px solid rgba(167,139,250,.5)',
              background: 'rgba(139,92,246,.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 28,
              fontWeight: 800,
              color: '#a78bfa',
            }}
          >
            N0
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <div style={{ fontSize: 26, fontWeight: 750 }}>battlen0de</div>
            <div style={{ marginTop: 5, fontSize: 13, letterSpacing: 4, color: '#a78bfa' }}>PUBLIC BETA · WARPATH CLOUD NODE</div>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', maxWidth: 930 }}>
          <div style={{ fontSize: 84, lineHeight: .98, letterSpacing: -5, fontWeight: 780 }}>
            Your Base.
          </div>
          <div
            style={{
              marginTop: 4,
              fontSize: 84,
              lineHeight: .98,
              letterSpacing: -5,
              fontWeight: 780,
              color: '#67e8f9',
            }}
          >
            One BattleN0de.
          </div>
          <div style={{ marginTop: 30, fontSize: 24, lineHeight: 1.45, color: '#94a3b8' }}>
            Production Buildings, Collection Convoys, Scout Plane telemetry and account operations in one cloud node.
          </div>
        </div>

        <div style={{ display: 'flex', gap: 16, fontSize: 16, color: '#64748b' }}>
          <span>INDIVIDUAL NODE · 1 COMMANDER</span>
          <span>•</span>
          <span>ALLIANCE NODE · MULTI-ACCOUNT</span>
        </div>
      </div>
    ),
    size,
  );
}
