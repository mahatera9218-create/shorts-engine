// 워드프레스 REST(headless CMS)에서 글·페이지를 읽는다.
// 사이트가 잠깐 안 떠도 빌드가 깨지지 않게 실패 시 빈 값을 돌려준다(런타임 ISR로 채움).

export const WP_API_BASE =
  process.env.WP_API_BASE || "https://astacgroup.com/wp-json/wp/v2";

export const SITE_NAME = process.env.NEXT_PUBLIC_SITE_NAME || "억선생의 경제판";
export const SITE_URL =
  process.env.NEXT_PUBLIC_SITE_URL || "https://astacgroup.com";
export const SITE_DESC =
  process.env.NEXT_PUBLIC_SITE_DESC ||
  "세무·절세·연금을 쉽게 — 숫자로 정확하게 정리하는 경제 블로그.";

// 발행 전/후 반영 지연(초). 10분마다 최신 글을 다시 받아 온다(ISR).
const REVALIDATE = 600;

export interface WpRendered {
  rendered: string;
}
export interface WpPost {
  id: number;
  slug: string;
  date: string;
  modified: string;
  link: string;
  title: WpRendered;
  excerpt: WpRendered;
  content: WpRendered;
  _embedded?: {
    "wp:featuredmedia"?: Array<{
      source_url?: string;
      alt_text?: string;
      media_details?: { width?: number; height?: number };
    }>;
    author?: Array<{ name?: string }>;
  };
}

async function wpGet<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${WP_API_BASE}${path}`, {
      next: { revalidate: REVALIDATE },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

export async function getPosts(perPage = 20): Promise<WpPost[]> {
  const data = await wpGet<WpPost[]>(
    `/posts?per_page=${perPage}&_embed&orderby=date&order=desc`,
  );
  return data ?? [];
}

export async function getPostBySlug(slug: string): Promise<WpPost | null> {
  const data = await wpGet<WpPost[]>(
    `/posts?slug=${encodeURIComponent(slug)}&_embed`,
  );
  return data && data.length > 0 ? data[0] : null;
}

export async function getPageBySlug(slug: string): Promise<WpPost | null> {
  const data = await wpGet<WpPost[]>(
    `/pages?slug=${encodeURIComponent(slug)}&_embed`,
  );
  return data && data.length > 0 ? data[0] : null;
}

export async function getAllPostSlugs(): Promise<string[]> {
  const posts = await getPosts(100);
  return posts.map((p) => p.slug).filter(Boolean);
}

export async function getAllPageSlugs(): Promise<string[]> {
  const data = await wpGet<WpPost[]>(`/pages?per_page=100`);
  return (data ?? []).map((p) => p.slug).filter(Boolean);
}

// 대표 이미지(featured) URL과 대체텍스트를 뽑는다.
export function featuredImage(
  post: WpPost,
): { url: string; alt: string; width?: number; height?: number } | null {
  const m = post._embedded?.["wp:featuredmedia"]?.[0];
  if (!m?.source_url) return null;
  return {
    url: m.source_url,
    alt: m.alt_text || stripHtml(post.title.rendered),
    width: m.media_details?.width,
    height: m.media_details?.height,
  };
}

export function stripHtml(html: string): string {
  return html
    .replace(/<[^>]*>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&#8217;/g, "’")
    .replace(/&#8216;/g, "‘")
    .replace(/&#x27;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&hellip;/g, "…")
    .trim();
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}
