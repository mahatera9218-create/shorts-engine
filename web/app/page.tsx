import Link from "next/link";
import { getPosts, CATEGORY_ORDER } from "@/lib/wp";
import { TOOLS } from "@/lib/tools/registry";
import PostCard from "@/components/PostCard";

import type { Metadata } from "next";
import { SITE_NAME, SITE_URL, SITE_DESC, EDITOR_NAME } from "@/lib/wp";

// 홈도 빌드 때 미리 만든다(완전 정적). 새 글은 배포 때 반영.
export const dynamic = "force-static";

export const metadata: Metadata = { alternates: { canonical: "/" } };

export default async function Home() {
  const posts = await getPosts(18);
  const tools = TOOLS.filter((t) => t.published);

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
          <h1>세금·연금, 내 경우 바로 계산</h1>
          <p>
            {process.env.NEXT_PUBLIC_INTRO_DESC ||
              "숫자만 넣으면 내 상황에 맞는 답이 나옵니다. 계산 과정은 공식 자료 기준, 입력값은 기기 안에서만."}
          </p>
        </div>
      </section>

      {/* 계산기·판정 도구를 사이트 간판으로 전면 배치(2026-11-02). 글보다 위. */}
      {tools.length > 0 ? (
        <section className="tools-home" aria-label="세금 계산기·판정 도구">
          <div className="tools-home-head">
            <h2>🧮 세금 계산기·판정 도구</h2>
            <Link href="/tools" className="tools-home-all">전체 보기 →</Link>
          </div>
          <div className="tool-grid">
            {tools.map((t) => (
              <Link key={t.slug} href={`/tools/${t.slug}`} className="tool-card">
                <span className="tool-card-name">{t.short}</span>
                <span className="tool-card-aud">{t.audience}</span>
                <span className="tool-card-desc">{t.description}</span>
                <span className="tool-card-go">내 경우 계산 →</span>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      <div className="chips">
        {CATEGORY_ORDER.map((c) => (
          <Link key={c.slug} href={`/category/${c.slug}`}>
            {c.name}
          </Link>
        ))}
      </div>

      {posts.length > 0 ? (
        <section aria-label="정보 글">
          <h2 className="feed-head">자세히 알아보기</h2>
          <div className="feed">
            {posts.map((post, i) => (
              <PostCard key={post.id} post={post} priority={i === 0} />
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
