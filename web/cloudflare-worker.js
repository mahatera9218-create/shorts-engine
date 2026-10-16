// astacgroup.com 트래픽 분리 Worker
// - 손님이 보는 페이지 → Vercel(헤드리스, 빠름)
// - /wp-* (관리자·로그인·REST·업로드 이미지 등) → 그대로 워드프레스(가비아 원본)
// 워드프레스·네임서버·SSL은 전혀 바꾸지 않는다. Cloudflare에 이 Worker만 올리고
// 라우트 astacgroup.com/* 에 연결하면 된다.

const VERCEL_ORIGIN = "https://shorts-engine-roan.vercel.app";

// 워드프레스가 처리해야 하는 경로
function isWordPress(pathname) {
  return (
    pathname.startsWith("/wp-admin") ||
    pathname.startsWith("/wp-content") ||
    pathname.startsWith("/wp-includes") ||
    pathname.startsWith("/wp-json") ||
    pathname.startsWith("/wp-login") ||
    pathname.startsWith("/wp-cron") ||
    pathname.startsWith("/wp-signup") ||
    pathname.startsWith("/wp-trackback") ||
    pathname.startsWith("/wp-comments-post") ||
    pathname === "/xmlrpc.php"
  );
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    // 같은 존(astacgroup.com)으로의 fetch는 Cloudflare가 원본(가비아 WP)으로 보낸다.
    if (isWordPress(url.pathname)) {
      return fetch(request);
    }
    // 나머지는 Vercel 헤드리스에서 가져온다.
    const target = new URL(url.pathname + url.search, VERCEL_ORIGIN);
    return fetch(new Request(target, request));
  },
};
