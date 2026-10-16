import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRanking, getRankingApp, getAllRankingSlugs } from "@/lib/rankings";
import { SITE_NAME } from "@/lib/wp";
import AdSlot from "@/components/AdSlot";
import RankTabs from "@/components/RankTabs";

export const dynamicParams = false;

export function generateStaticParams() {
  const out: { slug: string; app: string }[] = [];
  for (const slug of getAllRankingSlugs()) {
    const r = getRanking(slug);
    r?.apps.forEach((a) => out.push({ slug, app: a.slug }));
  }
  return out;
}

export function generateMetadata({
  params,
}: {
  params: { slug: string; app: string };
}): Metadata {
  const found = getRankingApp(params.slug, params.app);
  if (!found) return { title: "상세" };
  const { ranking, app } = found;
  return {
    title: `${app.name} 평가·리뷰 — ${ranking.title}`,
    description: app.summary.slice(0, 150),
    robots: ranking.beta ? { index: false, follow: false } : { index: true, follow: true },
  };
}

export default function AppDetailPage({
  params,
}: {
  params: { slug: string; app: string };
}) {
  const found = getRankingApp(params.slug, params.app);
  if (!found) notFound();
  const { ranking, app } = found;
  const hasLink = app.url && app.url !== "#";

  return (
    <div className="container article">
      <RankTabs current={ranking.slug} />
      <Link href={`/rank/${ranking.slug}`} className="a-cat">← {ranking.title}</Link>
      <h1>{app.name} 평가·리뷰</h1>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span>
        <span>{ranking.updated} 기준</span>
      </div>

      <div className="detail-head">
        <div className="detail-rank">{app.pending ? <>{ranking.categoryName} 후보 · <b>평가 대기</b></> : <>{ranking.categoryName} {ranking.apps.filter((x) => !x.pending).length}개 중 <b>{app.rank}위</b></>}</div>
        {app.pending ? null : <div className="detail-total">{app.total.toFixed(1)}<span>/5</span></div>}
      </div>
      <p className="rank-tag" style={{ fontSize: 15 }}>{app.tag}</p>

      <p className="rank-intro">{app.summary}</p>

      <AdSlot />

      {app.pending ? null : (<>
      <h2>항목별 점수</h2>
      <div className="score-bars">
        {ranking.criteria.map((c) => {
          const s = app.scores[c.key] ?? 0;
          return (
            <div key={c.key} className="score-row">
              <div className="score-label">{c.name}</div>
              <div className="score-track"><div className="score-fill" style={{ width: `${(s / 5) * 100}%` }} /></div>
              <div className="score-val">{s.toFixed(1)}</div>
            </div>
          );
        })}
      </div>
      </>)}

      {app.pending ? null : (<>
      <h2>이런 분에게 맞아요</h2>
      <p>{app.whoFor}</p>

      <div className="proscons">
        <div className="pros">
          <h3>장점</h3>
          <ul>{app.pros.map((p, i) => <li key={i}>{p}</li>)}</ul>
        </div>
        <div className="cons">
          <h3>아쉬운 점</h3>
          <ul>{app.cons.map((c, i) => <li key={i}>{c}</li>)}</ul>
        </div>
      </div>
      </>)}

      {/* 외부 바로가기 (여기서 광고 한 번 더 노출) */}
      <AdSlot />
      <div className="detail-cta">
        {hasLink ? (
          <a className="cta-btn" href={app.url} target="_blank" rel="nofollow sponsored noopener">
            {app.name} 공식 사이트 바로가기 ↗
          </a>
        ) : (
          <span className="cta-btn disabled">공식 링크 확인 중</span>
        )}
        <p className="cta-note">* 외부 사이트로 이동합니다. 일부 링크는 제휴 링크일 수 있으며, 그 경우 명확히 표시합니다.</p>
      </div>

      <p style={{ marginTop: 28 }}>
        <Link href={`/rank/${ranking.slug}`}>← {ranking.title} 전체 순위 보기</Link>
      </p>

      <div className="byline-foot">
        이 글은 일반 정보 제공이며 특정 서비스 가입을 권유하지 않습니다. 수수료·혜택은 바뀔 수 있으니 이용 전 공식 창구에서 확인하세요.
      </div>
    </div>
  );
}
