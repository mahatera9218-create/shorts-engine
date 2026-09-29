"""테마 (2026-09-29 대표 결정): 연봉 영수증 · 같은 종목 비교 · 다른 종목 비교 · 생활 물가 비교.

- 뽑기: config/players.yaml의 선수 풀과 테마 가중치대로 매일 무작위 (최근 글에 나온 선수는 뺀다)
- 계산·그림은 코드 (연봉·기록은 뉴스에서, 생활 물가는 config/prices.yaml의 확인된 값)
- 카드: 썸네일(1쪽) + 테마별 카드뉴스, 쪽 번호로 끝까지 넘기게
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image

from . import cards, receipt
from .brand import center_text, fit, font
from .cards import HL, INK, LINE, RED, SOFT, W, WHITE, _base, _highlight, _num, word
from .receipt import short_won, won

OLD = ("receipt.png", "table.png", "season.png", "compare.png")


def short(p: dict) -> str:
    return p.get("short") or p.get("short_name") or p["name"]


def count(x: float) -> str:
    """개수 표기는 버림 (올려서 부풀리지 않는다): 1.68 → 1.6, 23.9 → 23, 1234.5 → 1,234."""
    if x >= 10:
        return f"{int(x):,}"
    return f"{math.floor(x * 10) / 10:.1f}".removesuffix(".0")


def ratio(x: float) -> str:
    return f"{math.floor(x * 10) / 10:.1f}"


# ---------------------------------------------------------------- 뽑기

def plans(pool: dict, recent: set[str], seed: str, n: int = 6, override: str | None = None,
          theme: str | None = None) -> list[dict]:
    """오늘 시도할 (테마, 선수) 조합 후보 n개. 연봉 보도가 없는 선수가 있으면 다음 후보로 넘어간다."""
    rng = random.Random(seed)
    everyone = pool["players"]
    fresh = [p for p in everyone if p["name"] not in recent] or everyone
    themes = pool["themes"]

    def pick(cands, exclude=()):
        c = [p for p in cands if p["name"] not in exclude]
        return rng.choices(c, weights=[p.get("weight", 1) for p in c])[0] if c else None

    out, seen = [], set()
    for _ in range(n * 5):
        th = theme or rng.choices(list(themes), weights=[t["weight"] for t in themes.values()])[0]
        if override:
            a = next((p for p in everyone if override in (p["name"], p.get("short"))),
                     {"name": override, "sport": "kbo", "weight": 1})
        else:
            a = pick(fresh)
        ps = [a]
        if th in ("same", "cross"):
            b = pick([p for p in fresh if (p["sport"] == a["sport"]) == (th == "same")], {a["name"]})
            if not b:
                continue
            ps.append(b)
        key = (th, tuple(p["name"] for p in ps))
        if key in seen:
            continue
        seen.add(key)
        out.append({"theme": th, "players": ps})
        if len(out) >= n:
            break
    return out


def topic(pool: dict, p: dict) -> dict:
    """뉴스 수집·숫자 뽑기에 넘길 선수 정보."""
    s = pool["sports"].get(p["sport"], {"name": "", "sport": "야구", "hint": ""})
    money = "상금" if s["sport"] == "골프" else "연봉"
    return {"id": p["name"].replace(" ", ""), "player": p["name"], "short_name": short(p), "team": p.get("team", ""),
            "sport": f"{s['sport']} ({s['name']})", "hint": s.get("hint", ""),
            "queries": [f"{p['name']} {money}", f"{p['name']} 시즌 성적", f"{p['name']} 계약" if money == "연봉" else f"{p['name']} 우승"]}


def names_in(d: dict) -> list[str]:
    return [x for x in (d.get("player"), (d.get("a") or {}).get("player"), (d.get("b") or {}).get("player")) if x]


def title_name(d: dict) -> str:
    if d.get("theme") in ("same", "cross"):
        return f"{d['a'].get('short_name') or d['a']['player']} vs {d['b'].get('short_name') or d['b']['player']}"
    return d.get("short_name") or d["player"]


# ---------------------------------------------------------------- 계산 (코드)

def compute_vs(d: dict) -> dict:
    na, nb = receipt.compute(d["a"]), receipt.compute(d["b"])
    ka = {u["key"] for u in receipt.units(d["a"])}
    kb = {u["key"] for u in receipt.units(d["b"])}
    unit = "games" if "games" in ka and "games" in kb else None
    va = na["per"][unit] if unit else na["salary_krw"]
    vb = nb["per"][unit] if unit else nb["salary_krw"]
    win = "a" if va >= vb else "b"
    hi, lo = max(va, vb), min(va, vb)
    return {"a": na, "b": nb, "unit": unit, "unit_label": "1경기" if unit else "올해 연봉", "va": va, "vb": vb,
            "winner": win, "ratio": hi / lo if lo else 0,
            "salary_ratio": max(na["salary_krw"], nb["salary_krw"]) / max(1, min(na["salary_krw"], nb["salary_krw"])),
            "common": sorted((ka & kb) - {"games"})}


def compute_life(d: dict) -> dict:
    n = receipt.compute(d)
    keys = [u["key"] for u in receipt.units(d)]
    unit = "games" if "games" in keys else receipt.headline(d)
    per = n["per"][unit]
    label = next(u["label"] for u in receipt.units(d) if u["key"] == unit)
    items = [{**p, "salary_count": n["salary_krw"] / p["price_krw"], "unit_count": per / p["price_krw"]}
             for p in d["prices"]]
    return {**n, "life_unit": unit, "life_label": label, "life_per": per, "items": items}


def pick_prices(prices: dict, seed: str) -> list[dict]:
    """그룹별로 pick 수만큼, 검색량(weight)이 큰 것일수록 자주 뽑는다 (대표 결정: 많이 검색하는 동네·차종 위주)."""
    rng = random.Random(seed)
    out = []
    for group, k in (prices.get("pick") or {"home": 1, "car_kr": 1, "car_import": 1}).items():
        pool = [i for i in prices["items"] if i.get("group") == group]
        for _ in range(min(k, len(pool))):
            it = rng.choices(pool, weights=[max(1, i.get("weight", 1)) for i in pool])[0]
            pool.remove(it)
            out.append({x: it[x] for x in ("key", "group", "label", "short", "unit", "price_krw", "as_of", "source")})
    return out


def quiz_item(d: dict, n: dict) -> dict:
    """퀴즈는 국산차 (가장 체감되는 값). 없으면 첫 물건."""
    return next((i for i in n["items"] if i.get("group") == "car_kr"), n["items"][0])


# ---------------------------------------------------------------- 카드 (그림)

def _big_options(dr, labels: list[str], y0: int = 500):
    for i, t in enumerate(labels):
        y = y0 + i * 140
        dr.rounded_rectangle((170, y, W - 170, y + 110), radius=55, fill=WHITE, outline=LINE, width=3)
        _num(dr, (250, y + 55), i + 1)
        dr.text((W / 2 + 30, y + 55), t, font=fit(dr, t, "display", 56, W * 0.5), fill=INK, anchor="mm")


def _table(dr, rows: list[list[str]], cols: list[float], top: int, hot: set[int] = frozenset(), last_red: bool = False):
    pad, rh = 80, 96
    tw = W - 2 * pad
    xs = [pad]
    for c in cols:
        xs.append(xs[-1] + tw * c)
    for i, row in enumerate(rows):
        y = top + i * rh
        bg = (238, 234, 225) if i == 0 else (HL if i in hot else WHITE)
        if last_red and i == len(rows) - 1:
            bg = (255, 236, 236)
        dr.rectangle((pad, y, pad + tw, y + rh), fill=bg)
        for j, cell in enumerate(row):
            wt = "xb" if i == 0 or i in hot else "b"
            color = RED if last_red and i == len(rows) - 1 and j > 0 else INK
            center_text(dr, ((xs[j] + xs[j + 1]) / 2, y + rh / 2), cell, fit(dr, cell, wt, 38, tw * cols[j] * 0.9), color)
        dr.line((pad, y + rh, pad + tw, y + rh), fill=LINE, width=2)
    dr.rectangle((pad, top, pad + tw, top + rh * len(rows)), outline=(170, 165, 155), width=3)
    return top + rh * len(rows)


def build_vs(folder: Path, d: dict, photo: Image.Image | None) -> dict:
    n = compute_vs(d)
    A = d["a"].get("short_name") or d["a"]["player"]
    B = d["b"].get("short_name") or d["b"]["player"]
    total = 4
    imgs = {"thumb.png": receipt.poster(f"{d['season']} 연봉 대결", f"{A} vs {B}", "올해 연봉",
                                        f"{short_won(n['a']['salary_krw'])} vs {short_won(n['b']['salary_krw'])}", photo)}
    im, dr = _base(2, total)
    center_text(dr, (W / 2, 250), f"{n['unit_label']} 몸값,", font("display", 86), INK)
    center_text(dr, (W / 2, 360), "누가 더 비쌀까?", font("display", 86), INK)
    _big_options(dr, [A, B], 540)
    center_text(dr, (W / 2, 985), "정답은 아래에 ↓", font("b", 40), RED)
    imgs["card_quiz.png"] = im
    im, dr = _base(3, total)
    win, lose = (A, B) if n["winner"] == "a" else (B, A)
    vw, vl = (n["va"], n["vb"]) if n["winner"] == "a" else (n["vb"], n["va"])
    dr.text((W / 2 - 40, 230), "정답은", font=font("display", 70), fill=SOFT, anchor="rm")
    _num(dr, (W / 2 + 10, 232), 1 if n["winner"] == "a" else 2, r=44, color=RED)
    dr.text((W / 2 + 70, 230), "번", font=font("display", 70), fill=SOFT, anchor="lm")
    center_text(dr, (W / 2, 370), f"{win} {n['unit_label']}", fit(dr, f"{win} {n['unit_label']}", "display", 80, W * 0.86), INK)
    _highlight(dr, (W / 2, 510), won(vw), 150)
    line = f"{lose} {won(vl)}의 {ratio(n['ratio'])}배"
    center_text(dr, (W / 2, 700), line, fit(dr, line, "b", 46, W * 0.86), INK)
    imgs["card_answer.png"] = im
    im, dr = _base(4, total)
    center_text(dr, (W / 2, 190), f"한눈에 보는 {A} vs {B}", fit(dr, f"한눈에 보는 {A} vs {B}", "display", 64, W * 0.86), INK)
    rows = [["기준", A, B], ["올해 연봉", won(n["a"]["salary_krw"]), won(n["b"]["salary_krw"])]]
    hot = set()
    if n["unit"]:
        rows.append(["1경기", won(n["va"]), won(n["vb"])])
        hot.add(len(rows) - 1)
    for k in n["common"][:3]:
        lab = next(u["label"] for u in receipt.units(d["a"]) if u["key"] == k)
        rows.append([word(lab), won(n["a"]["per"][k]), won(n["b"]["per"][k])])
    if n["a"].get("min_wage_yearly_krw"):
        y = n["a"]["min_wage_yearly_krw"]
        rows.append(["최저임금으로", f"{count(n['a']['salary_krw'] / y)}년", f"{count(n['b']['salary_krw'] / y)}년"])
    end = _table(dr, rows, [0.3, 0.35, 0.35], 290, hot)
    note = "성적·연봉 보도 기준" + (f" · 환율 {d['a']['fx_krw_per_usd']:,}원" if d["a"].get("fx_krw_per_usd") else "")
    center_text(dr, (W / 2, end + 60), note, font("r", 28), SOFT)
    imgs["card_table.png"] = im
    _save(folder, imgs, n)
    return n


def build_life(folder: Path, d: dict, photo: Image.Image | None) -> dict:
    n = compute_life(d)
    name = d.get("short_name") or d["player"]
    apt = next((i for i in n["items"] if i.get("group") == "home"), n["items"][0])
    q = quiz_item(d, n)
    total = 5
    imgs = {"thumb.png": receipt.poster(f"{d['season']} 연봉 체감", name, "올해 연봉이면",
                                        f"{apt['short']} {count(apt['salary_count'])}{apt['unit']}", photo)}
    im, dr = _base(2, total)
    first = f"{name} {n['life_label']} 몸값이면"
    center_text(dr, (W / 2, 250), first, fit(dr, first, "display", 80, W * 0.86), INK)
    center_text(dr, (W / 2, 360), f"{q['short']} 몇 {q['unit']}?", font("display", 86), INK)
    opts, idx = cards.options(q["unit_count"], folder.name)
    _big_options(dr, [f"약 {count(v)}{q['unit']}" for v in opts])
    center_text(dr, (W / 2, 985), "정답은 아래에 ↓", font("b", 40), RED)
    imgs["card_quiz.png"] = im
    im, dr = _base(3, total)
    dr.text((W / 2 - 40, 260), "정답은", font=font("display", 70), fill=SOFT, anchor="rm")
    _num(dr, (W / 2 + 10, 262), idx + 1, r=44, color=RED)
    dr.text((W / 2 + 70, 260), "번", font=font("display", 70), fill=SOFT, anchor="lm")
    _highlight(dr, (W / 2, 470), f"{q['short']} {count(q['unit_count'])}{q['unit']}", 140)
    line = f"{n['life_label']} {won(n['life_per'])} ÷ {q['short']} {won(q['price_krw'])}"
    center_text(dr, (W / 2, 680), line, fit(dr, line, "b", 44, W * 0.86), INK)
    imgs["card_answer.png"] = im
    im, dr = _base(4, total)
    title = f"{name} 연봉으로 살 수 있는 것"
    center_text(dr, (W / 2, 190), title, fit(dr, title, "display", 64, W * 0.86), INK)
    rows = [["물건", "가격", "연봉으로", f"{word(n['life_label'])}로"]]
    rows += [[i["short"], won(i["price_krw"]), f"{count(i['salary_count'])}{i['unit']}",
              f"{count(i['unit_count'])}{i['unit']}"] for i in n["items"]]
    end = _table(dr, rows, [0.28, 0.28, 0.22, 0.22], 290, {1})
    center_text(dr, (W / 2, end + 60), "가격: 공식 발표·보도 기준 (본문 끝 출처)", font("r", 28), SOFT)
    imgs["card_items.png"] = im
    wage = cards.wage_card(n, n["life_unit"], 5, total)
    if wage is not None:
        imgs["card_wage.png"] = wage
    _save(folder, imgs, n)
    return n


def _save(folder: Path, imgs: dict, n: dict) -> None:
    (folder / "numbers.json").write_text(json.dumps(n, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for name, img in imgs.items():
        img.save(folder / name)
    for name in OLD + tuple(f for f in ("card_wage.png", "card_items.png") if f not in imgs):
        (folder / name).unlink(missing_ok=True)


def build(folder: Path, d: dict) -> dict:
    """테마에 맞게 썸네일과 카드를 그린다 (receipt는 기존 영수증 카드)."""
    photo = Image.open(folder / "photo.jpg") if (folder / "photo.jpg").exists() else None
    th = d.get("theme", "receipt")
    if th in ("same", "cross"):
        return build_vs(folder, d, photo)
    if th == "life":
        return build_life(folder, d, photo)
    return receipt.build(folder, d)


# ---------------------------------------------------------------- 글쓰기 안내 (이미지 자리)

IMAGE_PLANS = {
    "receipt": [
        ("첫문단아래", "thumb.png", "첫 문단 바로 아래 (홈판 카드와 같은 그림)"),
        ("퀴즈", "card_quiz.png", "단위별 금액을 말하기 전. 바로 앞 문장에서 '퀴즈 카드' 기록이 얼마일지 맞혀 보라고 묻는다"),
        ("정답", "card_answer.png", "퀴즈 바로 다음. 정답 카드보다 앞에서는 퀴즈 정답 금액을 쓰지 않는다"),
        ("최저임금", "card_wage.png", "최저임금 비교 문단 바로 위"),
        ("한눈에표", "card_table.png", "올 시즌 성적을 말하는 문단 바로 위")],
    "vs": [
        ("첫문단아래", "thumb.png", "첫 문단 바로 아래 (홈판 카드와 같은 그림)"),
        ("퀴즈", "card_quiz.png", "두 선수 소개 뒤. 바로 앞 문장에서 누가 더 받을지 맞혀 보라고 묻는다"),
        ("정답", "card_answer.png", "퀴즈 바로 다음. 정답 카드보다 앞에서는 누가 더 받는지 쓰지 않는다"),
        ("한눈에표", "card_table.png", "두 선수 기록을 나란히 말하는 문단 바로 위")],
    "life": [
        ("첫문단아래", "thumb.png", "첫 문단 바로 아래 (홈판 카드와 같은 그림)"),
        ("퀴즈", "card_quiz.png", "바로 앞 문장에서 '퀴즈 카드' 물건을 몇 대(채) 살 수 있을지 맞혀 보라고 묻는다"),
        ("정답", "card_answer.png", "퀴즈 바로 다음. 정답 카드보다 앞에서는 정답 숫자를 쓰지 않는다"),
        ("살수있는것", "card_items.png", "아파트·차값 비교 문단 바로 위"),
        ("최저임금", "card_wage.png", "최저임금 비교 문단 바로 위")],
}


def image_plan(theme: str) -> list[tuple[str, str, str]]:
    return IMAGE_PLANS["vs" if theme in ("same", "cross") else theme]


def image_lines(theme: str) -> list[str]:
    plan = image_plan(theme)
    return (["이미지 파일: " + ", ".join(f for _, f, _ in plan), "이미지 자리 (각각 한 줄로, 순서대로):"]
            + [f'  "[이미지 {i}_{lab}: {f}]" {where}' for i, (lab, f, where) in enumerate(plan, 1)])
