"""순위·총정리형 글 (대표 결정 2026-09-30, 양찬군주 벤치마크): 주 1~2편, 정한 요일의 첫 후보를 순위 글로.

- 목록·요일: config/rankings.yaml. 숫자: 확인 연봉표 config/salaries.yaml (발표·보도, 출처·기준일). 뉴스를 모으지 않는다.
- 계산(순위·공동 순위·월급·하루·1경기·최저임금·배수)과 그림은 코드, 글은 Claude (다른 글과 같은 검사).
- 달러 연봉은 오늘 글에서 뽑은 환율(3일 안)로만 원화 환산. 환율이 없으면 그 목록은 건너뛴다.
- 결과 폴더: posts/<날짜>-rank-<목록 key>/ (썸네일·순위표·단위표·최저임금 카드, 클립 줄거리)
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

from market.common import ROOT, load_yaml
from . import cards, receipt
from .brand import center_text, fit
from .cards import INK, PINK, SOFT, W, _base, _highlight
from .receipt import short_won, won
from .themes import _table, ratio

POSTS = ROOT / "posts"


def cfg() -> dict:
    return load_yaml("rankings.yaml")


def due(today: str, c: dict | None = None) -> bool:
    return date.fromisoformat(today).weekday() in (c or cfg()).get("days", [])


def short(name: str) -> str:
    """화면·글에 쓸 이름: 한국 이름은 그대로, 외국 이름은 성(마지막 말)만 ('스테픈 커리' → '커리')."""
    return name.split(" ")[-1] if " " in name else name


def last_used(key: str) -> str:
    """이 목록으로 쓴 가장 최근 날짜 (버린 글은 빼지 않는다: 같은 목록을 바로 다시 쓰지 않게)."""
    days = [f.name[:10] for f in POSTS.glob(f"*-rank-{key}") if f.is_dir()] if POSTS.exists() else []
    return max(days, default="0000-00-00")


def pick(today: str, c: dict | None = None) -> list[dict]:
    """오늘 쓸 수 있는 목록 (가장 오래전에 쓴 것부터). repeat_days 안에 쓴 목록은 뺀다."""
    c = c or cfg()
    cut = str(date.fromisoformat(today) - timedelta(days=c.get("repeat_days", 21)))
    ok = [x for x in c["lists"] if last_used(x["key"]) < cut]
    return sorted(ok, key=lambda x: last_used(x["key"]))


def data(lst: dict, today: str, fx: tuple[float | None, str]) -> tuple[dict, dict] | str:
    """목록 → (data, facts). 쓸 수 없으면 이유 문자열."""
    sal = load_yaml("salaries.yaml")
    pool = {p["name"]: p for p in load_yaml("players.yaml")["players"]}
    rate, fx_label = fx
    rows = []
    for name in lst["players"]:
        s = sal["players"].get(name)
        if not s:
            return f"{lst['title']}: 확인 연봉표에 {name} 없음"
        if s["currency"] == "USD" and not rate:
            return f"{lst['title']}: 달러 연봉인데 오늘 환율이 없음"
        krw = s["amount"] if s["currency"] == "KRW" else s["amount"] * rate
        team = pool.get(name, {}).get("team", "") or (lst.get("teams") or {}).get(name, "")
        rows.append({"name": name, "short": short(name), "team": team,
                     "amount": s["amount"], "currency": s["currency"], "krw": int(krw),
                     "basis": s["basis"], "as_of": str(s["as_of"]), "source": s["source"]})
    rows.sort(key=lambda r: -r["krw"])
    for r in rows:  # 공동 순위: 나보다 많은 사람 수 + 1
        r["rank"] = 1 + sum(1 for x in rows if x["krw"] > r["krw"])
        r["tie"] = sum(1 for x in rows if x["krw"] == r["krw"]) > 1
    usd = any(r["currency"] == "USD" for r in rows)
    d = {"theme": "rank", "key": lst["key"], "title": lst["title"], "short_name": lst["short"], "tag": lst["tag"],
         "sport": lst["sport"], "league": lst["league"], "games": lst["games"], "complete": lst["complete"],
         "basis": lst["basis"], "season": str(lst.get("season") or sal.get("season")), "rows": rows}
    if usd:
        d |= {"fx_krw_per_usd": rate, "fx_label": fx_label}
    facts = {f"salary.{r['name']}": {"key": f"salary.{r['name']}", "label": f"{r['name']} 연봉", "value": r["amount"],
                                     "unit": r["currency"], "date": r["as_of"], "rule": "확인 연봉표 (발표·보도)",
                                     "sources": [r["source"]], "differs": None} for r in rows}
    if usd:
        facts["fx_krw_per_usd"] = {"key": "fx_krw_per_usd", "label": "원·달러 환율", "value": rate, "unit": "원",
                                   "date": today, "rule": f"오늘 글의 환율 ({fx_label})", "sources": [], "differs": None}
    return d, facts


def compute(d: dict, min_wage_monthly: int) -> dict:
    rows, games = d["rows"], d["games"]
    per = [{"name": r["name"], "short": r["short"], "rank": r["rank"], "salary": r["krw"], "month": r["krw"] / 12,
            "day": r["krw"] / 365, "game": r["krw"] / games} for r in rows]
    top, low = rows[0], rows[-1]
    wage_year = min_wage_monthly * 12
    return {"per": per, "total": sum(r["krw"] for r in rows), "top_over_last": top["krw"] / low["krw"],
            "top_wage_years": top["krw"] / wage_year if wage_year else 0, "min_wage_yearly_krw": wage_year,
            "games": games}


def rank_label(r: dict, complete: bool) -> str:
    return f"공동 {r['rank']}위" if r["tie"] else f"{r['rank']}위"


def first_word(d: dict) -> str:
    """1위를 부르는 말: 전체 순위가 아니면 'N명 중 1위'."""
    return "1위" if d["complete"] else f"{len(d['rows'])}명 중 1위"


def build(folder: Path, d: dict) -> dict:
    """썸네일 + 순위표 + 단위표 + 최저임금 카드, 클립 줄거리, numbers.json."""
    qc = load_yaml("post_queue.yaml")["constants"]
    n = compute(d, qc["min_wage_monthly_krw"])
    rows, top = d["rows"], n["per"][0]
    photo = Image.open(folder / "photo.jpg") if (folder / "photo.jpg").exists() else None
    head = f"{d['short_name']} 연봉 TOP {len(rows)}" if d["complete"] else f"{d['short_name']} 연봉 {len(rows)}명"
    first = first_word(d)
    imgs = {"thumb.png": receipt.poster(d["tag"], head, f"{first} 하루에", short_won(top["day"]), photo)}
    total = 4
    team = all(r["team"] for r in rows)
    im, dr = _base(2, total)
    center_text(dr, (W / 2, 190), d["title"], fit(dr, d["title"], "display", 64, W * 0.86), INK)
    table = [["순위", "선수"] + (["팀"] if team else []) + ["연봉"]]
    table += [[rank_label(r, d["complete"]), r["short"]] + ([r["team"]] if team else []) + [won(r["krw"])] for r in rows]
    end = _table(dr, table, [0.2, 0.22, 0.28, 0.3] if team else [0.22, 0.3, 0.48], 290, {1})
    note = d["basis"] + (f" · 환율 {d['fx_label']}" if d.get("fx_label") else "")
    center_text(dr, (W / 2, end + 50), note, fit(dr, note, "r", 28, W * 0.86), SOFT)
    imgs["card_table.png"] = im
    im, dr = _base(3, total)
    title = "월급·하루·1경기로 바꾸면"
    center_text(dr, (W / 2, 190), title, fit(dr, title, "display", 64, W * 0.86), INK)
    units = [["선수", "월급", "하루", f"1경기 ({d['games']}경기)"]]
    units += [[p["short"], won(p["month"]), won(p["day"]), won(p["game"])] for p in n["per"]]
    end = _table(dr, units, [0.2, 0.28, 0.24, 0.28], 290, {1})
    note = "연봉 ÷ 12 · ÷ 365 · ÷ 정규시즌 경기 수 (만원 아래 버림)"
    center_text(dr, (W / 2, end + 50), note, fit(dr, note, "r", 28, W * 0.86), SOFT)
    imgs["card_units.png"] = im
    im, dr = _base(4, total)
    ask = f"{first} 연봉, 최저임금으로 벌려면?"
    center_text(dr, (W / 2, 230), ask, fit(dr, ask, "display", 68, W * 0.86), INK)
    _highlight(dr, (W / 2, 430), cards.wage_text(n["top_wage_years"]), 150, color=PINK)
    line = f"{top['short']} 연봉 {won(top['salary'])} ÷ 최저임금 1년 {won(n['min_wage_yearly_krw'])}"
    center_text(dr, (W / 2, 640), line, fit(dr, line, "b", 40, W * 0.86), INK)
    center_text(dr, (W / 2, 710), qc["min_wage_label"], fit(dr, qc["min_wage_label"], "r", 30, W * 0.86), SOFT)
    imgs["card_wage.png"] = im
    for name, img in imgs.items():
        img.save(folder / name)
    (folder / "numbers.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
    (folder / "clip.json").write_text(json.dumps(story(d, n, folder.name), ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def story(d: dict, n: dict, seed: str) -> dict:
    """클립: 1위 연봉(가림) → 1위는 누구? 퀴즈 → 정답 → 금액 공개 → 순위표 → 최저임금."""
    per = n["per"]
    first = first_word(d)
    opts = [p["short"] for p in per[:3]]
    random.Random(seed).shuffle(opts)
    return {"hook": {"tag": d["tag"], "name": f"{d['short_name']} TOP {len(per)}" if d["complete"] else f"{d['short_name']} {len(per)}명",
                     "label": f"{first} 연봉은", "big": short_won(per[0]["salary"]), "players": []},
            "quiz": {"lines": [f"{d['short_name']} 연봉 {first}는", "누구일까?"], "options": opts, "answer": opts.index(per[0]["short"])},
            "answer": {"big": per[0]["short"], "top": first, "line": f"하루에 {won(per[0]['day'])}"},
            "table": {"title": d["title"], "header": ["순위", "선수", "연봉"],
                      "rows": [[rank_label(r, d["complete"]), r["short"], short_won(r["krw"])] for r in d["rows"]], "hot": [0]},
            "wage": {"title": "최저임금으로 이 돈 벌려면?", "big": cards.wage_text(n["top_wage_years"])} if n["top_wage_years"] else None}


def sheet(d: dict, n: dict, qc: dict) -> str:
    """글쓴이에게 주는 숫자표 (검사도 이 표로)."""
    per, rows = n["per"], d["rows"]
    first = first_word(d)
    L = [f"주제: {d['title']} ({d['basis']})",
         f"제목용 짧은 이름: {d['short_name']}",
         f"썸네일: {d['short_name']} / {first} 하루에 / {short_won(per[0]['day'])} (추천 제목에는 이 금액을 다시 쓰지 않는다)",
         "순위 규칙: 이 목록 안에서만 순위를 말한다. " + ("발표·보도로 확인된 순위다." if d["complete"] else
                                                   f"전체 순위가 아니다 → 순위는 '{len(rows)}명 중 N위'로만, 'TOP'·'전체 1위'라고 쓰지 않는다.")
         + " 같은 금액은 '공동 N위'. 목록 밖 선수의 순위를 단정하지 않는다.",
         f"1경기 = 연봉 ÷ 정규시즌 {d['games']}경기 (실제 출전 경기가 아니다 → '1경기로 나누면'처럼 쓴다)"]
    if d.get("fx_label"):
        L.append(f"환율: {d['fx_label']} (달러 연봉을 원화로 환산. 본문 끝 '기준:' 문단에만 환율을 쓴다)")
    L.append("선수별 (연봉 · 월급=연봉÷12 · 하루=연봉÷365 · 1경기, 만원 아래 버림):")
    for r, p in zip(rows, per):
        L.append(f"- {rank_label(r, d['complete'])} {r['name']} ({r['team'] or '팀 표기 없음'}): 연봉 {won(p['salary'])}"
                 f" (버림 표기 {short_won(p['salary'])}) · 월급 {won(p['month'])} · 하루 {won(p['day'])} · 1경기 {won(p['game'])}"
                 f" · 근거: {r['basis']} ({r['as_of']})")
    L += [f"{len(rows)}명 연봉 합계: {won(n['total'])}",
          f"{first} 연봉은 마지막 {rank_label(rows[-1], d['complete'])}"
          f"({', '.join(r['short'] for r in rows if r['krw'] == rows[-1]['krw'])})보다 {won(rows[0]['krw'] - rows[-1]['krw'])} 더"
          + (f" ({ratio(n['top_over_last'])}배)" if n["top_over_last"] >= 1.5 else ""),
          f"{first} 연봉 = 최저임금 연봉 {n['top_wage_years']:.1f}년치 ({cards.wage_text(n['top_wage_years'])})",
          f"최저임금 1년: {won(n['min_wage_yearly_krw'])} ({qc['min_wage_label']})",
          "글 방향: 순위를 그대로 나열하지 말고, 1위와 마지막의 차이·같은 금액(공동 순위)·하루와 1경기로 바꾼 체감처럼 "
          "이 글에만 있는 계산을 앞에 둔다. 선수마다 한두 문장씩, 연봉 근거(계약·발표)를 풀어 쓴다."]
    return "\n".join(L)


def tags(d: dict) -> list[str]:
    s, lg = d["short_name"], d["sport"].split("(")[-1].rstrip(")").strip()
    out = [s, f"{s}연봉", f"{s}연봉순위", f"{lg}연봉", f"{str(d.get('season', ''))[:4]}{lg}", "연봉순위"]
    for r in d["rows"]:
        out += [r["short"], f"{r['short']}연봉"]
    return out


def suffix(d: dict, title: str) -> str:
    """추천 제목 뒤 검색어 괄호: '(2026 KBO 연봉 순위 · 양의지 고영표 최정)'."""
    words = f"{d.get('season', '')} {d['short_name']} 연봉 " + ("순위" if d["complete"] else "비교")
    names = " ".join(r["short"] for r in d["rows"][:3] if r["short"] not in title)
    return f"({words}" + (f" · {names}" if names else "") + ")"

