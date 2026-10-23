import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getPageBySlug,
  getAllPageSlugs,
  stripHtml,
} from "@/lib/wp";

// 고정 페이지도 빌드 때 전부 미리 만든다(완전 정적). 서버리스 렌더 없음 → 5xx 여지 0.
export const dynamic = "force-static";
export const dynamicParams = false;

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
