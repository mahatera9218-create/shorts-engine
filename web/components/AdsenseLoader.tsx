"use client";
import { useEffect } from "react";

// 애드센스 스크립트 지연 로드(PageSpeed '사용하지 않는 자바스크립트'·'긴 기본 스레드 작업' 개선).
// 첫 화면 렌더·상호작용 동안에는 광고 JS를 받지 않고, 사용자가 스크롤·터치·키 입력을 하거나
// 일정 시간(TIMEOUT)이 지나면 그때 한 번만 로드한다. 소유확인은 layout의 google-adsense-account 메타로 한다.
const CLIENT = process.env.NEXT_PUBLIC_ADSENSE_CLIENT || "ca-pub-6435261744776184";
const TIMEOUT = 8000;
const EVENTS = ["scroll", "touchstart", "pointerdown", "keydown"] as const;

export default function AdsenseLoader() {
  useEffect(() => {
    if (!CLIENT) return;
    let done = false;
    const load = () => {
      if (done) return;
      done = true;
      EVENTS.forEach((e) => window.removeEventListener(e, load));
      clearTimeout(timer);
      const s = document.createElement("script");
      s.async = true;
      s.crossOrigin = "anonymous";
      s.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${CLIENT}`;
      document.head.appendChild(s);
    };
    const timer = setTimeout(load, TIMEOUT);
    EVENTS.forEach((e) => window.addEventListener(e, load, { once: true, passive: true }));
    return () => {
      done = true;
      EVENTS.forEach((e) => window.removeEventListener(e, load));
      clearTimeout(timer);
    };
  }, []);
  return null;
}
