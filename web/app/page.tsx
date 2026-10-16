import Link from "next/link";
import { getPosts, CATEGORY_ORDER } from "@/lib/wp";
import PostCard from "@/components/PostCard";

import type { Metadata } from "next";
import { SITE_NAME, SITE_URL, SITE_DESC } from "@/lib/wp";

export const revalidate = 600;

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
            { "@context": "https://schema.org", "@type": "Organization", name: SITE_NAME, url: SITE_URL, logo: `${SITE_URL}/logo.webp` },
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
