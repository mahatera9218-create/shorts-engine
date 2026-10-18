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
  EDITOR_NAME,
} from "@/lib/wp";
import { stockPhoto, stockPhotos } from "@/lib/photos";
import PostCard from "@/components/PostCard";
import Thumb from "@/components/Thumb";
import { toolsForPost } from "@/lib/tools/registry";
import { sized } from "@/lib/imgsize";

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

// 본문 HTML의 ## 섹션(<h2>) 사이사이에 사진을 끼워 넣는다(장식용, alt 비움).
// 두 번째 섹션부터 한 섹션 걸러 한 장씩, 사진이 떨어질 때까지.
function injectBodyImages(html: string, imgs: string[]): string {
  if (imgs.length === 0) return html;
  const parts = html.split(/(?=<h2)/);
  if (parts.length < 3) return html;
  let k = 0;
  const out: string[] = [];
  for (let i = 0; i < parts.length; i++) {
    if (i >= 2 && (i - 2) % 2 === 0 && k < imgs.length) {
      out.push(
        `<figure class="body-photo"><img src="${sized(imgs[k], 800)}" alt="" loading="lazy" decoding="async" width="800" height="450"/></figure>`,
      );
      k += 1;
    }
    out.push(parts[i]);
  }
  return out.join("");
}

// 본문의 '자주 묻는 질문' 섹션에서 Q/A를 뽑아 FAQ 스키마로 쓴다(구글 Q&A·AI 인용).
function extractFaq(html: string): { q: string; a: string }[] {
  const h = html.indexOf("자주 묻는 질문");
  if (h === -1) return [];
  let seg = html.slice(h);
  const afterH = seg.indexOf("</h2>");
  if (afterH !== -1) seg = seg.slice(afterH + 5);
  const end = seg.search(/<h2[ >]/);
  if (end !== -1) seg = seg.slice(0, end);
  const paras = Array.from(seg.matchAll(/<p>([\s\S]*?)<\/p>/g))
    .map((m) => stripHtml(m[1]).trim())
    .filter(Boolean);
  const out: { q: string; a: string }[] = [];
  let cur: { q: string; a: string } | null = null;
  for (const t of paras) {
    if (/^Q[.\s]/.test(t)) {
      if (cur) out.push(cur);
      cur = { q: t.replace(/^Q[.\s]+/, "").trim(), a: "" };
    } else if (cur) {
      cur.a = cur.a ? `${cur.a} ${t}` : t;
    }
  }
  if (cur) out.push(cur);
  return out.filter((x) => x.q && x.a);
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
  // 본문 중간에 넣을 사진(대표 사진과 겹치지 않게). 섹션 사이사이에 배치.
  const bodyPhotos = await stockPhotos(cat?.slug, `${post.slug}-body`, 3, stock);
  const bodyHtml = injectBodyImages(post.content.rendered, bodyPhotos);
  const faq = extractFaq(post.content.rendered);
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
        {post.modified && post.modified.slice(0, 10) !== post.date.slice(0, 10) ? (
          <>
            <span>·</span>
            <span>마지막 업데이트 {formatDate(post.modified)}</span>
          </>
        ) : null}
      </div>

      {stock || feat ? (
        <div className="hero">
          <Thumb src={stock} fallback={feat?.url ?? null} alt={title} w={960} priority />
        </div>
      ) : null}

      <div
        className="article-body"
        dangerouslySetInnerHTML={{ __html: bodyHtml }}
      />

      {toolsForPost(post.slug).length > 0 ? (
        <section className="tool-callout">
          <b>내 경우는 어떨까? 바로 판정해 보기</b>
          <ul>
            {toolsForPost(post.slug).map((t) => (
              <li key={t.slug}><Link href={`/tools/${t.slug}`}>{t.short} →</Link> <small>({t.audience})</small></li>
            ))}
          </ul>
        </section>
      ) : null}

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
            accountablePerson: { "@type": "Person", name: EDITOR_NAME },
            datePublished: post.date,
            dateModified: post.modified,
            mainEntityOfPage: `${SITE_URL}/${post.slug}`,
          }),
        }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            itemListElement: [
              { "@type": "ListItem", position: 1, name: SITE_NAME, item: SITE_URL },
              ...(cat
                ? [{ "@type": "ListItem", position: 2, name: cat.name, item: `${SITE_URL}/category/${cat.slug}` }]
                : []),
              { "@type": "ListItem", position: cat ? 3 : 2, name: title, item: `${SITE_URL}/${post.slug}` },
            ],
          }),
        }}
      />
      {faq.length > 0 ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "FAQPage",
              mainEntity: faq.map((f) => ({
                "@type": "Question",
                name: f.q,
                acceptedAnswer: { "@type": "Answer", text: f.a },
              })),
            }),
          }}
        />
      ) : null}
    </article>
  );
}
