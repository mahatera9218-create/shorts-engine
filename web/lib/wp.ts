// 글·페이지를 저장소 안의 마크다운(미리 HTML로 변환됨) 파일에서 읽는다.
// 워드프레스를 쓰지 않는다(가비아 방화벽 문제 제거). 발행기가 content/posts·content/pages에
// 파일을 쓰고 커밋하면, 배포 때 이 모듈이 읽어 사이트에 반영한다. 서버 전용(fs 사용).
import fs from "node:fs";
import path from "node:path";

import {
  CATEGORY_ORDER,
  categoryName,
  postCategory,
  slugId,
  type WpCategory,
  type WpPost,
} from "./site";

// 상수·타입·순수 헬퍼는 그대로 다시 내보낸다(기존 import 경로 유지).
export * from "./site";

const POSTS_DIR = path.join(process.cwd(), "content", "posts");
const PAGES_DIR = path.join(process.cwd(), "content", "pages");

interface Parsed {
  data: Record<string, string>;
  body: string;
}

function parseFrontmatter(raw: string): Parsed {
  const m = raw.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!m) return { data: {}, body: raw };
  const data: Record<string, string> = {};
  for (const line of m[1].split(/\r?\n/)) {
    const i = line.indexOf(":");
    if (i === -1) continue;
    const k = line.slice(0, i).trim();
    let v = line.slice(i + 1).trim();
    if (
      (v.startsWith('"') && v.endsWith('"')) ||
      (v.startsWith("'") && v.endsWith("'"))
    ) {
      v = v.slice(1, -1);
    }
    data[k] = v;
  }
  return { data, body: m[2] };
}

function readDir(dir: string): Parsed[] {
  let names: string[] = [];
  try {
    names = fs.readdirSync(dir);
  } catch {
    return [];
  }
  const out: Parsed[] = [];
  for (const f of names) {
    if (!f.endsWith(".md")) continue;
    try {
      const raw = fs.readFileSync(path.join(dir, f), "utf8");
      const p = parseFrontmatter(raw);
      if (!p.data.slug) p.data.slug = f.replace(/\.md$/, "");
      out.push(p);
    } catch {
      /* 깨진 파일은 건너뛴다 */
    }
  }
  return out;
}

function toPost(p: Parsed): WpPost {
  const d = p.data;
  const slug = d.slug || "";
  const catSlug = d.category || "";
  const date = d.date || new Date().toISOString();
  const media = d.image
    ? [{ source_url: d.image, alt_text: d.title || slug }]
    : undefined;
  return {
    id: slugId(slug),
    slug,
    date,
    modified: d.modified || date,
    link: `/${slug}`,
    title: { rendered: d.title || slug },
    excerpt: { rendered: d.excerpt || "" },
    content: { rendered: p.body.trim() },
    _embedded: {
      ...(media ? { "wp:featuredmedia": media } : {}),
      ...(catSlug
        ? {
            "wp:term": [
              [
                {
                  id: slugId(catSlug),
                  name: categoryName(catSlug),
                  slug: catSlug,
                  taxonomy: "category",
                },
              ],
            ],
          }
        : {}),
    },
  };
}

let _postCache: WpPost[] | null = null;
function loadPosts(): WpPost[] {
  if (_postCache) return _postCache;
  const posts = readDir(POSTS_DIR)
    .map(toPost)
    .filter((p) => p.slug);
  posts.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));
  _postCache = posts;
  return posts;
}

export async function getPosts(perPage = 20): Promise<WpPost[]> {
  return loadPosts().slice(0, perPage);
}

export async function getPostBySlug(slug: string): Promise<WpPost | null> {
  return loadPosts().find((p) => p.slug === slug) ?? null;
}

export async function getAllPostSlugs(): Promise<string[]> {
  return loadPosts().map((p) => p.slug);
}

export async function getPostsByCategorySlug(
  slug: string,
  perPage = 30,
): Promise<WpPost[]> {
  return loadPosts()
    .filter((p) => postCategory(p)?.slug === slug)
    .slice(0, perPage);
}

export async function getCategoryBySlug(
  slug: string,
): Promise<WpCategory | null> {
  const known = CATEGORY_ORDER.find((c) => c.slug === slug);
  const count = loadPosts().filter((p) => postCategory(p)?.slug === slug).length;
  if (!known && count === 0) return null;
  return {
    id: slugId(slug),
    name: known?.name ?? slug,
    slug,
    count,
  };
}

export async function getCategories(): Promise<WpCategory[]> {
  const posts = loadPosts();
  return CATEGORY_ORDER.map((c) => ({
    id: slugId(c.slug),
    name: c.name,
    slug: c.slug,
    count: posts.filter((p) => postCategory(p)?.slug === c.slug).length,
  })).filter((c) => c.count > 0);
}

// 관련 글: 같은 카테고리 우선, 모자라면 최신에서 채운다(현재 글 제외).
export async function getRelated(post: WpPost, n = 3): Promise<WpPost[]> {
  const out: WpPost[] = [];
  const seen = new Set<number>([post.id]);
  const catSlug = postCategory(post)?.slug;
  const push = (list: WpPost[]) => {
    for (const p of list) {
      if (out.length >= n) break;
      if (!seen.has(p.id)) {
        out.push(p);
        seen.add(p.id);
      }
    }
  };
  if (catSlug) push(await getPostsByCategorySlug(catSlug, n + 1));
  if (out.length < n) push(await getPosts(n + 4));
  return out.slice(0, n);
}

// ---- 고정 페이지(개인정보·약관 등) ----

let _pageCache: WpPost[] | null = null;
function loadPages(): WpPost[] {
  if (_pageCache) return _pageCache;
  _pageCache = readDir(PAGES_DIR)
    .map(toPost)
    .filter((p) => p.slug);
  return _pageCache;
}

export async function getPageBySlug(slug: string): Promise<WpPost | null> {
  return loadPages().find((p) => p.slug === slug) ?? null;
}

export async function getAllPageSlugs(): Promise<string[]> {
  return loadPages().map((p) => p.slug);
}
