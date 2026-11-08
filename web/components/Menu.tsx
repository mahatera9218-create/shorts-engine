"use client";
import Link from "next/link";
import { useState } from "react";
import { TOOL_GROUPS } from "@/lib/tools/registry";

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
          <Link href="/tools">🧮 세금 계산기</Link>
          {TOOL_GROUPS.map((g) => (
            <Link key={g.key} href={`/tools/group/${g.key}`} className="menu-sub">
              {g.name}
            </Link>
          ))}
          <Link href="/p/about">소개</Link>
        </div>
      ) : null}
    </div>
  );
}
