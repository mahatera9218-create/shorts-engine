"use client";
import { useState } from "react";

// 스톡 사진 → 실패 시 생성 표지 → 둘 다 없으면 빈 박스. 깨진 이미지 방지.
export default function Thumb({
  src,
  fallback,
  alt,
}: {
  src: string | null;
  fallback: string | null;
  alt: string;
}) {
  const chain = [src, fallback].filter(Boolean) as string[];
  const [i, setI] = useState(0);
  const cur = chain[i];
  if (!cur) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={cur}
      alt={alt}
      loading="lazy"
      width={1200}
      height={800}
      onError={() => setI((n) => n + 1)}
    />
  );
}
