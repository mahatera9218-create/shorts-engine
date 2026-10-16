// 사이트 상수·타입·순수 헬퍼. fs를 쓰지 않아 클라이언트 컴포넌트에서도 import 가능.
// (실제 글 읽기는 서버 전용 lib/wp.ts에서 한다.)

export const SITE_NAME = "일드레터";
export const SITE_DESC = "재테크·부동산·세금·연금을 쉽게, 정확하게 정리합니다.";
// 사이트 정식 주소는 코드에 고정한다. (환경변수에 vercel.app 등 옛 주소가 박혀 있으면
// 사이트맵·canonical이 엉뚱한 주소를 가리켜 구글 색인이 안 되던 문제를 없앤다.)
export const SITE_URL = "https://astacgroup.com";

// 고정 카테고리 순서(네비게이션용).
export const CATEGORY_ORDER: Array<{ slug: string; name: string }> = [
  { slug: "jaetech", name: "재테크" },
  { slug: "realty", name: "부동산" },
  { slug: "tax", name: "세금·절세" },
  { slug: "pension", name: "연금·노후" },
];

export function categoryName(slug: string): string {
  return CATEGORY_ORDER.find((c) => c.slug === slug)?.name ?? slug;
}

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
    "wp:term"?: Array<
      Array<{ id: number; name: string; slug: string; taxonomy: string }>
    >;
  };
}
export interface WpCategory {
  id: number;
  name: string;
  slug: string;
  count: number;
}

export function postCategory(
  post: WpPost,
): { name: string; slug: string } | null {
  const terms = post._embedded?.["wp:term"]?.flat() ?? [];
  const cat = terms.find((t) => t.taxonomy === "category");
  return cat ? { name: cat.name, slug: cat.slug } : null;
}

// 대표 이미지(글 파일에 image가 지정됐을 때만). 없으면 null → 사이트가 실사진(Unsplash)으로 채운다.
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
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, " ")
    .replace(/&hellip;/g, "…")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim();
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}.${String(d.getMonth() + 1).padStart(2, "0")}.${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

// slug로 안정적인 숫자 id(목록 key·중복 제거용).
export function slugId(slug: string): number {
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  return h;
}
