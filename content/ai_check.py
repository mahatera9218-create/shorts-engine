"""AI 연결 점검 (2026-10-05): Gemini(구글 검색 연동) · Grok · Claude 웹 검색이 키로 실제 답하는지 한 번씩 물어본다.

키 값은 출력하지 않는다. 결과: reports/AI-연결-점검-<날짜>.md
"""
from __future__ import annotations

import os
import time
from datetime import date
from pathlib import Path

import requests

Q = "오늘 국제 금값과 관련해 가장 최근 주요 뉴스 한 가지를 한 문장으로, 출처 사이트 이름과 함께 알려줘."


def key(n: str) -> str:
    return os.environ.get(n, "").strip()


def gemini() -> str:
    k = key("GEMINI_API_KEY")
    if not k:
        return "❌ 키 없음 (GEMINI_API_KEY)"
    h = {"x-goog-api-key": k}
    models = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers=h, timeout=30)
    if models.status_code != 200:
        return f"❌ 모델 목록 HTTP {models.status_code}: {models.text[:150]}"
    names = [m["name"].split("/")[-1] for m in models.json().get("models", [])]
    model = next((m for m in ("gemini-2.5-flash", "gemini-flash-latest") if m in names), None) or \
        next((m for m in names if "flash" in m and "image" not in m and "tts" not in m), names[0])
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers=h,
                      json={"contents": [{"parts": [{"text": Q}]}], "tools": [{"google_search": {}}]}, timeout=120)
    if r.status_code != 200:
        return f"❌ {model} HTTP {r.status_code}: {r.text[:200]}"
    c = r.json()["candidates"][0]
    text = "".join(p.get("text", "") for p in c["content"]["parts"])
    srcs = [g.get("web", {}).get("title", "") for g in c.get("groundingMetadata", {}).get("groundingChunks", [])]
    return f"✅ {model} · 구글 검색 출처 {len(srcs)}개 ({', '.join(srcs[:3])})\n  > {text.strip()[:200]}"


def grok() -> str:
    k = key("XAI_API_KEY")
    if not k:
        return "❌ 키 없음 (XAI_API_KEY)"
    h = {"Authorization": f"Bearer {k}"}
    m = requests.get("https://api.x.ai/v1/models", headers=h, timeout=30)
    if m.status_code != 200:
        return f"❌ 모델 목록 HTTP {m.status_code}: {m.text[:200]}"
    ids = [x["id"] for x in m.json().get("data", [])]
    model = next((i for i in ids if "grok" in i and "image" not in i and "vision" not in i and "mini" not in i), ids[0])
    r = requests.post("https://api.x.ai/v1/chat/completions", headers=h, timeout=120,
                      json={"model": model, "messages": [{"role": "user", "content": "한 문장으로 자기소개 해줘."}]})
    if r.status_code != 200:
        return f"❌ {model} HTTP {r.status_code}: {r.text[:200]}"
    return f"✅ {model} 응답 OK (쓸 수 있는 모델 {len(ids)}개: {', '.join(ids[:6])})\n  > {r.json()['choices'][0]['message']['content'][:150]}"


def claude_search() -> str:
    if not key("ANTHROPIC_API_KEY"):
        return "❌ 키 없음 (ANTHROPIC_API_KEY)"
    import anthropic
    c = anthropic.Anthropic()
    msg = c.messages.create(model="claude-sonnet-5-5", max_tokens=600,
                            tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 2}],
                            messages=[{"role": "user", "content": Q}])
    text = "".join(b.text for b in msg.content if b.type == "text")
    n = sum(1 for b in msg.content if b.type == "web_search_tool_result")
    return f"✅ claude-sonnet-5-5 웹 검색 {n}번\n  > {text.strip()[:200]}"


def main() -> None:
    lines = [f"# AI 연결 점검 ({date.today()})", ""]
    for name, fn in (("Gemini (구글 검색 연동)", gemini), ("Grok", grok), ("Claude 웹 검색", claude_search)):
        t0 = time.time()
        try:
            res = fn()
        except Exception as e:  # 실패도 그대로
            res = f"❌ {type(e).__name__}: {str(e)[:200]}"
        lines += [f"## {name}", "", res, f"({time.time() - t0:.0f}초)", ""]
    out = Path("reports") / f"AI-연결-점검-{date.today()}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
