// 글 주제에 맞는 무료 스톡 사진(Unsplash). 저작권 0(Unsplash License).
// UNSPLASH_ACCESS_KEY가 있으면 카테고리별로 검색해 사진을 쓴다. 없으면 null → 생성 표지로 폴백.

const KEY = process.env.UNSPLASH_ACCESS_KEY || "";

const QUERIES: Record<string, string> = {
  jaetech: "investment stock market finance chart",
  realty: "apartment building city korea real estate",
  tax: "tax documents calculator desk paperwork",
  pension: "retirement savings money coins piggy bank",
};
const DEFAULT_QUERY = "finance money economy";

// 카테고리별 사진 후보를 한 번만 받아 캐시(빌드 중). 실패/키 없음이면 빈 배열.
const cache = new Map<string, Promise<string[]>>();

async function pool(catSlug: string): Promise<string[]> {
  if (!KEY) return [];
  const query = QUERIES[catSlug] || DEFAULT_QUERY;
  if (!cache.has(query)) {
    cache.set(
      query,
      (async () => {
        try {
          const r = await fetch(
            `https://api.unsplash.com/search/photos?query=${encodeURIComponent(query)}&per_page=24&orientation=landscape&content_filter=high&client_id=${KEY}`,
            { next: { revalidate: 86400 } },
          );
          if (!r.ok) return [];
          const data = (await r.json()) as { results?: Array<{ urls?: { regular?: string } }> };
          return (data.results ?? [])
            .map((p) => p.urls?.regular)
            .filter((u): u is string => Boolean(u));
        } catch {
          return [];
        }
      })(),
    );
  }
  return cache.get(query)!;
}

function hash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

// 카테고리 사진 중 slug로 고정 선택. 없으면 null.
export async function stockPhoto(catSlug: string | undefined, seed: string): Promise<string | null> {
  const urls = await pool(catSlug || "");
  if (urls.length === 0) return null;
  return urls[hash(seed) % urls.length];
}

// 본문용으로 서로 다른 사진 n장(대표 사진 hero는 제외). 부족하면 있는 만큼만.
export async function stockPhotos(
  catSlug: string | undefined,
  seed: string,
  n: number,
  exclude?: string | null,
): Promise<string[]> {
  const urls = (await pool(catSlug || "")).filter((u) => u !== exclude);
  if (urls.length === 0) return [];
  const out: string[] = [];
  let i = hash(seed) % urls.length;
  for (let k = 0; k < n && out.length < urls.length; k++) {
    out.push(urls[i % urls.length]);
    i += 1;
  }
  return out;
}
