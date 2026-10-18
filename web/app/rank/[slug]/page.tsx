import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getRanking, getAllRankingSlugs, activeCriteria } from "@/lib/rankings";
import { getPostBySlug, stripHtml, SITE_NAME } from "@/lib/wp";
import AdSlot from "@/components/AdSlot";
import RankTabs from "@/components/RankTabs";
import MetricCompare, { type CompareRow } from "@/components/MetricCompare";
import Sparkline from "@/components/Sparkline";

export const dynamicParams = false;

export function generateStaticParams() {
  return getAllRankingSlugs().map((slug) => ({ slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const r = getRanking(params.slug);
  if (!r) return { title: "공개 지표 비교" };
  return {
    title: `${r.title} — ${r.subtitle}`,
    description: r.intro.slice(0, 150),
    // 베타(데이터 수집·검증 중)인 동안은 색인 제외. 검증되면 beta:false로 바꾸면 공개.
    robots: r.beta ? { index: false, follow: false } : { index: true, follow: true },
  };
}

export default async function RankingPage({ params }: { params: { slug: string } }) {
  const r = getRanking(params.slug);
  if (!r) notFound();

  const criteria = activeCriteria(r);
  const live = r.apps.filter((a) => !a.pending);
  const rows: CompareRow[] = live.map((a) => ({
    slug: a.slug,
    name: a.name,
    vals: Object.fromEntries(
      criteria
        .filter((c) => typeof a.scores[c.key] === "number" && a.evidence?.[c.key])
        .map((c) => {
          const ev = a.evidence![c.key];
          return [c.key, { s: a.scores[c.key], label: ev.label, checked: ev.checked, type: ev.type, url: ev.url }];
        }),
    ),
  }));
  const factApps = r.apps.filter((a) => (a.facts?.length ?? 0) > 0);
  const histApps = r.apps.filter((a) => (a.history?.length ?? 0) >= 2);
  const related = (
    await Promise.all((r.related ?? []).map((s) => getPostBySlug(s)))
  ).filter((p): p is NonNullable<typeof p> => Boolean(p));

  return (
    <div className="container article">
      <RankTabs current={r.slug} />
      {r.beta ? (
        <div className="mock-banner">
          {r.status === "pending" ? (
            <>📋 <b>준비 중</b> — 출처를 확인한 자료만 공개합니다. 근거가 없는 항목은 표시하지 않습니다.</>
          ) : (
            <>📋 <b>베타</b> — 데이터 수집·검증 중입니다. 이 페이지는 <b>순위가 아니라 공개 지표 비교</b>입니다.</>
          )}
        </div>
      ) : null}

      <span className="a-cat">{r.categoryName}</span>
      <h1>{r.title}</h1>
      <p className="rank-tag" style={{ fontSize: 15 }}>{r.subtitle}</p>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span>
        <span>{r.updated} 기준 · 매주 갱신</span>
      </div>

      <p className="rank-intro">
        {r.intro} <Link href="#methodology">비교 방법 보기 →</Link>
      </p>

      <AdSlot />

      {r.apps.length > 0 ? (
        <>
          <h2>한눈에 보기</h2>
          <div className="rank-list">
            {r.apps.map((a) => (
              <div key={a.slug} className="rank-card">
                <div className="rank-body">
                  <Link href={`/rank/${r.slug}/${a.slug}`} className="rank-name">{a.name}</Link>
                  <div className="rank-tag">{a.tag}</div>
                  <p className="rank-note">{a.summary}</p>
                  <Link href={`/rank/${r.slug}/${a.slug}`} className="rank-link">
                    {a.name} 지표 보기 →
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {criteria.length > 0 && rows.length > 0 ? (
        <>
          <h2>공개 지표 비교</h2>
          <p className="cmp-sub">보고 싶은 항목을 고르면 그 값 순으로 보여 드립니다. 종합 점수·순위는 만들지 않습니다.</p>
          <MetricCompare slugBase={`/rank/${r.slug}`} criteria={criteria} rows={rows} />
        </>
      ) : null}

      {factApps.length > 0 ? (
        <>
          <h2>확인한 사실</h2>
          <p className="cmp-sub">공식 페이지에서 직접 확인한 내용만, 출처 링크와 함께 적었습니다.</p>
          <figure className="wp-block-table">
            <table>
              <thead><tr><th>대상</th><th>항목</th><th>내용</th><th>출처</th></tr></thead>
              <tbody>
                {factApps.flatMap((a) =>
                  (a.facts ?? []).map((f, i) => (
                    <tr key={`${a.slug}-${i}`}>
                      <td>{a.name}</td><td>{f.label}</td><td>{f.value}</td>
                      <td><a href={f.url} target="_blank" rel="nofollow noopener">링크</a> · {f.checked}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </figure>
        </>
      ) : null}

      {histApps.length > 0 ? (
        <>
          <h2>검색 관심도 추이</h2>
          <p className="cmp-sub">매주 기록한 최근 4주 관심도입니다(같은 비교 그룹 내 상대값).</p>
          <div className="spark-list">
            {histApps.map((a) => (
              <div key={a.slug} className="spark-item">
                <span>{a.name}</span>
                <Sparkline points={a.history!} field="interest" label={a.name} />
              </div>
            ))}
          </div>
        </>
      ) : null}

      {related.length > 0 ? (
        <>
          <h2>함께 보면 좋은 글</h2>
          <ul>
            {related.map((p) => (
              <li key={p.slug}><Link href={`/${p.slug}`}>{stripHtml(p.title.rendered)}</Link></li>
            ))}
          </ul>
        </>
      ) : null}

      <h2 id="methodology">비교 방법 (투명 공개)</h2>
      <ul>
        <li><b>종합 점수·순위 없음</b>: 임의 가중치로 서열을 만들지 않고, 항목별 값을 그대로 보여 드립니다.</li>
        <li><b>자동 지표</b>: 네이버 검색 데이터(월 검색수·검색 관심도)와 앱스토어 평점을 매주 수집합니다. '얼마나 알려지고 찾는가'를 보여 줄 뿐, 서비스의 좋고 나쁨을 뜻하지 않습니다.</li>
        <li><b>직접 확인</b>: 수수료·운영사 같은 사실은 공식 페이지를 사람이 확인하고 링크와 확인일을 적습니다.</li>
        <li><b>근거가 없으면 표시하지 않습니다</b>: 출처를 확인하지 못한 항목은 비워 두지 않고 화면에서 뺍니다.</li>
        <li><b>독립성</b>: 제휴·광고는 표시 내용에 영향을 주지 않으며 '광고'로 분리 표시합니다.</li>
      </ul>

      <div className="byline-foot">
        이 글은 일반 정보 제공이며 특정 서비스 가입을 권유하지 않습니다. 수수료·혜택은 바뀔 수 있으니 이용 전 각 서비스에서 확인하세요. 일부 바로가기는 제휴 링크일 수 있으며, 그 경우 명확히 표시합니다.
      </div>
    </div>
  );
}
