"use client";
import { useEffect, useState } from "react";

export default function DarkToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    const t = document.documentElement.getAttribute("data-theme");
    const sys =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-color-scheme: dark)").matches;
    setDark(t === "dark" || (!t && sys));
  }, []);
  const toggle = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {}
    setDark(!dark);
  };
  return (
    <button className="icon-btn" onClick={toggle} aria-label="다크 모드 전환">
      {dark ? "☀" : "☾"}
    </button>
  );
}
