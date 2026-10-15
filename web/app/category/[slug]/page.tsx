import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getCategoryBySlug,
  getPostsByCategory,
  CATEGORY_ORDER,
  SITE_NAME,
} from "@/lib/wp";
import PostCard from "@/components/PostCard";

export const revalidate = 600;
export const dynamicParams = true;

export function generateStaticParams() {
  return CATEGORY_ORDER.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const known = CATEGORY_ORDER.find((c) => c.slug === params.slug);
  const name = known?.name ?? params.slug;
  return {
    title: `${name} 글 모음`,
    description: `${SITE_NAME}의 ${name} 관련 글 모음.`,
    alternates: { canonical: `/category/${params.slug}` },
  };
}

export default async function CategoryPage({
  params,
}: {
  params: { slug: string };
}) {
  const known = CATEGORY_ORDER.find((c) => c.slug === params.slug);
  const cat = await getCategoryBySlug(params.slug);
  if (!cat && !known) notFound();
  const name = cat?.name ?? known?.name ?? params.slug;
  const posts = cat ? await getPostsByCategory(cat.id, 30) : [];

  return (
    <div className="container">
      <section className="hero">
        <div className="post-card-cat" style={{ marginBottom: 8 }}>
          카테고리
        </div>
        <h1>{name}</h1>
      </section>
      {posts.length === 0 ? (
        <p style={{ color: "var(--muted)", padding: "40px 0 80px" }}>
          이 카테고리에는 아직 글이 없습니다.
        </p>
      ) : (
        <div className="post-grid">
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </div>
      )}
    </div>
  );
}
