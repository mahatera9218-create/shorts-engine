import Link from "next/link";
import { getPosts, CATEGORY_ORDER } from "@/lib/wp";
import PostCard from "@/components/PostCard";

import type { Metadata } from "next";
import { SITE_NAME, SITE_URL, SITE_DESC, EDITOR_NAME } from "@/lib/wp";

// 홈도 빌드 때 미리 만든다(완전 정적). 새 글은 배포 때 반영.
export const dynamic = "force-static";

export const metadata: Metadata = { alternates: { canonical: "/" } };

export default async function Home() {
  const posts = await getPosts(24);

  return (
    <div className="container">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify([
            { "@context": "https://schema.org", "@type": "WebSite", name: SITE_NAME, url: SITE_URL, description: SITE_DESC, inLanguage: "ko-KR" },
            { "@context": "https://schema.org", "@type": "Organization", name: SITE_NAME, url: SITE_URL, logo: `${SITE_URL}/logo.webp`, founder: { "@type": "Person", name: EDITOR_NAME } },
          ]),
        }}
      />
      <section className="intro">
        <div>
          <h1>Yield Briefing</h1>
          <p>
            {process.env.NEXT_PUBLIC_INTRO_DESC ||
              "재테크·부동산·세금·연금을 공식 자료로 정확하게."}
          </p>
        </div>
      </section>

      <div className="chips">
        {CATEGORY_ORDER.map((c) => (
          <Link key={c.slug} href={`/category/${c.slug}`}>
            {c.name}
          </Link>
        ))}
      </div>

      <Link href="/tools" className="tool-strip">
        <b>🧮 내 경우 바로 판정</b>
        <span>월세 분리과세 · 셀러 간이과세 · 피부양자 자격 · 사업자등록</span>
      </Link>

      {posts.length === 0 ? (
        <p className="empty">
          아직 발행된 글이 없습니다. 워드프레스에서 글을 공개하면 여기에 나타납니다.
        </p>
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
