import type { HistoryPoint } from "@/lib/rankings";

// 주간 추이 미니 그래프(서버 컴포넌트, 인라인 SVG). 기록이 2개 미만이면 그리지 않는다.
export default function Sparkline({ points, field, label }: { points: HistoryPoint[]; field: "volume" | "interest"; label: string }) {
  const vals = points.map((p) => p[field]).filter((v): v is number => typeof v === "number");
  if (vals.length < 2) return null;
  const w = 260, h = 56, pad = 4;
  const max = Math.max(...vals), min = Math.min(...vals);
  const span = max - min || 1;
  const pts = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (w - pad * 2);
    const y = h - pad - ((v - min) / span) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg className="spark" viewBox={`0 0 ${w} ${h}`} role="img" aria-label={`${label} 추이 ${vals.length}회 기록`}>
      <polyline points={pts.join(" ")} fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={pts[pts.length - 1].split(",")[0]} cy={pts[pts.length - 1].split(",")[1]} r="3" fill="currentColor" />
    </svg>
  );
}
