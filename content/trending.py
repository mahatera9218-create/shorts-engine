"""화제 선수와 검색량 (대표 결정 2026-09-30): 풀을 넓히고, 지금 화제인 선수를 더 자주 쓴다.

1. 이벤트 뉴스(config/events.yaml: 한국시리즈·드래프트·트레이드·FA·챔스·월드컵…)에서 그 뉴스의 중심 선수를 뽑는다.
   Claude가 이름을 고르고, 코드가 그 이름이 기사 제목·요약에 실제로 있는지 확인한다. 경기·커리어 뉴스만 (사건·사고·사생활 제외).
   → config/trending.yaml (14일 동안 풀에 머물고 뽑힐 확률 3배). 풀에 없던 선수도 이 기간엔 후보가 된다.
2. 풀·화제 선수 이름의 네이버 월간 검색량(검색광고 키워드 도구, 공식 API) → config/search_volume.yaml.
   많이 찾는 선수일수록 뽑힐 확률을 올린다 (autopost.weighted_pool).
매일 자동 글쓰기 전에 실행 (daily-post.yml). 키가 없거나 실패하면 건너뛴다 (글쓰기는 그대로).
사용법: python -m content.trending [--sample]
"""
from __future__ import annotations

import math
import sys
from datetime import date, timedelta

import yaml

from market.common import ROOT, load_yaml, missing_secrets
from .autopost import extract_opts, gather_news, news_prompt

TREND_SCHEMA = {
    "type": "object",
    "properties": {"players": {"type": "array", "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "short": {"type": "string"},
                       "sport": {"type": "string", "enum": ["kbo", "mlb", "soccer", "epl", "laliga", "nba", "golf"]},
                       "team": {"type": "string"}, "why": {"type": "string"}, "source": {"type": "integer"}},
        "required": ["name", "short", "sport", "team", "why", "source"], "additionalProperties": False}}},
    "required": ["players"],
    "additionalProperties": False,
}

TREND_RULES = """너는 스포츠 뉴스 요약문에서 '지금 화제인 선수'를 고르는 담당이다.
- 경기 성과(결승타·홈런·골·우승·기록), 시상, 이적·트레이드·FA 계약, 드래프트처럼 경기와 커리어에 관한 뉴스의 중심 선수만.
- 사건·사고·범죄·사생활·연애·가족·도박·논란 뉴스의 선수는 고르지 않는다. 감독·구단 관계자·은퇴 선수도 제외.
- name은 기사에 적힌 한글 이름 그대로 (외국 선수도 기사 표기). short는 흔히 부르는 짧은 이름.
- sport: kbo(한국 프로야구) mlb(메이저리그) epl(프리미어리그) laliga(라리가) soccer(그 밖의 축구) nba golf.
- team은 기사에 나온 지금 소속팀 (모르면 빈 문자열). why는 화제 이유 한 줄 (숫자는 기사에 있는 것만). source는 기사 번호.
- 최대 12명, 화제가 큰 순서로."""


def find_trending(hub, llm, today: str) -> list[dict]:
    cfg = load_yaml("events.yaml")
    month = date.fromisoformat(today).month
    queries = [e["query"] for evs in cfg["events"].values() for e in evs if not e.get("months") or month in e["months"]]
    day = date.fromisoformat(today)
    news = [n for n in gather_news(hub, queries, per_query=6) if (day - date.fromisoformat(n["date"])).days <= 3]
    if not news:
        return []
    r = llm.ask_json([TREND_RULES], f"오늘: {today}\n\n뉴스 요약 (번호 = source):\n{news_prompt(news)}", TREND_SCHEMA, stage="화제 선수",
                     max_tokens=3000, **extract_opts())
    out = []
    for p in r["players"]:
        src = news[p["source"] - 1] if 1 <= p["source"] <= len(news) else None
        text = (src["title"] + " " + src["description"]) if src else ""
        if not src or (p["name"] not in text and p["short"] not in text):  # 기사에 없는 이름은 버린다
            continue
        out.append({**p, "date": today, "link": src["link"]})
    return out


