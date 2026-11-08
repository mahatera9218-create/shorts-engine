import type { Metadata } from "next";
import Link from "next/link";
import { TOOLS, TOOL_GROUPS, toolsInGroup } from "@/lib/tools/registry";
import { SITE_URL } from "@/lib/wp";

export const metadata: Metadata = {
  title: "세금 계산기 — 부동산·상속증여·소득·건강보험",
  description: "집·상속·소득·건강보험 세금을 주제별로 모은 계산기. 내 상황을 넣으면 세금·유불리를 바로 계산합니다.",
  alternates: { canonical: "/tools" },
  robots: TOOLS.some((t) => t.published) ? { index: true, follow: true } : { index: false, follow: false },
};

export default function ToolsHub() {
  const groups = TOOL_GROUPS.map((g) => ({ ...g, tools: toolsInGroup(g.key) })).filter((g) => g.tools.length > 0);
  return (
    <div className="container article tool-page">
      <h1>세금 계산기</h1>
      <p className="tool-sub">주제별로 골라, 내 상황을 넣으면 세금·유불리를 바로 계산합니다. 입력값은 기기 안에서만 계산됩니다.</p>

      <nav className="tool-toc" aria-label="분류">
        {groups.map((g) => <a key={g.key} href={`#${g.key}`}>{g.name}</a>)}
      </nav>

      {groups.map((g) => (
        <section key={g.key} id={g.key} className="tool-group">
          <div className="tool-group-head">
            <h2>{g.name}</h2>
            <span>{g.desc}</span>
          </div>
          <div className="tool-grid">
            {g.tools.map((t) => (
              <Link key={t.slug} href={`/tools/${t.slug}`} className="tool-card">
                <span className="tool-card-name">{t.short}</span>
                <span className="tool-card-aud">{t.audience}</span>
                <span className="tool-card-desc">{t.description}</span>
                <span className="tool-card-go">내 경우 계산 →</span>
              </Link>
            ))}
          </div>
        </section>
      ))}

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "ItemList",
            itemListElement: TOOLS.filter((t) => t.published).map((t, i) => ({
              "@type": "ListItem",
              position: i + 1,
              name: t.short,
              url: `${SITE_URL}/tools/${t.slug}`,
            })),
          }),
        }}
      />
    </div>
  );
}
