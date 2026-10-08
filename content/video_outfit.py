"""방송 클립 착장 조사 시험 (대표 요청 2026-10-08: 유튜브 방송 클립에서 연예인 착장을 머리부터 발끝까지).

공식 통로만 쓴다 (영상은 받지 않는다 — 타인 영상 다운로드 금지):
1) 유튜브 Data API(YOUTUBE_API_KEY): 이름으로 최근 공개 클립 찾기
2) Gemini API(GEMINI_API_KEY): 유튜브 주소를 직접 보고 착장을 부위별로 정리 (색·소재·실루엣·잘 보이는 시각)
   — 영상만 보고 브랜드를 짐작하지 않게 한다
3) Grok(XAI_API_KEY, 웹+X): 착장마다 브랜드·제품명·가격을 기사·공식·팬 계정에서 확인, 없으면 '확인 안 됨'
결과: reports/<날짜>-<이름>-방송착장-시험.md (토큰·비용 포함). 설정: config/video_outfit.yaml
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

from . import econ_flow as F

ROOT = Path(__file__).resolve().parent.parent
CFG = ROOT / "config" / "video_outfit.yaml"
GEM_MODEL = "gemini-2.5-flash"
GEM_PRICE = (0.30, 2.50)  # 달러/100만 토큰 (입력·출력). 공식 단가표로 다시 확인할 것 (2026-10-08 집계 사이트 기준)
DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def key(n: str) -> str:
    return os.environ.get(n, "").strip()


def seconds(iso: str) -> int:
    m = DUR.fullmatch(iso or "")
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0) if m else 0


def clips(name: str, days: int, max_sec: int, n: int) -> list[dict]:
    """최근 days일 공개 클립 중 max_sec 이하, 조회수 많은 순 n개."""
    k = key("YOUTUBE_API_KEY")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get("https://www.googleapis.com/youtube/v3/search", timeout=30, params={
        "key": k, "part": "snippet", "q": name, "type": "video", "order": "relevance", "publishedAfter": since,
        "maxResults": 25, "regionCode": "KR", "relevanceLanguage": "ko"})
    r.raise_for_status()
    ids = [it["id"]["videoId"] for it in r.json().get("items", [])]
    if not ids:
        return []
    v = requests.get("https://www.googleapis.com/youtube/v3/videos", timeout=30, params={
        "key": k, "part": "snippet,contentDetails,statistics,status", "id": ",".join(ids)})
    v.raise_for_status()
    out = []
    for it in v.json().get("items", []):
        sec = seconds(it["contentDetails"].get("duration", ""))
        if not (20 <= sec <= max_sec) or it.get("status", {}).get("privacyStatus") != "public":
            continue
        if name.replace(" ", "") not in (it["snippet"]["title"] + it["snippet"].get("description", "")).replace(" ", ""):
            continue  # 이름이 제목·설명에 없으면 다른 사람 영상일 수 있음
        out.append({"id": it["id"], "title": it["snippet"]["title"], "channel": it["snippet"]["channelTitle"],
                    "at": it["snippet"]["publishedAt"][:10], "sec": sec,
                    "views": int(it.get("statistics", {}).get("viewCount", 0))})
    return sorted(out, key=lambda x: -x["views"])[:n]


ASK = """이 영상에 나오는 '{name}'의 착장을 머리부터 발끝까지 정리해 주세요. {name}이 안 나오거나 누군지 확실하지 않으면 "확인 불가"라고만 쓰세요.
부위 순서: 헤어 / 메이크업 포인트 / 귀걸이·목걸이·반지 등 액세서리 / 아우터 / 상의 / 하의(또는 원피스·드레스) / 가방 / 신발 / 기타(시계·모자·안경).
부위마다: 아이템 종류, 색, 소재(보이는 대로), 실루엣·핏, 눈에 띄는 디테일(단추·로고 모양·패턴), 가장 잘 보이는 시각(분:초).
규칙: 영상에서 로고·글자가 또렷이 읽히는 경우만 브랜드를 적고("로고로 확인"), 아니면 브랜드는 비워 두세요. 짐작으로 브랜드·가격을 쓰지 마세요.
옷이 바뀌면 장면별로 나눠 주세요. 한국어로."""


def gemini_watch(url: str, name: str) -> tuple[str, dict]:
    h = {"x-goog-api-key": key("GEMINI_API_KEY")}
    body = {"contents": [{"parts": [{"file_data": {"file_uri": url}}, {"text": ASK.format(name=name)}]}],
            "generationConfig": {"mediaResolution": "MEDIA_RESOLUTION_LOW"}}  # 낮은 화질로 토큰 아낌
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEM_MODEL}:generateContent",
                      headers=h, json=body, timeout=600)
    if r.status_code != 200:
        return f"❌ Gemini HTTP {r.status_code}: {r.text[:300]}", {}
    j = r.json()
    text = "".join(p.get("text", "") for c in j.get("candidates", [])[:1] for p in c.get("content", {}).get("parts", []))
    return text.strip(), j.get("usageMetadata", {})


def main() -> None:
    cfg = yaml.safe_load(CFG.read_text(encoding="utf-8")) or {}
    name = cfg["name"]
    found = clips(name, cfg.get("days", 3), cfg.get("max_sec", 600), cfg.get("clips", 2)) or \
        clips(name, 14, cfg.get("max_sec", 600), cfg.get("clips", 2))  # 최근 3일에 없으면 2주로
    md = [f"# 방송 클립 착장 조사 시험: {name} ({F.today()})", "",
          "공식 통로만: 유튜브 Data API로 찾고 → Gemini가 유튜브 주소를 직접 봄(영상 다운로드 없음) → Grok이 브랜드·가격 확인.", ""]
    if not found:
        md += ["찾은 클립이 없어요 (최근 2주, 공개, 10분 이하, 제목·설명에 이름)."]
    gem_in = gem_out = 0
    notes = []
    for c in found:
        url = f"https://www.youtube.com/watch?v={c['id']}"
        text, u = gemini_watch(url, name)
        gem_in += u.get("promptTokenCount", 0)
        gem_out += u.get("candidatesTokenCount", 0) + u.get("thoughtsTokenCount", 0)
        notes.append(f"[{c['title']}]\n{text}")
        md += [f"## {c['title']}", f"- {c['channel']} · {c['at']} · {c['sec'] // 60}분 {c['sec'] % 60}초 · 조회 {c['views']:,} · {url}",
               f"- Gemini 토큰: 입력 {u.get('promptTokenCount', 0):,} / 출력 {u.get('candidatesTokenCount', 0) + u.get('thoughtsTokenCount', 0):,}", "",
               "### Gemini가 본 착장", "", text, ""]
    if notes:
        before = sum(F.SPENT.values())
        g = F.grok(f"오늘은 {F.today()}(한국 시간)입니다. 아래는 '{name}'이 최근 방송 클립에서 입은 착장을 영상으로 정리한 메모입니다.\n"
                   "아이템마다 웹·X에서 기사·브랜드 공식·스타일리스트·팬 계정(착용 정보) 자료를 찾아 브랜드·제품명·가격(원, 기준 시점)을 확인해 주세요.\n"
                   "형식: 부위 | 아이템 | 브랜드·제품명 | 가격 | 근거(사이트 이름·날짜) | 확실도(확인/추정/확인 안 됨).\n"
                   "자료로 확인 안 되면 '확인 안 됨'으로 두고 지어내지 마세요. 맨 끝에 '출처:' 아래 제목과 URL.\n\n" + "\n\n".join(notes)[:12000],
                   days=14, web=True, turns=3)
        grok_usd = sum(F.SPENT.values()) - before
        md += ["## 브랜드·가격 확인 (Grok, 웹+X)", "", g or "❌ Grok 응답 없음", ""]
    else:
        grok_usd = 0.0
    gem_usd = gem_in / 1e6 * GEM_PRICE[0] + gem_out / 1e6 * GEM_PRICE[1]
    md += ["## 비용", "",
           f"- Gemini({GEM_MODEL}): 입력 {gem_in:,} · 출력 {gem_out:,} 토큰 → 약 ${gem_usd:.4f} (약 {gem_usd * 1400:,.0f}원, 단가 ${GEM_PRICE[0]}/${GEM_PRICE[1]} 백만 토큰 기준 — 공식 단가표 확인 필요)",
           f"- Grok: 약 ${grok_usd:.4f} (약 {grok_usd * 1400:,.0f}원)",
           f"- 합계: 약 {(gem_usd + grok_usd) * 1400:,.0f}원 (클립 {len(found)}개)", ""]
    out = ROOT / "reports" / f"{F.today()}-{name}-방송착장-시험.md"
    out.write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md)[:3000])


if __name__ == "__main__":
    main()
