"use client";
import Link from "next/link";
import { useState } from "react";
import { CATEGORY_ORDER } from "@/lib/site";

export default function Menu() {
  const [open, setOpen] = useState(false);
  return (
    <div className="menu-wrap">
      <button
        className="icon-btn"
        onClick={() => setOpen((o) => !o)}
        aria-label="메뉴"
      >
        ≡
      </button>
      {open ? (
        <div className="menu-pop" onClick={() => setOpen(false)}>
          <Link href="/">홈</Link>
          {CATEGORY_ORDER.map((c) => (
            <Link key={c.slug} href={`/category/${c.slug}`}>
              {c.name}
            </Link>
          ))}
          <Link href="/tools">판정 도구</Link>
          {/* 공개 지표 비교(/rank)는 데이터 채우기 전까지 메뉴에서 숨김 — 심사 중 '미완성' 인상 방지(2026-10-18). 페이지 자체는 noindex로 유지. */}
          <Link href="/p/about">소개</Link>
        </div>
      ) : null}
    </div>
  );
}
