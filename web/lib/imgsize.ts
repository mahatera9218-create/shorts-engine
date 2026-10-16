// Unsplash 이미지 주소에 크기·품질·포맷을 붙여 필요한 만큼만 받는다(PageSpeed '이미지 전송 개선').
// Unsplash가 아닌 주소는 그대로 둔다.
export function sized(url: string, w: number): string {
  try {
    const u = new URL(url);
    if (!u.hostname.endsWith("unsplash.com")) return url;
    u.searchParams.set("w", String(w));
    u.searchParams.set("q", "65");
    u.searchParams.set("fm", "webp");
    u.searchParams.set("fit", "crop");
    return u.toString();
  } catch {
    return url;
  }
}
