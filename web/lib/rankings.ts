// 순위(랭킹) 데이터: web/content/rankings/*.json 을 읽어 점수를 계산한다. 서버 전용(fs).
// 나중에 그록 주간 수집이 이 JSON을 갱신하면 배포 때 자동 반영된다.
import fs from "node:fs";
import path from "node:path";

export interface Criterion {
  key: string;
  name: string;
  weight: number;
}
export interface RankApp {
  slug: string;
  name: string;
  tag: string;
  scores: Record<string, number>;
  summary: string;
  pros: string[];
  cons: string[];
  whoFor: string;
  url: string;
  total: number;
  rank: number;
  pending?: boolean;
}
export interface Ranking {
  slug: string;
  category: string;
  categoryName: string;
  title: string;
  subtitle: string;
  intro: string;
  updated: string;
  beta: boolean;
  status?: "example" | "pending" | "verified";
  criteria: Criterion[];
  apps: RankApp[];
}

const RANK_DIR = path.join(process.cwd(), "content", "rankings");

function weightedTotal(scores: Record<string, number>, criteria: Criterion[]): number {
  let sum = 0;
  let w = 0;
  for (const c of criteria) {
    const s = scores[c.key];
    if (typeof s === "number") {
      sum += s * c.weight;
      w += c.weight;
    }
  }
  return w > 0 ? Math.round((sum / w) * 10) / 10 : 0;
}

function load(slug: string): Ranking | null {
  let raw: string;
  try {
    raw = fs.readFileSync(path.join(RANK_DIR, `${slug}.json`), "utf8");
  } catch {
    return null;
  }
  const data = JSON.parse(raw) as Ranking;
  const scored = data.apps
    .filter((a) => !a.pending)
    .map((a) => ({ ...a, total: weightedTotal(a.scores, data.criteria), rank: 0 }))
    .sort((a, b) => b.total - a.total)
    .map((a, i) => ({ ...a, rank: i + 1 }));
  // 평가 대기 후보는 순위 없이(rank 0) 뒤에 붙인다.
  const waiting = data.apps.filter((a) => a.pending).map((a) => ({ ...a, total: 0, rank: 0 }));
  data.apps = [...scored, ...waiting];
  return data;
}

export function getRanking(slug: string): Ranking | null {
  return load(slug);
}

export function getAllRankingSlugs(): string[] {
  try {
    return fs
      .readdirSync(RANK_DIR)
      .filter((f) => f.endsWith(".json"))
      .map((f) => f.replace(/\.json$/, ""));
  } catch {
    return [];
  }
}

export function getRankingApp(
  slug: string,
  appSlug: string,
): { ranking: Ranking; app: RankApp } | null {
  const ranking = getRanking(slug);
  if (!ranking) return null;
  const app = ranking.apps.find((a) => a.slug === appSlug);
  return app ? { ranking, app } : null;
}

// 탭 순서(고정). 목록에 없는 순위는 뒤에 붙는다.
const TAB_ORDER = ["tax-firms", "law-firms", "tax-apps", "insurance-apps"];
const TAB_LABEL: Record<string, string> = {
  "tax-firms": "세무법인",
  "law-firms": "법무법인",
  "tax-apps": "세무앱",
  "insurance-apps": "보험앱",
};

export function getRankTabs(): { slug: string; label: string }[] {
  const all = getAllRankingSlugs();
  const ordered = [...TAB_ORDER.filter((s) => all.includes(s)), ...all.filter((s) => !TAB_ORDER.includes(s))];
  return ordered.map((slug) => ({ slug, label: TAB_LABEL[slug] ?? getRanking(slug)?.categoryName ?? slug }));
}
