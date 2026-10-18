import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRanking, getRankingApp, getAllRankingSlugs } from "@/lib/rankings";
import { SITE_NAME } from "@/lib/wp";
import AdSlot from "@/components/AdSlot";
import RankTabs from "@/components/RankTabs";
import Sparkline from "@/components/Sparkline";

export const dynamicParams = false;

export function generateStaticParams() {
  const out: { slug: string; app: string }[] = [];
  for (const slug of getAllRankingSlugs()) {
    const r = getRanking(slug);
    r?.apps.forEach((a) => out.push({ slug, app: a.slug }));
  }
  return out;
}

export function generateMetadata({ params }: { params: { slug: string; app: string } }): Metadata {
  const found = getRankingApp(params.slug, params.app);
  if (!found) return { title: "상세" };
  const { ranking, app } = found;
  return {
    title: `${app.name} 공개 지표 — ${ranking.title}`,
    description: app.summary.slice(0, 150),
    robots: ranking.beta ? { index: false, follow: false } : { index: true, follow: true },
  };
}

export default function AppDetailPage({ params }: { params: { slug: string; app: string } }) {
  const found = getRankingApp(params.slug, params.app);
  if (!found) notFound();
  const { ranking, app } = found;
  const hasLink = app.url && app.url !== "#";
  const shown = ranking.criteria.filter((c) => typeof app.scores[c.key] === "number" && app.evidence?.[c.key]);

  return (
    <div className="container article">
      <RankTabs current={ranking.slug} />
      <Link href={`/rank/${ranking.slug}`} className="a-cat">← {ranking.title}</Link>
      <h1>{app.name} 공개 지표</h1>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span>
        <span>{ranking.updated} 기준</span>
      </div>
      <p className="rank-tag" style={{ fontSize: 15 }}>{app.tag}</p>
      <p className="rank-intro">{app.summary}</p>

      <AdSlot />

      <h2>항목별 값</h2>
      {shown.length === 0 ? (
        <p className="cmp-sub">아직 출처를 확인한 지표가 없습니다. 확인되는 대로 표시합니다.</p>
      ) : (
        <div className="score-bars">
          {shown.map((c) => {
            const s = app.scores[c.key];
            const ev = app.evidence![c.key];
            return (
              <div key={c.key} className="score-block">
                <div className="score-row">
                  <div className="score-label">{c.name}</div>
                  <div className="score-track"><div className="score-fill" style={{ width: `${(s / 5) * 100}%` }} /></div>
                  <div className="score-val">{s.toFixed(1)}</div>
                </div>
                <div className="cmp-ev">
                  <em className={ev.type}>{ev.type === "auto" ? "자동 지표" : "직접 확인"}</em>
                  {ev.label} · {ev.checked}
                  {ev.url ? <> · <a href={ev.url} target="_blank" rel="nofollow noopener">출처</a></> : null}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {(app.facts?.length ?? 0) > 0 ? (
        <>
          <h2>확인한 사실</h2>
          <ul>
            {app.facts!.map((f, i) => (
              <li key={i}><b>{f.label}</b>: {f.value} (<a href={f.url} target="_blank" rel="nofollow noopener">출처</a> · {f.checked})</li>
            ))}
          </ul>
        </>
      ) : null}

      {(app.history?.length ?? 0) >= 2 ? (
        <>
          <h2>검색 관심도 추이</h2>
          <div className="spark-item"><Sparkline points={app.history!} field="interest" label={app.name} /></div>
        </>
      ) : null}

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
        <Link href={`/rank/${ranking.slug}`}>← {ranking.title} 전체 보기</Link>
      </p>

      <div className="byline-foot">
        이 글은 일반 정보 제공이며 특정 서비스 가입을 권유하지 않습니다. 수수료·혜택은 바뀔 수 있으니 이용 전 공식 창구에서 확인하세요.
      </div>
    </div>
  );
}
