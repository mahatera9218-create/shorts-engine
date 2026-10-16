import type { Metadata } from "next";
import Link from "next/link";
import { getRanking, getRankTabs } from "@/lib/rankings";
import RankTabs from "@/components/RankTabs";

export const metadata: Metadata = {
  title: "순위",
  description: "세무법인·법무법인·세무앱·보험앱을 공개 기준으로 비교한 순위 모음.",
  // 분류별 순위가 모두 검증 전(베타)이라 허브도 색인 제외. 검증되면 index로 전환.
  robots: { index: false, follow: false },
};

export default function RankHub() {
  const tabs = getRankTabs();
  return (
    <div className="container article">
      <RankTabs />
      <h1>순위 모음</h1>
      <p className="rank-intro">분류를 골라 공개 기준으로 비교해 보세요. 근거 자료가 확인된 곳만 점수를 공개합니다.</p>
      <div className="rank-list">
        {tabs.map((t) => {
          const r = getRanking(t.slug);
          if (!r) return null;
          return (
            <div key={t.slug} className="rank-card">
              <div className="rank-body">
                <Link href={`/rank/${t.slug}`} className="rank-name">{t.label}</Link>
                <div className="rank-tag">{r.status === "pending" ? "준비 중 · 기준 공개" : r.beta ? "베타(예시 데이터)" : `${r.updated} 기준`}</div>
                <p className="rank-note">{r.title}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
