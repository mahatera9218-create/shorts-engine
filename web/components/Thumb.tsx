"use client";
import { useState } from "react";
import { sized } from "@/lib/imgsize";

// 스톡 사진 → 실패 시 생성 표지 → 둘 다 없으면 빈 박스. 깨진 이미지 방지.
export default function Thumb({
  src,
  fallback,
  alt,
  w = 640,
  priority = false,
}: {
  src: string | null;
  fallback: string | null;
  alt: string;
  w?: number;
  priority?: boolean;
}) {
  const chain = [src, fallback].filter(Boolean) as string[];
  const [i, setI] = useState(0);
  const cur = chain[i];
  if (!cur) return null;
  // eslint-disable-next-line @next/next/no-img-element
  return (
    <img
      src={sized(cur, w)}
      alt={alt}
      loading={priority ? "eager" : "lazy"}
      decoding="async"
      {...(priority ? { fetchPriority: "high" as const } : {})}
      width={w}
      height={Math.round((w * 2) / 3)}
      onError={() => setI((n) => n + 1)}
    />
  );
}
