import { getPosts, stripHtml, SITE_URL, SITE_NAME, SITE_DESC } from "@/lib/wp";

// RSS 2.0 피드(네이버 서치어드바이저 RSS 제출용). 주소: /rss.xml
export const dynamic = "force-static";
export const revalidate = 3600;

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

export async function GET() {
  const posts = await getPosts(50);
  const items = posts
    .map((p) => {
      const url = `${SITE_URL}/${p.slug}`;
      const desc = stripHtml(p.excerpt.rendered).slice(0, 300);
      return `<item><title>${esc(stripHtml(p.title.rendered))}</title><link>${url}</link><guid isPermaLink="true">${url}</guid><pubDate>${new Date(p.date).toUTCString()}</pubDate><description>${esc(desc)}</description></item>`;
    })
    .join("");
  const xml = `<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>${esc(SITE_NAME)}</title><link>${SITE_URL}</link><description>${esc(SITE_DESC)}</description><language>ko</language><lastBuildDate>${new Date().toUTCString()}</lastBuildDate>${items}</channel></rss>`;
  return new Response(xml, { headers: { "Content-Type": "application/rss+xml; charset=utf-8" } });
}
