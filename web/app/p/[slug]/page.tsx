import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getPageBySlug,
  getAllPageSlugs,
  stripHtml,
} from "@/lib/wp";

export const revalidate = 3600;
export const dynamicParams = true;

export async function generateStaticParams() {
  const slugs = await getAllPageSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const page = await getPageBySlug(decodeURIComponent(params.slug));
  if (!page) return { title: "페이지를 찾을 수 없음" };
  return {
    title: stripHtml(page.title.rendered),
    alternates: { canonical: `/p/${page.slug}` },
  };
}

export default async function WpPage({
  params,
}: {
  params: { slug: string };
}) {
  const page = await getPageBySlug(decodeURIComponent(params.slug));
  if (!page) notFound();

  return (
    <article className="container article">
      <h1 dangerouslySetInnerHTML={{ __html: page.title.rendered }} />
      <div
        className="article-body"
        dangerouslySetInnerHTML={{ __html: page.content.rendered }}
      />
    </article>
  );
}
