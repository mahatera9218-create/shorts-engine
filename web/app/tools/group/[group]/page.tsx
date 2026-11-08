import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { TOOL_GROUPS, toolsInGroup } from "@/lib/tools/registry";
import { SITE_URL } from "@/lib/wp";

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

export default function GroupPage({ params }: { params: { group: string } }) {
  const g = TOOL_GROUPS.find((x) => x.key === params.group);
  if (!g) notFound();
  const tools = toolsInGroup(g.key);

  return (
    <div className="container article tool-page">
      <nav className="crumbs" aria-label="위치">
        <Link href="/">홈</Link>
        <span aria-hidden>›</span>
        <Link href="/tools">세금 계산기</Link>
      </nav>
      <h1>{g.name} 계산기</h1>
      <p className="tool-sub">{g.desc}. 내 상황을 넣으면 세금·유불리를 바로 계산합니다.</p>

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

      <p className="tool-note-inline" style={{ marginTop: 20 }}>
        <Link href="/tools">← 다른 분류의 세금 계산기 보기</Link>
      </p>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            itemListElement: [
              { "@type": "ListItem", position: 1, name: "홈", item: SITE_URL },
              { "@type": "ListItem", position: 2, name: "세금 계산기", item: `${SITE_URL}/tools` },
              { "@type": "ListItem", position: 3, name: g.name, item: `${SITE_URL}/tools/group/${g.key}` },
            ],
          }),
        }}
      />
    </div>
  );
}
