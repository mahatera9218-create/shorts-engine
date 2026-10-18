"use client";
import Link from "next/link";
import { useState } from "react";

// 공개 지표 비교: 보고 싶은 항목을 고르면 그 항목 값 순으로 막대를 정렬해 보여 준다(종합 점수·순위 없음).
export interface CompareRow {
  slug: string;
  name: string;
  vals: Record<string, { s: number; label: string; checked: string; type: "auto" | "manual"; url?: string }>;
}
export default function MetricCompare({
  slugBase,
  criteria,
  rows,
}: {
  slugBase: string;
  criteria: { key: string; name: string; note?: string }[];
  rows: CompareRow[];
}) {
  const [key, setKey] = useState(criteria[0]?.key);
  if (!key) return null;
  const cur = criteria.find((c) => c.key === key)!;
  const list = rows
    .filter((r) => r.vals[key])
    .sort((a, b) => b.vals[key].s - a.vals[key].s);
  return (
    <div className="mc">
      <div className="mc-tabs" role="tablist" aria-label="비교 항목">
        {criteria.map((c) => (
          <button key={c.key} role="tab" aria-selected={c.key === key} className={c.key === key ? "on" : ""} onClick={() => setKey(c.key)}>
            {c.name}
          </button>
        ))}
      </div>
      {cur.note ? <p className="mc-note">{cur.note}</p> : null}
      {list.map((r) => {
        const v = r.vals[key];
        return (
          <div key={r.slug} className="cmp-item">
            <div className="cmp-row">
              <Link href={`${slugBase}/${r.slug}`} className="cmp-name">{r.name}</Link>
              <div className="cmp-bar"><i style={{ width: `${(v.s / 5) * 100}%` }} /></div>
              <b className="cmp-val">{v.s.toFixed(1)}</b>
            </div>
            <div className="cmp-ev">
              <em className={v.type}>{v.type === "auto" ? "자동 지표" : "직접 확인"}</em>
              {v.label} · {v.checked}
              {v.url ? <> · <a href={v.url} target="_blank" rel="nofollow noopener">출처</a></> : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
