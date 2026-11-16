import type { Metadata } from "next";
import Link from "next/link";
import { TOOLS, TOOL_GROUPS, toolsInGroup } from "@/lib/tools/registry";
import { GROUP_GUIDES } from "@/lib/tools/guides";
import { getPostBySlug, stripHtml, SITE_URL } from "@/lib/wp";

export const metadata: Metadata = {
  title: "세금 계산기 — 부동산·상속증여·소득·건강보험",
  description:
    "집·상속·소득·건강보험 세금을 주제별로 모은 계산기. 취득세·재산세·양도세·증여세·상속세·부가세·연금 공제까지 내 경우로 바로 계산합니다.",
  alternates: { canonical: "/tools" },
  robots: TOOLS.some((t) => t.published) ? { index: true, follow: true } : { index: false, follow: false },
};

const FAQ: Array<{ q: string; a: string }> = [
  {
    q: "계산 결과를 그대로 신고에 써도 되나요?",
    a: "계산기는 공개된 규칙(소득세법·지방세법·상속세및증여세법 등)으로 만든 '대략 판정'입니다. 특례·감면·가산세·기납부세액처럼 개별 사정에 따라 달라지는 부분은 반영되지 않으므로, 방향과 규모를 잡는 데 쓰고 신고 전에는 국세청(126)이나 세무 전문가 확인을 권합니다.",
  },
  {
    q: "입력한 금액이 서버에 저장되나요?",
    a: "아니요. 계산은 브라우저(내 기기) 안에서만 이뤄지고 입력값은 서버로 보내지 않습니다. 로그인도 필요 없습니다.",
  },
  {
    q: "계산기와 글이 같은 주제인데 무엇부터 봐야 하나요?",
    a: "요건·절차·예외가 궁금하면 글을, 내 숫자로 얼마인지 궁금하면 계산기를 보세요. 글 하단에는 그 글과 이어지는 계산기가, 계산기 하단에는 관련 가이드가 붙어 있어 서로 오갈 수 있습니다.",
  },
  {
    q: "세율과 한도는 어느 시점 기준인가요?",
    a: "계산기마다 '기준 규칙' 날짜를 표시하고 그 시점의 공개 자료를 반영했습니다. 세율·공제 한도·보험료율은 해마다 바뀌므로, 신고·계약 직전에 국세청·공단 고시로 한 번 더 확인하세요.",
  },
];

