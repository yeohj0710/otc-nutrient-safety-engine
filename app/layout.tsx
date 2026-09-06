import type { Metadata } from "next";
import { Noto_Sans_KR } from "next/font/google";

import { SiteFrame } from "@/src/components/site-frame";
import { getSiteUrl, siteDescription, siteKeywords, siteName } from "@/src/lib/site";

import "./globals.css";

/* 의약품안전나라(nedrug.mfds.go.kr)가 쓰는 본문 글꼴. 빌드 때 받아 두므로
   방문자 기기에 설치돼 있지 않아도 같은 글꼴로 보인다. */
const appFont = Noto_Sans_KR({
  variable: "--font-app-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: getSiteUrl(),
  applicationName: siteName,
  title: {
    default: siteName,
    template: `%s | ${siteName}`,
  },
  description: siteDescription,
  keywords: siteKeywords,
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: [
      { url: "/yonsei-logo.svg", type: "image/svg+xml" },
    ],
    shortcut: "/yonsei-logo.svg",
    apple: "/yonsei-logo.svg",
  },
  manifest: "/manifest.webmanifest",
  openGraph: {
    type: "website",
    locale: "ko_KR",
    siteName,
    title: siteName,
    description: siteDescription,
    url: "/",
  },
  twitter: {
    card: "summary",
    title: siteName,
    description: siteDescription,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
      "max-video-preview": -1,
    },
  },
  category: "health",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="ko"
      className={`${appFont.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <SiteFrame>{children}</SiteFrame>
      </body>
    </html>
  );
}