def update_trending(found: list[dict], today: str, write: bool = True) -> list[dict]:
    """새로 찾은 화제 선수를 더하고, TTL이 지난 선수는 뺀다."""
    f = ROOT / "config" / "trending.yaml"
    cur = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("players", []) if f.exists() else []
    ttl = load_yaml("events.yaml").get("ttl_days", 14)
    cutoff = date.fromisoformat(today) - timedelta(days=ttl)
    keep = {p["name"]: p for p in cur if date.fromisoformat(str(p["date"])) >= cutoff}
    for p in found:
        keep[p["name"]] = p  # 다시 화제가 되면 날짜를 새로
    players = sorted(keep.values(), key=lambda p: str(p["date"]), reverse=True)
    if write:
        f.write_text("# 자동 생성 (content/trending.py). 손으로 고치지 않는다.\n" +
                 yaml.safe_dump({"updated": today, "players": players}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return players


def volume_factor(v: float) -> float:
    """월 검색량 → 뽑힐 확률 배수 (1만 = 1배, 10만 = 2배, 100만 이상 = 3배, 1천 이하 = 0.5배)."""
    if v <= 0:
        return 1.0
    return max(0.5, min(3.0, 1 + math.log10(v / 10_000)))


def update_volume(tool, names: list[str], today: str, write: bool = True) -> dict[str, int]:
    rows = {r["keyword"].replace(" ", ""): r for r in tool.related(names)}
    vol = {n: int(rows.get(n.replace(" ", ""), {}).get("volume", 0)) for n in names}
    if write:
        (ROOT / "config" / "search_volume.yaml").write_text(
        "# 자동 생성 (content/trending.py): 선수 이름 네이버 월간 검색량. 뽑힐 확률 배수는 autopost.weighted_pool.\n" +
        yaml.safe_dump({"updated": today, "volume": vol}, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return vol


def main() -> None:
    today = date.today().isoformat()
    sample = "--sample" in sys.argv
    pool = load_yaml("players.yaml")
    if sample:
        from .sample_post import FakeClaude, FakeNewsHub
        from market.sample import FakeKeywordTool
        hub, llm, tool = FakeNewsHub(), FakeClaude(), FakeKeywordTool()
    else:
        from market.naver_hub import ApiHub
        from .llm import Claude
        hub = ApiHub(load_yaml("global.yaml")["endpoints"]["naver_hub"]) if not missing_secrets("naver_hub") else None
        llm = Claude() if not missing_secrets("anthropic") else None
        tool = None
        if not missing_secrets("naver_ad"):
            from market.naver_ad import KeywordTool
            tool = KeywordTool(load_yaml("global.yaml")["endpoints"]["naver_ad_base"])
    lines = []
    trending = []
    try:
        if hub and llm:
            found = find_trending(hub, llm, today)
            trending = update_trending(found, today, write=not sample)
            lines.append(f"화제 선수 {len(found)}명 새로 찾음: " + ", ".join(f"{p['short']}({p['why']})" for p in found[:8]))
    except Exception as e:  # 화제 찾기가 실패해도 글쓰기는 그대로
        lines.append(f"화제 선수 찾기 건너뜀: {type(e).__name__}: {str(e)[:120]}")
    try:
        if tool:
            names = [p["name"] for p in pool["players"]] + [p["name"] for p in trending]
            vol = update_volume(tool, sorted(set(names)), today, write=not sample)
            top = sorted(vol.items(), key=lambda x: -x[1])[:5]
            lines.append("검색량 상위: " + ", ".join(f"{n} {v:,}" for n, v in top))
    except Exception as e:
        lines.append(f"검색량 재기 건너뜀: {type(e).__name__}: {str(e)[:120]}")
    if llm and not sample:
        from .llm import log_cost
        log_cost("화제 선수", llm)
    print("\n".join(lines) or "화제·검색량: 키가 없어 건너뜀")


if __name__ == "__main__":
    main()
