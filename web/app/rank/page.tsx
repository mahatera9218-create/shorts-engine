import type { Metadata } from "next";
import Link from "next/link";
import { getRanking, getRankTabs, type RankApp } from "@/lib/rankings";
import RankTabs from "@/components/RankTabs";

export const metadata: Metadata = {
  title: "공개 지표 비교",
  description: "세무법인·법무법인·세무앱·보험앱을 출처가 있는 공개 지표로 비교합니다.",
  // 분류별 데이터가 모두 수집·검증 전(베타)이라 허브도 색인 제외. 검증되면 index로 전환.
  robots: { index: false, follow: false },
};

const TOP = 3;   // 처음 보여줄 개수
const MAX = 10;  // '더보기'로 펼쳤을 때 최대 개수

// 허브 정렬 기준: 최근 관심도 → 인지도 순. 값이 없으면 뒤로(이름순).
function sortApps(apps: RankApp[]): RankApp[] {
  const v = (a: RankApp) => a.scores.interest ?? a.scores.awareness ?? -1;
  return [...apps].sort((a, b) => v(b) - v(a) || a.name.localeCompare(b.name, "ko"));
}

function Row({ slug, a }: { slug: string; a: RankApp }) {
  const ev = a.evidence?.interest ?? a.evidence?.awareness;
  return (
    <Link href={`/rank/${slug}/${a.slug}`} className="hub-row">
      <span className="rank-num">·</span>
      <span className="hub-name">{a.name}<small>{ev ? ev.label : a.tag}</small></span>
      <span className="hub-score">{typeof a.scores.interest === "number" ? a.scores.interest.toFixed(1) : "–"}</span>
    </Link>
  );
}

export default function RankHub() {
  const tabs = getRankTabs();
  return (
    <div className="container article">
      <RankTabs />
      <h1>공개 지표 비교</h1>
      <p className="rank-intro">분류별로 출처가 확인된 지표를 보여 드립니다. 종합 점수·순위는 만들지 않고, 처음엔 {TOP}곳만 보이며 &lsquo;더보기&rsquo;로 최대 {MAX}곳까지 펼칠 수 있습니다.</p>

      {tabs.map((t) => {
        const r = getRanking(t.slug);
        if (!r) return null;
        const apps = sortApps(r.apps).slice(0, MAX);
        const head = apps.slice(0, TOP);
        const more = apps.slice(TOP);
        return (
          <section key={t.slug} className="hub-cat">
            <div className="hub-cat-head">
              <h2>{t.label}</h2>
              <Link href={`/rank/${t.slug}`} className="hub-all">전체 보기 →</Link>
            </div>
            <div className="rank-tag">
              {r.status === "pending" ? "준비 중 · 출처 확인 후 공개" : r.beta ? "베타 · 데이터 수집 중(관심도 점수, 5점 만점)" : `${r.updated} 기준`}
            </div>
            {head.length === 0 ? (
              <p className="rank-note">아직 공개할 대상이 없습니다. 비교 방법은 <Link href={`/rank/${t.slug}#methodology`}>여기</Link>에서 볼 수 있습니다.</p>
            ) : (
              <div className="hub-list">
                {head.map((a) => <Row key={a.slug} slug={t.slug} a={a} />)}
                {more.length > 0 ? (
                  <details className="hub-more">
                    <summary>더보기 ({more.length})</summary>
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
