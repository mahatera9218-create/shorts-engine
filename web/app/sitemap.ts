import type { MetadataRoute } from "next";
import { getPosts, getAllPageSlugs, SITE_URL } from "@/lib/wp";

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

  return [{ url: SITE_URL }, ...postUrls, ...pageUrls];
}
