import Link from "next/link";
import type { Ranking } from "@/lib/rankings";

// 항목별 점수 비교(모바일 우선): 항목마다 카드 하나, 안에서 앱을 점수 높은 순으로 막대로 보여 준다.
// 표(열 7개)는 좁은 화면에서 읽기 어려워 항목 단위로 쪼갠다. 1등은 강조, 막대 길이 = 점수/5.
export default function ScoreCompare({ r }: { r: Ranking }) {
  const apps = r.apps.filter((a) => !a.pending);
  if (apps.length === 0) return null;
  return (
    <div className="cmp">
      {r.criteria.map((c) => {
        const rows = apps
          .map((a) => ({ a, s: a.scores[c.key] }))
          .filter((x): x is { a: typeof apps[number]; s: number } => typeof x.s === "number")
          .sort((x, y) => y.s - x.s);
        if (rows.length === 0) return null;
        const top = rows[0].s;
        return (
          <section key={c.key} className="cmp-card">
            <div className="cmp-head">
              <h3>{c.name}</h3>
              <span>가중치 {c.weight}%</span>
            </div>
            {rows.map(({ a, s }) => (
              <div key={a.slug} className={`cmp-row${s === top ? " lead" : ""}`}>
                <Link href={`/rank/${r.slug}/${a.slug}`} className="cmp-name">{a.name}</Link>
                <div className="cmp-bar"><i style={{ width: `${(s / 5) * 100}%` }} /></div>
                <b className="cmp-val">{s.toFixed(1)}</b>
              </div>
            ))}
          </section>
        );
      })}
    </div>
  );
}
