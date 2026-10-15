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
  experimental: { missingSuspenseWithCSRBailout: false },
};

export default nextConfig;
