import Link from "next/link";
import type { ToolMeta } from "@/lib/tools/registry";
import { getPostBySlug, stripHtml, SITE_NAME } from "@/lib/wp";
import AdSlot from "@/components/AdSlot";

// 도구 공통 틀: 제목·대상·면책·근거(규칙 표)·관련 글. 계산/판정 화면(children)은 도구별 클라이언트 컴포넌트.
export default async function ToolShell({
  tool,
  basis,
  limits,
  children,
}: {
  tool: ToolMeta;
  basis: { rule: string; value: string; source: string; url?: string }[];
  limits: string[];
  children: React.ReactNode;
}) {
  const related = (await Promise.all(tool.related.map((s) => getPostBySlug(s)))).filter(
    (p): p is NonNullable<typeof p> => Boolean(p),
  );
  return (
    <div className="container article">
      <Link href="/tools" className="a-cat">← 판정·비교 도구</Link>
      <h1>{tool.title}</h1>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span><span>{tool.checked} 기준 규칙</span>
      </div>
      <p className="rank-intro">{tool.description} <b>대상:</b> {tool.audience}.</p>
      <div className="mock-banner">
        ⚠️ 일반 정보 제공용 <b>대략 판정</b>입니다. 개별 사정(다른 소득·공제·특례)에 따라 달라질 수 있으니, 신고·가입 전 국세청(126)·국민건강보험공단·세무 전문가에게 확인하세요.
      </div>

      {children}

      <AdSlot />

      <h2>계산·판정 기준 (출처)</h2>
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

      <h2>이 도구가 다루지 않는 것</h2>
      <ul>{limits.map((l, i) => <li key={i}>{l}</li>)}</ul>

      {related.length > 0 ? (
        <>
          <h2>함께 보면 좋은 글</h2>
          <ul>{related.map((p) => <li key={p.slug}><Link href={`/${p.slug}`}>{stripHtml(p.title.rendered)}</Link></li>)}</ul>
        </>
      ) : null}

      <div className="byline-foot">
        입력하신 값은 이 기기 안에서만 계산되며 서버로 전송·저장되지 않습니다. 이 도구는 세무·법률·보험 자문이 아니며, 규칙은 {tool.checked} 기준 공개 자료를 바탕으로 합니다.
      </div>
    </div>
  );
}
