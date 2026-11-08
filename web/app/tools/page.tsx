import type { Metadata } from "next";
import Link from "next/link";
import { TOOLS, TOOL_GROUPS, toolsInGroup } from "@/lib/tools/registry";
import { SITE_URL } from "@/lib/wp";

export const metadata: Metadata = {
  title: "세금 계산기 — 부동산·상속증여·소득·건강보험",
  description: "집·상속·소득·건강보험 세금을 주제별로 모은 계산기. 분류를 고르면 해당 계산기로 들어갑니다.",
  alternates: { canonical: "/tools" },
  robots: TOOLS.some((t) => t.published) ? { index: true, follow: true } : { index: false, follow: false },
};

export default function ToolsHub() {
  const groups = TOOL_GROUPS.map((g) => ({ ...g, tools: toolsInGroup(g.key) })).filter((g) => g.tools.length > 0);
  return (
    <div className="container article tool-page">
      <nav className="crumbs" aria-label="위치">
        <Link href="/">홈</Link>
        <span aria-hidden>›</span>
        <span>세금 계산기</span>
      </nav>
      <h1>세금 계산기</h1>
      <p className="tool-sub">분류를 고르면 해당 계산기로 들어갑니다. 내 상황을 넣으면 세금·유불리를 바로 계산합니다.</p>

      <div className="tool-grid">
        {groups.map((g) => (
          <Link key={g.key} href={`/tools/group/${g.key}`} className="tool-card cat-card">
            <span className="tool-card-name">{g.name}</span>
            <span className="tool-card-aud">{g.desc}</span>
            <span className="tool-card-desc">{g.tools.map((t) => t.short.replace(/\s*(계산|비교|판정).*$/, "")).join(" · ")}</span>
            <span className="tool-card-go">{g.tools.length}개 계산기 →</span>
          </Link>
        ))}
      </div>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "ItemList",
            itemListElement: groups.map((g, i) => ({
              "@type": "ListItem",
              position: i + 1,
              name: `${g.name} 계산기`,
              url: `${SITE_URL}/tools/group/${g.key}`,
            })),
          }),
        }}
      />
    </div>
  );
}
