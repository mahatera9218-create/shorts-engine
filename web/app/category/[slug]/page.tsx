import type { Metadata } from "next";
import { notFound } from "next/navigation";
import {
  getPostsByCategorySlug,
  CATEGORY_ORDER,
  SITE_NAME,
} from "@/lib/wp";
import { stockPhoto } from "@/lib/photos";
import Link from "next/link";
import PostCard from "@/components/PostCard";

// 카테고리별 한 줄 안내 + 연결할 계산기 분류(얇은 카테고리 페이지 보강 + 내부 링크).
const CATEGORY_INTRO: Record<string, { text: string; group?: { key: string; name: string } }> = {
  jaetech: {
    text: "재테크 글은 ISA·연금저축처럼 '어디에 얼마를 넣을까'를 다룹니다. 세액공제 한도(연금저축 600만원·IRP 합산 900만원)는 아래 계산기로 바로 확인할 수 있습니다.",
    group: { key: "insurance", name: "건강보험·연금 계산기" },
  },
  realty: {
    text: "부동산 글은 집을 살 때(취득세), 보유할 때(재산세·종합부동산세), 팔 때(양도소득세) 붙는 세금을 다룹니다. 내 금액으로 계산해 보려면 부동산 세금 계산기 모음으로 이동하세요.",
    group: { key: "property", name: "부동산 세금 계산기" },
  },
  tax: {
    text: "세금·절세 글은 5월 신고, 증여·상속, 사업자등록처럼 '언제 무엇을 신고하는지'를 다룹니다. 내 숫자로 계산하려면 계산기 허브에서 상황에 맞는 계산기를 고르세요.",
    group: { key: "income", name: "소득·사업 세금 계산기" },
  },
  pension: {
    text: "연금·노후 글은 연금저축·IRP의 세액공제와 수령(연금소득세) 구조를 다룹니다. 납입액을 넣으면 돌려받을 세금을 계산기로 바로 확인할 수 있습니다.",
    group: { key: "insurance", name: "건강보험·연금 계산기" },
  },
};

// 글이 모두 저장소 파일에 있으므로 빌드 때 전부 미리 만든다(완전 정적).
// 서버리스 렌더가 없어 5xx 여지 0. 없는 주소는 정적 404. 새 글은 배포 때 반영.
export const dynamic = "force-static";
export const dynamicParams = false;

export function generateStaticParams() {
  return CATEGORY_ORDER.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const known = CATEGORY_ORDER.find((c) => c.slug === params.slug);
  const name = known?.name ?? params.slug;
  // 글이 3개 미만인 카테고리는 내용이 얇아 구글이 'soft 404'로 본다.
  // 글이 쌓일 때까지 색인에서 빼되(링크는 따라가게 follow:true), 3개 이상이면 자동 색인.
  const count = (await getPostsByCategorySlug(params.slug, 30)).length;
  const thin = count < 3;
  return {
    title: `${name} 글 모음`,
    description: `${SITE_NAME}의 ${name} 관련 글 모음.`,
    alternates: { canonical: `/category/${params.slug}` },
    robots: thin
      ? { index: false, follow: true }
      : { index: true, follow: true },
  };
}

export default async function CategoryPage({
  params,
}: {
  params: { slug: string };
}) {
  const known = CATEGORY_ORDER.find((c) => c.slug === params.slug);
  if (!known) notFound();
  const name = known.name;
  const posts = await getPostsByCategorySlug(params.slug, 30);
  const intro = CATEGORY_INTRO[params.slug];

  return (
    <div className="container">
      <section className="intro">
        <div>
          <h1 style={{ margin: 0 }}>{name}</h1>
          <p style={{ margin: "4px 0 0", color: "var(--sub)" }}>
            {name} 관련 글 모음
          </p>
        </div>
      </section>
      {intro ? (
        <p className="tool-sub" style={{ marginTop: 10 }}>
          {intro.text}{" "}
          {intro.group ? (
            <Link href={`/tools/group/${intro.group.key}`}>{intro.group.name} →</Link>
          ) : (
            <Link href="/tools">세금 계산기 →</Link>
          )}
        </p>
      ) : null}
      {posts.length === 0 ? (
        <p className="empty">이 카테고리에는 아직 글이 없습니다.</p>
      ) : (
        <div className="feed">
          {posts.map((post, i) => (
            <PostCard key={post.id} post={post} priority={i === 0} />
          ))}
        </div>
      )}
    </div>
  );
}
