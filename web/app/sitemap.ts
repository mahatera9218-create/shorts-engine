import type { MetadataRoute } from "next";
import { getPosts, getAllPageSlugs, postCategory, SITE_URL, CATEGORY_ORDER } from "@/lib/wp";
import { TOOLS } from "@/lib/tools/registry";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await getPosts(100);
  const pageSlugs = await getAllPageSlugs();

  const postUrls = posts.map((p) => ({
    url: `${SITE_URL}/${p.slug}`,
    lastModified: p.modified,
  }));
  const pageUrls = pageSlugs.map((slug) => ({
    url: `${SITE_URL}/p/${slug}`,
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
  const toolUrls = TOOLS.some((t) => t.published)
    ? [{ url: `${SITE_URL}/tools` }, ...TOOLS.filter((t) => t.published).map((t) => ({ url: `${SITE_URL}/tools/${t.slug}`, lastModified: t.checked }))]
    : [];
  return [{ url: SITE_URL }, ...catUrls, ...toolUrls, ...postUrls, ...pageUrls];
}