export default async function ToolsHub() {
  const groups = TOOL_GROUPS.map((g) => ({ ...g, tools: toolsInGroup(g.key) })).filter(
    (g) => g.tools.length > 0,
  );
  const published = TOOLS.filter((t) => t.published);
  // 허브에서 각 분류의 대표 가이드 3편씩 링크한다(글까지 이어지는 내부 링크).
  const guideLinks = await Promise.all(
    TOOL_GROUPS.map(async (g) => ({
      ...g,
      posts: (
        await Promise.all((GROUP_GUIDES[g.key]?.guides ?? []).slice(0, 3).map((s) => getPostBySlug(s)))
      ).filter((p): p is NonNullable<typeof p> => Boolean(p)),
    })),
  );

  return (
    <div className="container article tool-page">
      <nav className="crumbs" aria-label="위치">
        <Link href="/">홈</Link>
        <span aria-hidden>›</span>
        <span>세금 계산기</span>
      </nav>
      <h1>세금 계산기</h1>
      <p className="tool-sub">
        분류를 고르면 해당 계산기로 들어갑니다. 내 상황을 넣으면 세금·유불리를 바로 계산합니다.
      </p>

      <section className="tool-guide article-body">
        <h2>세금은 '얼마'보다 '어떤 상황인가'에서 갈립니다</h2>
        <p>
          같은 1억원이라도 월급인지 사업소득인지, 집을 살 때인지 팔 때인지, 받는 사람이 자녀인지 배우자인지에
          따라 세금이 전혀 달라집니다. 그래서 세금 계산은 금액 하나를 넣는 문제가 아니라, 내 상황에 맞는
          규칙을 찾는 문제입니다.
        </p>
        <p>
          이 사이트의 계산기는 소득세법·지방세법·상속세및증여세법·건강보험법 등 공개된 규칙을 코드로 옮겨
          만들었습니다. 숫자를 넣으면 내 경우의 세금과 유불리를 보여 주고, 계산에 쓴 규칙과 다루지 못한 범위도
          함께 밝힙니다. 정확한 신고 금액은 홈택스·위택스에서 확정해야 하지만, 어느 방향으로 얼마가 움직이는지
          먼저 잡아 두면 그만큼 판단이 빨라집니다.
        </p>

        <h2>이 순서로 확인하세요</h2>
        <ul>
          <li>
            <b>1. 상황 분류</b> — 집·상속증여·소득사업·건강보험연금 중 지금 내 상황이 어디인지 고릅니다.
            아래 분류 카드에서 해당 묶음으로 들어갑니다.
          </li>
          <li>
            <b>2. 계산</b> — 각 계산기에 금액·기간·관계를 넣습니다. 대부분은 30초 안에 결과가 나옵니다.
          </li>
          <li>
            <b>3. 요건 확인</b> — 결과 아래 '결과를 실제로 쓸 때 확인할 점'과 '이 도구가 다루지 않는 것'을
            읽고, 요건·예외가 걸리는지 확인합니다.
          </li>
          <li>
            <b>4. 글에서 배경 확인</b> — 왜 그렇게 계산되는지, 절차와 신고 기한은 어떻게 되는지는 각 계산기
            하단의 관련 가이드에서 이어 볼 수 있습니다.
          </li>
        </ul>
      </section>

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

      {guidesWithPosts(guideLinks)}

      <section className="tool-guide article-body">
        <h2>계산기 전체 목록</h2>
        <p>
          지금 열려 있는 계산기 {published.length}개입니다. 분류와 상관없이 이름으로 찾을 때는 아래 목록을
          보세요.
        </p>
      </section>

      {groups.map((g) => (
        <section key={g.key} className="tool-group">
          <div className="tool-group-head">
            <h2>{g.name}</h2>
            <span>{g.desc}</span>
          </div>
          <ul className="tool-links">
            {g.tools.map((t) => (
              <li key={t.slug}>
                <Link href={`/tools/${t.slug}`}>{t.title}</Link>
                <small>{t.description}</small>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <section className="tool-section article-body">
        <h2>자주 묻는 질문</h2>
        {FAQ.map((f, i) => (
          <div key={i}>
            <h3>{f.q}</h3>
            <p>{f.a}</p>
          </div>
        ))}
      </section>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify([
            {
              "@context": "https://schema.org",
              "@type": "ItemList",
              itemListElement: groups.map((g, i) => ({
                "@type": "ListItem",
                position: i + 1,
                name: `${g.name} 계산기`,
                url: `${SITE_URL}/tools/group/${g.key}`,
              })),
            },
            {
              "@context": "https://schema.org",
              "@type": "FAQPage",
              mainEntity: FAQ.map((f) => ({
                "@type": "Question",
                name: f.q,
                acceptedAnswer: { "@type": "Answer", text: f.a },
              })),
            },
          ]),
        }}
      />
    </div>
  );
}

type GuideGroup = {
  key: string;
  name: string;
  posts: Array<{ slug: string; title: { rendered: string } }>;
};

function guidesWithPosts(guideLinks: GuideGroup[]) {
  const nonEmpty = guideLinks.filter((g) => g.posts.length > 0);
  if (nonEmpty.length === 0) return null;
  return (
    <section className="tool-section">
      <h2 className="feed-head">분류별 가이드</h2>
      {nonEmpty.map((g) => (
        <div key={g.key} className="tool-group">
          <div className="tool-group-head">
            <h2>{g.name}</h2>
            <span>
              <Link href={`/tools/group/${g.key}`}>계산기 {toolsInGroup(g.key).length}개 →</Link>
            </span>
          </div>
          <ul className="tool-links">
            {g.posts.map((p) => (
              <li key={p.slug}>
                <Link href={`/${p.slug}`}>{stripHtml(p.title.rendered)}</Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
