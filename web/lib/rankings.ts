// 공개 지표 비교 데이터: web/content/rankings/*.json 을 읽는다. 서버 전용(fs).
// 종합 점수·순위는 만들지 않는다. 항목별 값과 근거(출처·확인일)를 그대로 보여 주고, 근거 없는 항목은 숨긴다.
import fs from "node:fs";
import path from "node:path";

export interface Criterion {
  key: string;
  name: string;
  note?: string;
}
export interface Evidence {
  type: "auto" | "manual";
  source: string;
  label: string;
  url?: string;
  checked: string;
}
export interface Fact {
  label: string;
  value: string;
  url: string;
  checked: string;
}
export interface HistoryPoint {
  date: string;
  volume?: number;
  interest?: number;
}
export interface RankApp {
  slug: string;
  name: string;
  tag: string;
  summary: string;
  url: string;
  scores: Record<string, number>;
  evidence?: Record<string, Evidence>;
  facts?: Fact[];
  history?: HistoryPoint[];
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
  status?: "beta" | "pending" | "verified";
  criteria: Criterion[];
  apps: RankApp[];
  related?: string[];
}

const RANK_DIR = path.join(process.cwd(), "content", "rankings");

function load(slug: string): Ranking | null {
  let raw: string;
  try {
    raw = fs.readFileSync(path.join(RANK_DIR, `${slug}.json`), "utf8");
  } catch {
    return null;
  }
  const data = JSON.parse(raw) as Ranking;
  data.apps = data.apps.map((a) => ({ ...a, scores: a.scores ?? {} }));
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

// 값(점수)이 하나라도 있는 항목만 비교에 쓴다. 근거 없는 항목은 화면에서 숨긴다.
export function activeCriteria(r: Ranking): Criterion[] {
  return r.criteria.filter((c) => r.apps.some((a) => !a.pending && typeof a.scores[c.key] === "number"));
}

// 탭 순서(고정). 목록에 없는 분류는 뒤에 붙는다.
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
