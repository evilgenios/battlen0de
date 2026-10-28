import type { MetadataRoute } from 'next';
import { getSiteUrl } from '@/lib/site';

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl();
  return {
    rules: [
      {
        userAgent: '*',
        allow: ['/', '/terms', '/privacy', '/refunds'],
        disallow: [
          '/api/',
          '/dashboard',
          '/alliance',
          '/accounts',
          '/operations',
          '/events',
          '/settings',
          '/login',
          '/activate',
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
  };
}
