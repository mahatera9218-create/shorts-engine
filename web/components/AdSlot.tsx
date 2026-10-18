"use client";
import { useEffect } from "react";

// 광고 자리. 애드센스 광고 단위 ID(NEXT_PUBLIC_ADSENSE_SLOT)가 설정되면 실제 광고를,
// 없으면 아무것도 그리지 않는다. 레이아웃의 애드센스 스크립트를 사용.
const CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT || "ca-pub-6435261744776184";
const SLOT = process.env.NEXT_PUBLIC_ADSENSE_SLOT || "";

export default function AdSlot() {
  useEffect(() => {
    if (!SLOT) return;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      ((window as any).adsbygoogle = (window as any).adsbygoogle || []).push({});
    } catch {
      /* 광고 로드 실패는 무시 */
    }
  }, []);

  // 광고 단위 ID가 없으면 아무것도 그리지 않는다(빈 '광고' 자리표는 승인 심사에서 오해를 부를 수 있음).
  if (!SLOT) return null;
  return (
    <ins
      className="adsbygoogle"
      style={{ display: "block" }}
      data-ad-client={CLIENT}
      data-ad-slot={SLOT}
      data-ad-format="auto"
      data-full-width-responsive="true"
    />
  );
}
