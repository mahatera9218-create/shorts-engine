import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRanking, getAllRankingSlugs } from "@/lib/rankings";
import { SITE_NAME } from "@/lib/wp";
import AdSlot from "@/components/AdSlot";
import RankTabs from "@/components/RankTabs";
import ScoreCompare from "@/components/ScoreCompare";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllRankingSlugs().map((slug) => ({ slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const r = getRanking(params.slug);
  if (!r) return { title: "순위" };
  return {
    title: `${r.title} — ${r.subtitle}`,
    description: r.intro.slice(0, 150),
    // 베타(평가 작업 중)인 동안은 색인 제외. 확정되면 beta:false로 바꾸면 공개.
    robots: r.beta ? { index: false, follow: false } : { index: true, follow: true },
  };
}

export default function RankingPage({ params }: { params: { slug: string } }) {
  const r = getRanking(params.slug);
  if (!r) notFound();

  return (
    <div className="container article">
      <RankTabs current={r.slug} />
      {r.beta ? (
        <div className="mock-banner">
          {r.status === "pending" ? (
            <>📋 <b>준비 중</b> — 근거 자료 검증이 끝난 곳부터 점수·순위를 공개합니다. 아래는 평가 기준입니다.</>
          ) : (
            <>📋 <b>미리보기(베타)</b> — 평가 기준 확정 전 <b>예시 데이터</b>입니다. 점수·순위는 임시이며, 확정 후 공개합니다.</>
          )}
        </div>
      ) : null}

      <span className="a-cat">{r.categoryName}</span>
      <h1>{r.title} — {r.subtitle}</h1>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span>
        <span>{r.updated} 기준 · 매주 갱신</span>
      </div>

      <p className="rank-intro">
        {r.intro} <Link href="#methodology">평가 방법 보기 →</Link>
      </p>

      <AdSlot />

      <div className="rank-list">
        {r.apps.map((a) => (
          <div key={a.slug} className="rank-card">
            <div className={`rank-num${a.rank === 1 ? " top" : ""}`}>{a.pending ? "·" : a.rank}</div>
            <div className="rank-body">
              <div className="rank-head">
                <div>
                  <Link href={`/rank/${r.slug}/${a.slug}`} className="rank-name">{a.name}</Link>
                  <div className="rank-tag">{a.tag}</div>
                </div>
                <div className="rank-score">{a.pending ? <span>평가 대기</span> : <>{a.total.toFixed(1)}<span>/5</span></>}</div>
              </div>
              <p className="rank-note">{a.summary}</p>
              <Link href={`/rank/${r.slug}/${a.slug}`} className="rank-link">
                {a.name} 자세히 보기 →
              </Link>
            </div>
          </div>
        ))}
      </div>

      {r.apps.some((a) => !a.pending) ? (<>
      <h2>항목별 점수 비교</h2>
      <ScoreCompare r={r} />
      </>) : null}

      <h2 id="methodology">평가 방법 (투명 공개)</h2>
      <ul>
        <li><b>기준·가중치</b>: {r.criteria.map((c) => `${c.name} ${c.weight}%`).join(" · ")}.</li>
        <li><b>자료</b>: 공개된 자격·수수료·기능·약관, 앱스토어 평점, 공개된 이용 후기만 사용(지어내지 않음). 근거 자료가 확인되지 않은 항목은 점수를 매기지 않습니다.</li>
        <li><b>갱신</b>: 매주 1회, 최신 이용 동향(검색·언급 추세)을 반영해 재계산.</li>
        <li><b>독립성</b>: 순위는 위 기준으로만 매깁니다. 제휴·광고는 순위에 영향을 주지 않으며 <b>'광고'로 분리 표시</b>합니다.</li>
      </ul>

      <div className="byline-foot">
        이 글은 일반 정보 제공이며 특정 서비스 가입을 권유하지 않습니다. 수수료·혜택은 바뀔 수 있으니 이용 전 각 앱에서 확인하세요. 일부 바로가기는 제휴 링크일 수 있으며, 그 경우 명확히 표시합니다.
      </div>
    </div>
  );
}
