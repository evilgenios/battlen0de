import type { MetadataRoute } from 'next';

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'BattleN0de',
    short_name: 'BattleN0de',
    description: 'Warpath: Ace Shooter AIO command hub for linked Commander accounts.',
    start_url: '/',
    display: 'standalone',
    background_color: '#03050b',
    theme_color: '#070b15',
    icons: [
      { src: '/icon.svg', sizes: 'any', type: 'image/svg+xml' },
    ],
  };
}
