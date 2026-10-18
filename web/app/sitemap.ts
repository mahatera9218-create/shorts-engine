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

  const catUrls = CATEGORY_ORDER.map((c) => ({
    url: `${SITE_URL}/category/${c.slug}`,
    lastModified: posts.find((p) => postCategory(p)?.slug === c.slug)?.modified,
  }));
  const toolUrls = TOOLS.some((t) => t.published)
    ? [{ url: `${SITE_URL}/tools` }, ...TOOLS.filter((t) => t.published).map((t) => ({ url: `${SITE_URL}/tools/${t.slug}`, lastModified: t.checked }))]
    : [];
  return [{ url: SITE_URL }, ...catUrls, ...toolUrls, ...postUrls, ...pageUrls];
}
