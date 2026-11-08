import Link from "next/link";
import type { ToolMeta } from "@/lib/tools/registry";
import { getPostBySlug, stripHtml, SITE_NAME } from "@/lib/wp";
import AdSlot from "@/components/AdSlot";

// 도구 공통 틀: 제목·대상·면책·근거(규칙 표)·관련 글. 계산/판정 화면(children)은 도구별 클라이언트 컴포넌트.
export default async function ToolShell({
  tool,
  basis,
  limits,
  intro,
  faq,
  children,
}: {
  tool: ToolMeta;
  basis: { rule: string; value: string; source: string; url?: string }[];
  limits: string[];
  intro?: string[];
  faq?: { q: string; a: string }[];
  children: React.ReactNode;
}) {
  const related = (await Promise.all(tool.related.map((s) => getPostBySlug(s)))).filter(
    (p): p is NonNullable<typeof p> => Boolean(p),
  );
  return (
    <div className="container article tool-page">
      <Link href="/tools" className="a-cat">← 세금 계산기</Link>
      <h1>{tool.title}</h1>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span><span>{tool.checked} 기준 규칙</span>
      </div>
      <p className="tool-sub">{tool.description} · <b>대상</b> {tool.audience}</p>

      {intro && intro.length > 0 ? (
        <section className="tool-lead article-body">
          {intro.map((p, i) => <p key={i}>{p}</p>)}
        </section>
      ) : null}

      <section className="tool-panel" aria-label="계산기">
        <div className="tool-panel-head"><span aria-hidden>🧮</span> 계산해 보기</div>
        <div className="tool-panel-body">{children}</div>
      </section>
      <p className="tool-note-inline">
        ⚠️ 일반 정보 제공용 <b>대략 판정</b>입니다. 개별 사정(다른 소득·공제·특례)에 따라 달라질 수 있으니, 신고·가입 전 국세청(126)·국민건강보험공단·세무 전문가에게 확인하세요.
      </p>

      <AdSlot />

      {faq && faq.length > 0 ? (
        <section className="tool-section article-body">
          <h2>자주 묻는 질문</h2>
          {faq.map((f, i) => (
            <div key={i}>
              <h3>{f.q}</h3>
              <p>{f.a}</p>
            </div>
          ))}
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
        </section>
      ) : null}

      <div className="tool-folds">
      <details className="tool-fold">
        <summary>계산·판정 기준 (출처)</summary>
        <figure className="wp-block-table basis">
          <table>
            <thead><tr><th>규칙</th><th>값</th><th>출처</th></tr></thead>
            <tbody>
              {basis.map((b, i) => (
                <tr key={i}>
                  <td>{b.rule}</td><td>{b.value}</td>
                  <td>{b.url ? <a href={b.url} target="_blank" rel="nofollow noopener">{b.source}</a> : b.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </figure>
      </details>

      <details className="tool-fold">
        <summary>이 도구가 다루지 않는 것</summary>
        <ul>{limits.map((l, i) => <li key={i}>{l}</li>)}</ul>
      </details>
      </div>

      {related.length > 0 ? (
        <section className="tool-section">
          <h2>함께 보면 좋은 글</h2>
          <ul className="tool-related">{related.map((p) => <li key={p.slug}><Link href={`/${p.slug}`}>{stripHtml(p.title.rendered)}</Link></li>)}</ul>
        </section>
      ) : null}

      <div className="byline-foot">
        입력하신 값은 이 기기 안에서만 계산되며 서버로 전송·저장되지 않습니다. 이 도구는 세무·법률·보험 자문이 아니며, 규칙은 {tool.checked} 기준 공개 자료를 바탕으로 합니다.
      </div>
    </div>
  );
}
