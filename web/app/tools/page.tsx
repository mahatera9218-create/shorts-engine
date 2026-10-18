import type { Metadata } from "next";
import Link from "next/link";
import { TOOLS } from "@/lib/tools/registry";

export const metadata: Metadata = {
  title: "판정·비교 도구",
  description: "직업·상황별로 내 경우에 해당하는지 바로 판정해 보는 세금·건강보험 도구 모음.",
  robots: TOOLS.some((t) => t.published) ? { index: true, follow: true } : { index: false, follow: false },
};

export default function ToolsHub() {
  return (
    <div className="container article">
      <h1>판정·비교 도구</h1>
      <p className="rank-intro">내 상황을 고르면 어느 쪽이 해당되는지·어느 쪽이 유리한지 바로 확인해 보세요. 입력값은 기기 안에서만 계산됩니다.</p>
      <div className="rank-list">
        {TOOLS.map((t) => (
          <div key={t.slug} className="rank-card">
            <div className="rank-body">
              <Link href={`/tools/${t.slug}`} className="rank-name">{t.short}</Link>
              <div className="rank-tag">{t.audience}{t.published ? "" : " · 검토 중(베타)"}</div>
              <p className="rank-note">{t.description}</p>
              <Link href={`/tools/${t.slug}`} className="rank-link">해보기 →</Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
