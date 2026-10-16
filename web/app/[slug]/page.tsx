import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getPostBySlug,
  getAllPostSlugs,
  getRelated,
  featuredImage,
  postCategory,
  stripHtml,
  formatDate,
  SITE_NAME,
  SITE_URL,
} from "@/lib/wp";
import { stockPhoto } from "@/lib/photos";
import PostCard from "@/components/PostCard";
import Thumb from "@/components/Thumb";

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
  // 대표 이미지: 주제에 맞는 실사진(Unsplash) 우선, 없으면 워드프레스 대표 이미지.
  const cat = postCategory(post);
  const stock = await stockPhoto(cat?.slug, post.slug);
  const hero = stock ?? featuredImage(post)?.url ?? null;
  return {
    title,
    description: desc,
    alternates: { canonical: `/${post.slug}` },
    openGraph: {
      type: "article",
      title,
      description: desc,
      images: hero ? [{ url: hero }] : undefined,
    },
    twitter: {
      card: hero ? "summary_large_image" : "summary",
      title,
      description: desc,
      images: hero ? [hero] : undefined,
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
  const cat = postCategory(post);
  const feat = featuredImage(post);
  const stock = await stockPhoto(cat?.slug, post.slug);
  const hero = stock ?? feat?.url ?? null;
  const related = await getRelated(post, 3);

  return (
    <article className="container article">
      {cat ? (
        <Link href={`/category/${cat.slug}`} className="a-cat">
          {cat.name}
        </Link>
      ) : null}
      <h1 dangerouslySetInnerHTML={{ __html: post.title.rendered }} />
      <div className="byline">
        <Link href="/p/about">{SITE_NAME}</Link>
        <span>·</span>
        <span>{formatDate(post.date)}</span>
      </div>

      {stock || feat ? (
        <div className="hero">
          <Thumb src={stock} fallback={feat?.url ?? null} alt={title} />
        </div>
      ) : null}

      <div
        className="article-body"
        dangerouslySetInnerHTML={{ __html: post.content.rendered }}
      />

      <div className="byline-foot">
        글쓴이 <Link href="/p/about">{SITE_NAME}</Link> · 재테크·부동산·세금 정보를 공식 자료로 정리합니다. 이 글은 일반 정보이며 개별 사안은 국세청(126)·세무
        전문가 확인을 권합니다.
      </div>

      {related.length > 0 ? (
        <section className="related">
          <h2>함께 보면 좋은 글</h2>
          <div className="feed">
            {related.map((p) => (
              <PostCard key={p.id} post={p} />
            ))}
          </div>
        </section>
      ) : null}

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "Article",
            headline: title,
            image: hero ? [hero] : undefined,
            author: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
            publisher: { "@type": "Organization", name: SITE_NAME, url: SITE_URL },
            datePublished: post.date,
            dateModified: post.modified,
            mainEntityOfPage: `${SITE_URL}/${post.slug}`,
          }),
        }}
      />
    </article>
  );
}
