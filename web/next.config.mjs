/** @type {import('next').NextConfig} */
const wpHost = (() => {
  try {
    return new URL(process.env.WP_API_BASE || "https://astacgroup.com/wp-json/wp/v2").hostname;
  } catch {
    return "astacgroup.com";
  }
})();

const nextConfig = {
  reactStrictMode: true,
  // 워드프레스 미디어(도식·이미지)를 next/image로 최적화하려면 호스트를 허용해야 한다.
  images: {
    remotePatterns: [
      { protocol: "https", hostname: wpHost },
      { protocol: "https", hostname: "*.gravatar.com" },
    ],
  },
  // 빌드 시 WP가 잠깐 안 떠도 배포가 막히지 않게(런타임 ISR로 채움).
  experimental: {
    missingSuspenseWithCSRBailout: false,
  },
  // 옛 주소 → 지금 페이지 301 영구 리다이렉트.
  // 2024년에 이 도메인에 있던 워드프레스 글 주소로, 지금은 글이 없다(Search Console '찾을 수 없음(404)' 9건).
  // 가장 가까운 현행 글·계산기로 보내 색인·유입을 살린다. statusCode 301 = 진짜 301(permanent: true는 308).
  async redirects() {
    const old = [
      // 국민연금 실업크레딧 → 실업급여 계산기(고용보험·실업 계열)
      ["/gukmin-yeongeum-sileop-credit", "/tools/unemployment"],
      // 내일배움카드(고용보험 직업훈련) → 실업급여 계산기
      ["/naeil-baeum-card", "/tools/unemployment"],
      // 고용보험 실업급여 요건 → 실업급여 계산기
      ["/goyong-boheom-sileop-geupyeo-yogeon", "/tools/unemployment"],
      // 금융소득 종합과세(2,000만원 초과) → 5월 종합소득세 신고 글
      ["/geumyung-sodeuk-jonghap-gwase", "/jonghap-sodeukse-singo-5wol"],
      // 예금 이자 소득세(15.4%) → 소득세율표
      ["/yegeum-ija-sodeukse", "/sodeukse-yulpyo-2026"],
      // 연금 수령 한도 → 연금저축·IRP 글
      ["/yeongeum-suryeong-hando", "/yeongeum-irp-semuchul-gongje-2026"],
      // 건강보험 임의계속가입 → 직장 그만둔 뒤 지역가입자 건보료 글
      ["/geonbo-imui-gyesok-gaip", "/jiyeok-geonbo-san-jeong"],
      // 옛 홈 주소 → 홈
      ["/home", "/"],
      // ---- 2026-11-16: 대응이 정확한 옛 글 4건 → 현행 계산기·글 ----
      // 퇴직금 세금 계산 → 퇴직소득세 계산기
      ["/toejikgeum-se-gyesan", "/tools/retirement-tax"],
      // 재산세 납기(재산세 안내) → 주택 재산세 계산기
      ["/jaesan-se-nap-gi", "/tools/property-tax"],
      // 증여 vs 상속 어디가 유리 → 부동산 증여·상속 비교 글
      ["/jeungyeo-vs-sangsok-eoddi-yuri", "/budongsan-jeungyeo-vs-sangsok"],
      // 부가세 환급 요건 → 온라인 셀러 부가세(간이·일반) 비교
      ["/budaese-hwangeup-yogeon", "/tools/seller-vat"],
    ];
    // 301(permanent)로 보낸다. 요청이 `/옛주소/` 처럼 슬래시로 끝나면 Next가 먼저
    // `/옛주소`로 308 정규화한 뒤 이 301을 타므로, 두 형태 모두 결국 같은 페이지(200)로 도착한다.
    return old.map(([source, destination]) => ({ source, destination, statusCode: 301 }));
  },
  // 정적 이미지는 오래 캐시(PageSpeed '효율적인 캐시 수명').
  async headers() {
    const long = [{ key: "Cache-Control", value: "public, max-age=31536000, immutable" }];
    return [
      { source: "/logo.webp", headers: long },
      { source: "/icon.png", headers: long },
    ];
  },
};

export default nextConfig;
