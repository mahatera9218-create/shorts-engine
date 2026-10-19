import type { Metadata } from "next";
import Link from "next/link";
import fs from "node:fs";
import path from "node:path";
import { SITE_NAME, SITE_URL, SITE_DESC, EDITOR_NAME, CONTACT_EMAIL } from "@/lib/wp";
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
  alternates: { types: { "application/rss+xml": `${SITE_URL}/rss.xml` } },
  // 검색엔진 소유확인(공개 토큰). 네이버 서치어드바이저.
  verification: {
    other: {
      "naver-site-verification": [
        "77856750d7c78447f76f81fc80a91308d2af573b",
        "18ac1493a909859444407b5105f7b234e15c242e", // 2026-10-18 서치어드바이저 추가 소유확인
      ],
      // 애드센스 소유확인 메타(광고 JS는 head의 adsbygoogle 스크립트가 로드).
      ...(ADSENSE_CLIENT ? { "google-adsense-account": ADSENSE_CLIENT } : {}),
    },
  },
};

// CSS를 <style>로 HTML에 인라인(작은 파일 11KB) → 별도 CSS 요청·렌더링 차단 제거(PageSpeed).
const CSS = fs.readFileSync(path.join(process.cwd(), "app", "globals.css"), "utf8");

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <style dangerouslySetInnerHTML={{ __html: CSS }} />
        {/* 애드센스 광고 스크립트 — head에 고정(심사 크롤러가 바로 감지). 소유확인 메타와 함께 둔다. */}
        {ADSENSE_CLIENT ? (
          <script
            async
            src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`}
            crossOrigin="anonymous"
          />
        ) : null}
      </head>
      <body>
        <header className="site-header">
          <div className="container inner">
            <Link href="/" className="brand" aria-label={SITE_NAME}>
              {/* 로고 이미지만. AI로 받은 로고로 교체 시 web/public/logo.svg만 바꾸면 됨. */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/logo.webp" alt={SITE_NAME} className="brand-logo" width={111} height={30} fetchPriority="high" />
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
              <Link href="/p/editorial" prefetch={false}>편집 원칙</Link>
              <Link href="/tools" prefetch={false}>판정 도구</Link>
              <Link href="/p/about" prefetch={false}>소개</Link>
            </div>
            © {new Date().getFullYear()} {SITE_NAME} · 운영·편집 책임 {EDITOR_NAME} · 문의 {CONTACT_EMAIL} · 일반 정보 제공 목적이며 개별
            사안은 국세청(126)·세무 전문가 확인을 권합니다.
          </div>
        </footer>
      </body>
    </html>
  );
}
