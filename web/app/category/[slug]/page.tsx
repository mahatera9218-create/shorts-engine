import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getPostsByCategorySlug,
  CATEGORY_ORDER,
  SITE_NAME,
} from "@/lib/wp";
import PostCard from "@/components/PostCard";

// 글이 모두 저장소 파일에 있으므로 빌드 때 전부 미리 만든다(완전 정적).
// 서버리스 렌더가 없어 5xx 여지 0. 없는 주소는 정적 404. 새 글은 배포 때 반영.
export const dynamic = "force-static";
export const dynamicParams = false;

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
  if (!known) notFound();
  const name = known.name;
  const posts = await getPostsByCategorySlug(params.slug, 30);

  return (
    <div className="container">
      <section className="intro">
        <div>
          <h1 style={{ margin: 0 }}>{name}</h1>
          <p style={{ margin: "4px 0 0", color: "var(--sub)" }}>
            {name} 관련 글 모음
          </p>
        </div>
      </section>
      {posts.length === 0 ? (
        <p className="empty">이 카테고리에는 아직 글이 없습니다.</p>
      ) : (
        <div className="feed">
          {posts.map((post, i) => (
            <PostCard key={post.id} post={post} priority={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}
