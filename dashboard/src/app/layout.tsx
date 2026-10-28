import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SiteBoundary } from "@/components/layout/SiteBoundary";
import { THEME_INIT_SCRIPT } from "@/components/layout/ThemeToggle";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: "BattleN0de — Your Warpath AIO Command Hub.",
    template: "%s · BattleN0de",
  },
  description:
    "BattleN0de is a Warpath: Ace Shooter AIO command hub for Base status, Production Buildings, Collection Convoys, Scout Plane actions, Conquest Guard and account activity.",
  applicationName: "BattleN0de",
  keywords: [
    "Warpath",
    "Warpath Ace Shooter dashboard",
    "Warpath Base dashboard",
    "Warpath Production Buildings",
    "Warpath AIO dashboard",
  ],
  openGraph: {
    type: "website",
    title: "BattleN0de — One Account. Total Command.",
    description:
      "Monitor your Base, Production Buildings, Collection Convoys and Conquest Guard from one BattleN0de.",
    siteName: "BattleN0de",
    images: ["/opengraph-image"],
  },
  twitter: {
    card: "summary_large_image",
    title: "BattleN0de — One Account. Total Command.",
    description:
      "Monitor production, active operations and account state from one cloud command center.",
    images: ["/opengraph-image"],
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="min-h-full">
        <SiteBoundary>{children}</SiteBoundary>
      </body>
    </html>
  );
}
