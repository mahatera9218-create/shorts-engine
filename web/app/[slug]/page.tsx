import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getPostBySlug,
  getAllPostSlugs,
  featuredImage,
  stripHtml,
  formatDate,
} from "@/lib/wp";

export const revalidate = 600;
export const dynamicParams = true;

export async function generateStaticParams() {
  const slugs = await getAllPostSlugs();
  return slugs.map((slug) => ({ slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const post = await getPostBySlug(decodeURIComponent(params.slug));
  if (!post) return { title: "글을 찾을 수 없음" };
  const title = stripHtml(post.title.rendered);
  const desc = stripHtml(post.excerpt.rendered).slice(0, 150);
  const img = featuredImage(post);
  return {
    title,
    description: desc,
    alternates: { canonical: `/${post.slug}` },
    openGraph: {
      type: "article",
      title,
      description: desc,
      images: img ? [{ url: img.url }] : undefined,
    },
  };
}

export default async function PostPage({
  params,
}: {
  params: { slug: string };
}) {
  const post = await getPostBySlug(decodeURIComponent(params.slug));
  if (!post) notFound();

  const title = stripHtml(post.title.rendered);

  return (
    <article className="container article">
      <h1 dangerouslySetInnerHTML={{ __html: post.title.rendered }} />
      <div className="meta">{formatDate(post.date)}</div>
      <div
        className="article-body"
        dangerouslySetInnerHTML={{ __html: post.content.rendered }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Article",
            headline: title,
            datePublished: post.date,
            dateModified: post.modified,
          }),
        }}
      />
    </article>
  );
}
