import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { TOOLS, getTool } from "@/lib/tools/registry";

export const dynamicParams = false;

export function generateStaticParams() {
  return TOOLS.map((t) => ({ slug: t.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const t = getTool(params.slug);
  if (!t) return { title: "도구" };
  return {
    title: t.title,
    description: t.description,
    robots: t.published ? { index: true, follow: true } : { index: false, follow: false },
  };
}

export default function ToolPage({ params }: { params: { slug: string } }) {
  const tool = getTool(params.slug);
  if (!tool) notFound();
  // 도구별 화면은 구현·검증이 끝나는 대로 이 자리에 연결한다.
  return (
    <div className="container article">
      <Link href="/tools" className="a-cat">← 판정·비교 도구</Link>
      <h1>{tool.title}</h1>
      <p className="rank-intro">{tool.description}</p>
      <div className="mock-banner">🛠️ 준비 중입니다. 세법 규칙을 공식 자료로 확인한 뒤 공개합니다.</div>
    </div>
  );
}
