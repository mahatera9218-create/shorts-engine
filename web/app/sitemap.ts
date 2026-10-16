import type { MetadataRoute } from "next";
import { getPosts, getAllPageSlugs, postCategory, SITE_URL, CATEGORY_ORDER } from "@/lib/wp";

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
  return [{ url: SITE_URL }, ...catUrls, ...postUrls, ...pageUrls];
}
