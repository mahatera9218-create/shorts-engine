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
          <Link href="/p/about">소개</Link>
        </div>
      ) : null}
    </div>
  );
}
