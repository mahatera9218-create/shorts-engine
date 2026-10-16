import { getPosts, getAllPageSlugs, stripHtml, SITE_NAME, SITE_DESC, SITE_URL } from "@/lib/wp";

export const revalidate = 3600;

// llms.txt — ChatGPT·Perplexity 등 AI가 사이트를 올바르게 인용하도록 돕는 안내 파일.
export async function GET() {
  const posts = await getPosts(100);
  const pages = await getAllPageSlugs();
  const lines: string[] = [
    `# ${SITE_NAME}`,
    `> ${SITE_DESC}`,
    "",
    `${SITE_NAME}는 재테크·부동산·세금·연금 정보를 국세청·국가법령정보 등 공식 1차 자료로 쉽고 정확하게 정리하는 한국 개인 금융 콘텐츠입니다. 연도·수정일·출처를 밝히고, 투자 권유나 수익 보장은 하지 않습니다. (${SITE_URL})`,
    "",
    "## 글",
    ...posts.map((p) => `- [${stripHtml(p.title.rendered)}](${SITE_URL}/${p.slug})`),
    "",
    "## 안내",
    ...pages.map((s) => `- ${SITE_URL}/p/${s}`),
    "",
  ];
  return new Response(lines.join("\n"), {
    headers: { "content-type": "text/plain; charset=utf-8" },
  });
}
