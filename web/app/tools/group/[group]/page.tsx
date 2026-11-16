import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { TOOL_GROUPS, toolsInGroup } from "@/lib/tools/registry";
import { GROUP_GUIDES } from "@/lib/tools/guides";
import { getPostBySlug, stripHtml, SITE_URL } from "@/lib/wp";

export const dynamicParams = false;

export function generateStaticParams() {
  return TOOL_GROUPS.map((g) => ({ group: g.key }));
}

export function generateMetadata({ params }: { params: { group: string } }): Metadata {
  const g = TOOL_GROUPS.find((x) => x.key === params.group);
  if (!g) return { title: "세금 계산기" };
  return {
    title: `${g.name} 계산기 — ${g.desc}`,
    description: `${g.name} 관련 세금 계산기 모음. ${g.desc}. 내 상황을 넣으면 세금을 바로 계산합니다.`,
    alternates: { canonical: `/tools/group/${g.key}` },
  };
}

export default async function GroupPage({ params }: { params: { group: string } }) {
  const g = TOOL_GROUPS.find((x) => x.key === params.group);
  if (!g) notFound();
  const tools = toolsInGroup(g.key);
  const guide = GROUP_GUIDES[g.key];
  const posts = guide
    ? (await Promise.all(guide.guides.map((s) => getPostBySlug(s)))).filter(
        (p): p is NonNullable<typeof p> => Boolean(p),
      )
    : [];
  const others = TOOL_GROUPS.filter((x) => x.key !== g.key).map((x) => ({
    ...x,
    count: toolsInGroup(x.key).length,
  }));

  return (
    <div className="container article tool-page">
      <nav className="crumbs" aria-label="위치">
        <Link href="/">홈</Link>
        <span aria-hidden>›</span>
        <Link href="/tools">세금 계산기</Link>
        <span aria-hidden>›</span>
        <span>{g.name}</span>
      </nav>
      <h1>{g.name} 계산기</h1>
      <p className="tool-sub">{g.desc}. 내 상황을 넣으면 세금·유불리를 바로 계산합니다.</p>

      {guide ? (
        <section className="tool-lead article-body">
          {guide.lead.map((p, i) => <p key={i}>{p}</p>)}
        </section>
      ) : null}

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

      {guide ? (
        <section className="tool-guide article-body">
          <h2>이 순서로 확인하세요</h2>
          <ol>
            {guide.steps.map((s, i) => <li key={i}>{s}</li>)}
          </ol>

          <h2>계산 예시</h2>
          <p className="tool-example-lead">{guide.example.title}</p>
          <figure className="wp-block-table">
            <table>
              <thead>
                <tr><th>항목</th><th>금액</th></tr>
              </thead>
              <tbody>
                {guide.example.rows.map(([a, b], i) => (
                  <tr key={i}><td>{a}</td><td>{b}</td></tr>
                ))}
              </tbody>
            </table>
          </figure>
          {guide.example.note ? <p className="tool-example-note">{guide.example.note}</p> : null}
        </section>
      ) : null}

      {posts.length > 0 ? (
        <section className="tool-section">
          <h2>관련 가이드</h2>
          <ul className="tool-links">
            {posts.map((p) => (
              <li key={p.slug}>
                <Link href={`/${p.slug}`}>{stripHtml(p.title.rendered)}</Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {guide && guide.faq.length > 0 ? (
        <section className="tool-section article-body">
          <h2>자주 묻는 질문</h2>
          {guide.faq.map((f, i) => (
            <div key={i}>
              <h3>{f.q}</h3>
              <p>{f.a}</p>
            </div>
          ))}
        </section>
      ) : null}

      <section className="tool-section">
        <h2>다른 분류의 계산기</h2>
        <ul className="tool-links">
          {others.map((o) => (
            <li key={o.key}>
              <Link href={`/tools/group/${o.key}`}>{o.name} 계산기</Link>
              <small>{o.desc} · {o.count}개</small>
            </li>
          ))}
        </ul>
      </section>

      <p className="tool-note-inline" style={{ marginTop: 20 }}>
        <Link href="/tools">← 세금 계산기 전체 보기</Link>
      </p>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(
            [
              {
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                itemListElement: [
                  { "@type": "ListItem", position: 1, name: "홈", item: SITE_URL },
                  { "@type": "ListItem", position: 2, name: "세금 계산기", item: `${SITE_URL}/tools` },
                  { "@type": "ListItem", position: 3, name: g.name, item: `${SITE_URL}/tools/group/${g.key}` },
                ],
              },
              ...(guide && guide.faq.length > 0
                ? [
                    {
                      "@context": "https://schema.org",
                      "@type": "FAQPage",
                      mainEntity: guide.faq.map((f) => ({
                        "@type": "Question",
                        name: f.q,
                        acceptedAnswer: { "@type": "Answer", text: f.a },
                      })),
                    },
                  ]
                : []),
            ],
          ),
        }}
      />
    </div>
  );
}
