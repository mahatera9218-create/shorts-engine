import type { MetadataRoute } from "next";
import { getPosts, getAllPages, postCategory, SITE_URL, CATEGORY_ORDER } from "@/lib/wp";
import { TOOLS, TOOL_GROUPS, toolsInGroup } from "@/lib/tools/registry";

export const revalidate = 3600;

// 원래 문자열 그대로(형식 유지) 가장 최근 날짜를 고른다. 시간대 표기가 섞여도 정확하도록 시각으로 비교.
function newest(dates: Array<string | undefined>): string | undefined {
  const parsed = dates
    .filter((d): d is string => !!d)
    .map((d) => ({ d, t: Date.parse(d) || 0 }));
  if (parsed.length === 0) return undefined;
  parsed.sort((a, b) => b.t - a.t);
  return parsed[0].d;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getPosts(100);
  const pages = await getAllPages();
  const publishedTools = TOOLS.filter((t) => t.published);

  const postUrls = posts.map((p) => ({
    url: `${SITE_URL}/${p.slug}`,
    lastModified: p.modified,
  }));
  // 고정 페이지: frontmatter에 적어 둔 마지막 수정일. 없으면 lastmod 생략.
  const pageUrls = pages.map((p) => ({
    url: `${SITE_URL}/p/${p.slug}`,
    lastModified: p.modified,
  }));

  // 글 3개 이상인 카테고리만 사이트맵에 넣는다(얇은 카테고리는 noindex라 제외).
  const catUrls = CATEGORY_ORDER.map((c) => ({
    slug: c.slug,
    count: posts.filter((p) => postCategory(p)?.slug === c.slug).length,
  }))
    .filter((c) => c.count >= 3)
    .map((c) => ({
      url: `${SITE_URL}/category/${c.slug}`,
      lastModified: posts.find((p) => postCategory(p)?.slug === c.slug)?.modified,
    }));
  // 계산기 그룹 페이지: 그 그룹에서 가장 최근에 규칙을 확인한 계산기 날짜.
  const groupUrls = TOOL_GROUPS.filter((g) => toolsInGroup(g.key).length > 0).map((g) => ({
    url: `${SITE_URL}/tools/group/${g.key}`,
    lastModified: newest(
      toolsInGroup(g.key)
        .filter((t) => t.published)
        .map((t) => t.checked),
    ),
  }));
  const toolUrls = publishedTools.length > 0
    ? [
        { url: `${SITE_URL}/tools`, lastModified: newest(publishedTools.map((t) => t.checked)) },
        ...groupUrls,
        ...publishedTools.map((t) => ({ url: `${SITE_URL}/tools/${t.slug}`, lastModified: t.checked })),
      ]
    : [];
  // 홈은 글·계산기 중 가장 최근에 바뀐 날짜.
  const homeUpdated = newest([
    ...posts.map((p) => p.modified),
    ...publishedTools.map((t) => t.checked),
  ]);
  return [{ url: SITE_URL, lastModified: homeUpdated }, ...catUrls, ...toolUrls, ...postUrls, ...pageUrls];
}
