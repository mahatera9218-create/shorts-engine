import Link from "next/link";
import type { Evidence, Ranking } from "@/lib/rankings";

// 항목별 점수 비교(모바일 우선): 항목마다 카드 하나, 안에서 앱을 점수 높은 순으로 막대로 보여 준다.
// 점수마다 근거(자동 지표/수동 확인)와 확인일을 함께 표시하고, 근거가 없는 항목은 '확인 중'으로 둔다.
export default function ScoreCompare({ r }: { r: Ranking }) {
  const apps = r.apps.filter((a) => !a.pending);
  if (apps.length === 0) return null;
  return (
    <div className="cmp">
      {r.criteria.map((c) => {
        const rows = apps
          .map((a) => ({ a, s: a.scores[c.key], ev: a.evidence?.[c.key] }))
          .filter((x): x is { a: (typeof apps)[number]; s: number; ev: Evidence | undefined } => typeof x.s === "number")
          .sort((x, y) => y.s - x.s);
        if (rows.length === 0) {
          return (
            <section key={c.key} className="cmp-card muted">
              <div className="cmp-head"><h3>{c.name}</h3><span>가중치 {c.weight}%</span></div>
              <p className="cmp-empty">근거 자료 확인 중 — 확인되면 점수를 공개합니다.</p>
            </section>
          );
        }
        const top = rows[0].s;
        return (
          <section key={c.key} className="cmp-card">
            <div className="cmp-head">
              <h3>{c.name}</h3>
              <span>가중치 {c.weight}%</span>
            </div>
            {rows.map(({ a, s, ev }) => (
              <div key={a.slug} className="cmp-item">
                <div className={`cmp-row${s === top ? " lead" : ""}`}>
                  <Link href={`/rank/${r.slug}/${a.slug}`} className="cmp-name">{a.name}</Link>
                  <div className="cmp-bar"><i style={{ width: `${(s / 5) * 100}%` }} /></div>
                  <b className="cmp-val">{s.toFixed(1)}</b>
                </div>
                {ev ? (
                  <div className="cmp-ev">
                    <em className={ev.type}>{ev.type === "auto" ? "자동 지표" : "직접 확인"}</em>
                    {ev.label} · {ev.checked}
                    {ev.url ? <> · <a href={ev.url} target="_blank" rel="nofollow noopener">출처</a></> : null}
                  </div>
                ) : null}
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
