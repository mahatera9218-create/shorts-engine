import type { Metadata } from "next";
import Link from "next/link";
import { getRanking, getRankTabs, type RankApp } from "@/lib/rankings";
import RankTabs from "@/components/RankTabs";

export const metadata: Metadata = {
  title: "순위",
  description: "세무법인·법무법인·세무앱·보험앱을 공개 기준으로 비교한 순위 모음.",
  // 분류별 순위가 모두 검증 전(베타)이라 허브도 색인 제외. 검증되면 index로 전환.
  robots: { index: false, follow: false },
};

const TOP = 3;   // 처음 보여줄 개수
const MAX = 10;  // '더보기'로 펼쳤을 때 최대 개수

function Row({ slug, a }: { slug: string; a: RankApp }) {
  return (
    <Link href={`/rank/${slug}/${a.slug}`} className="hub-row">
      <span className={`rank-num${a.rank === 1 ? " top" : ""}`}>{a.pending ? "·" : a.rank}</span>
      <span className="hub-name">{a.name}<small>{a.tag}</small></span>
      <span className="hub-score">{a.pending ? "대기" : a.total.toFixed(1)}</span>
    </Link>
  );
}

export default function RankHub() {
  const tabs = getRankTabs();
  return (
    <div className="container article">
      <RankTabs />
      <h1>순위 모음</h1>
      <p className="rank-intro">분류별 상위 {TOP}곳을 먼저 보여드립니다. 근거 자료가 확인된 곳만 점수를 공개합니다.</p>

      {tabs.map((t) => {
        const r = getRanking(t.slug);
        if (!r) return null;
        const apps = r.apps.slice(0, MAX);
        const head = apps.slice(0, TOP);
        const more = apps.slice(TOP);
        return (
          <section key={t.slug} className="hub-cat">
            <div className="hub-cat-head">
              <h2>{t.label}</h2>
              <Link href={`/rank/${t.slug}`} className="hub-all">전체 보기 →</Link>
            </div>
            <div className="rank-tag">
              {r.status === "pending" ? "준비 중 · 근거 확인 후 점수 공개" : r.beta ? "베타(예시 데이터)" : `${r.updated} 기준`}
            </div>
            {head.length === 0 ? (
              <p className="rank-note">아직 공개할 업체가 없습니다. 평가 기준은 <Link href={`/rank/${t.slug}#methodology`}>여기</Link>에서 볼 수 있습니다.</p>
            ) : (
              <div className="hub-list">
                {head.map((a) => <Row key={a.slug} slug={t.slug} a={a} />)}
                {more.length > 0 ? (
                  <details className="hub-more">
                    <summary>순위 더보기 ({more.length})</summary>
                    {more.map((a) => <Row key={a.slug} slug={t.slug} a={a} />)}
                  </details>
                ) : null}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
