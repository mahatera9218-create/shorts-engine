import type { Metadata } from "next";
import Script from "next/script";
import Link from "next/link";
import "./globals.css";
import { SITE_NAME, SITE_URL, SITE_DESC } from "@/lib/wp";
import Menu from "@/components/Menu";

const ADSENSE_CLIENT =
  process.env.NEXT_PUBLIC_ADSENSE_CLIENT || "ca-pub-6435261744776184";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: `${SITE_NAME} — 세무·절세·연금을 쉽게`,
    template: `%s | ${SITE_NAME}`,
  },
  description: SITE_DESC,
  openGraph: { type: "website", siteName: SITE_NAME, locale: "ko_KR", url: SITE_URL },
  robots: { index: true, follow: true },
  // 검색엔진 소유확인(공개 토큰). 네이버 서치어드바이저.
  verification: {
    other: {
      "naver-site-verification": "77856750d7c78447f76f81fc80a91308d2af573b",
    },
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        {ADSENSE_CLIENT ? (
          <Script
            id="adsbygoogle-init"
            async
            strategy="afterInteractive"
            crossOrigin="anonymous"
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`}
          />
        ) : null}
      </head>
      <body>
        <header className="site-header">
          <div className="container inner">
            <Link href="/" className="brand" aria-label={SITE_NAME}>
              {/* 로고 이미지만. AI로 받은 로고로 교체 시 web/public/logo.svg만 바꾸면 됨. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.svg" alt={SITE_NAME} className="brand-logo" />
            </Link>
            <div className="header-spacer" />
            <Menu />
          </div>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <div className="container">
            <div style={{ marginBottom: 10 }}>
              <Link href="/p/privacy" prefetch={false}>개인정보처리방침</Link>
              <Link href="/p/terms" prefetch={false}>이용약관</Link>
              <Link href="/p/disclaimer" prefetch={false}>면책조항</Link>
              <Link href="/p/contact" prefetch={false}>연락처</Link>
              <Link href="/p/about" prefetch={false}>소개</Link>
            </div>
            © {new Date().getFullYear()} {SITE_NAME} · 일반 정보 제공 목적이며 개별
            사안은 국세청(126)·세무 전문가 확인을 권합니다.
          </div>
        </footer>
      </body>
    </html>
  );
}
