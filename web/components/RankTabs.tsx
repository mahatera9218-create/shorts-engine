import Link from "next/link";
import { getRankTabs } from "@/lib/rankings";

// 순위 탭(서버 컴포넌트 — 링크 이동이라 클라이언트 JS 0). 현재 탭은 active로 강조.
export default function RankTabs({ current }: { current?: string }) {
  const tabs = getRankTabs();
  return (
    <nav className="rank-tabs" aria-label="순위 분류">
      {tabs.map((t) => (
        <Link
          key={t.slug}
          href={`/rank/${t.slug}`}
          className={`rank-tab${t.slug === current ? " active" : ""}`}
          aria-current={t.slug === current ? "page" : undefined}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
