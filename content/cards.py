"""본문 카드뉴스 (2026-09-29 대표 선택): 퀴즈 → 정답 → 최저임금 체감 → 한눈에 표.

한 장에 메시지 하나, 밝은 바탕, 굵은 글꼴, 쪽 번호(2/5)로 끝까지 넘기게 한다.
썸네일(1/5)과 제목이 이미 제목 기록의 답을 보여주므로, 퀴즈는 다른 기록으로 낸다.
오답 보기는 코드가 정답의 몇 분의 1·몇 배로 만든다 (사실이 아닌 보기라 숫자 검사 대상이 아님).
"""
from __future__ import annotations

import hashlib
import math

from PIL import Image, ImageDraw

from .brand import center_text, fit, font

W = 1080
BG = (250, 247, 240)
INK = (24, 24, 28)
SOFT = (120, 118, 112)
HL = (255, 222, 89)
PINK = (255, 190, 190)
RED = (222, 52, 52)
BLUE = (40, 90, 200)
WHITE = (255, 255, 255)
LINE = (220, 215, 205)


def won(x: float) -> str:
    from .receipt import won as _won
    return _won(x)


def nice(x: float) -> float:
    """보기용 어림수: 유효숫자 2자리 (3,015만 → 3,000만, 2억 7,135만 → 2억 7,000만)."""
    if x <= 0:
        return 0
    p = 10 ** (int(math.log10(x)) - 1)
    return round(x / p) * p


def word(label: str) -> str:
    """'홈런 1개' → '홈런', '1이닝' → '이닝'."""
    return label.replace("1개", "").replace("1", "").strip()


def quiz_unit(d: dict, units: list[dict], per: dict, head: str) -> dict:
    """퀴즈는 제목 기록이 아닌 것 중 1번에 받는 돈이 가장 큰 기록으로."""
    others = [u for u in units if u["key"] != head] or units
    return max(others, key=lambda u: per[u["key"]])


def options(value: float, seed: str) -> tuple[list[float], int]:
    """보기 3개(작은 순)와 정답 위치. 정답 위치가 늘 가운데가 되지 않게 글마다 바꾼다."""
    pattern = int(hashlib.sha1(seed.encode()).hexdigest(), 16) % 3
    mult = [(1 / 3, 1, 3), (1, 3, 8), (1 / 8, 1 / 3, 1)][pattern]
    return [nice(value * m) for m in mult], mult.index(1)


def _base(page: int, total: int):
    im = Image.new("RGB", (W, W), BG)
    d = ImageDraw.Draw(im)
    d.text((70, 70), "억소리 나는 스포츠", font=font("b", 30), fill=SOFT, anchor="lm")
    d.text((W - 70, 70), f"{page}/{total}", font=font("b", 30), fill=SOFT, anchor="rm")
    return im, d


def _num(d, xy, n, r=38, color=BLUE):
    x, y = xy
    d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    d.text((x, y + 2), str(n), font=font("display", int(r * 1.15)), fill=WHITE, anchor="mm")


def _highlight(d, xy, text, size, color=HL, max_w=W * 0.86):
    f = fit(d, text, "display", size, max_w)
    l, t, r, b = d.textbbox(xy, text, font=f, anchor="mm")
    d.rectangle((l - 14, t + (b - t) * 0.45, r + 14, b + 8), fill=color)
    d.text(xy, text, font=f, fill=INK, anchor="mm")


def quiz_card(d: dict, q: dict, value: float, page: int, total: int, seed: str) -> Image.Image:
    im, dr = _base(page, total)
    first = f"{d.get('short_name') or d['player']} {q['label']},"
    center_text(dr, (W / 2, 250), first, fit(dr, first, "display", 86, W * 0.86), INK)
    center_text(dr, (W / 2, 360), "얼마짜리일까?", font("display", 86), INK)
    opts, _ = options(value, seed)
    for i, v in enumerate(opts):
        y = 500 + i * 140
        dr.rounded_rectangle((170, y, W - 170, y + 110), radius=55, fill=WHITE, outline=LINE, width=3)
        _num(dr, (250, y + 55), i + 1)
        t = "약 " + won(v)
        dr.text((W / 2 + 30, y + 55), t, font=fit(dr, t, "display", 56, W * 0.5), fill=INK, anchor="mm")
    center_text(dr, (W / 2, 985), "정답은 아래에 ↓", font("b", 40), RED)
    return im


def answer_card(d: dict, n: dict, q: dict, page: int, total: int, seed: str) -> Image.Image:
    im, dr = _base(page, total)
    _, idx = options(n["per"][q["key"]], seed)
    dr.text((W / 2 - 40, 260), "정답은", font=font("display", 70), fill=SOFT, anchor="rm")
    _num(dr, (W / 2 + 10, 262), idx + 1, r=44, color=RED)
    dr.text((W / 2 + 70, 260), "번", font=font("display", 70), fill=SOFT, anchor="lm")
    _highlight(dr, (W / 2, 470), won(n["per"][q["key"]]), 170)
    eok = won(n["salary_krw"]).split(" ")[0]
    line = f"올해 연봉 약 {eok} ÷ {word(q['label'])} {q['count']:,}"
    center_text(dr, (W / 2, 680), line, fit(dr, line, "b", 46, W * 0.86), INK)
    if d.get("salary_basis"):
        note = "※ " + d["salary_basis"]
        center_text(dr, (W / 2, 760), note, fit(dr, note, "r", 34, W * 0.86), SOFT)
    return im


def wage_card(n: dict, head: str, page: int, total: int) -> Image.Image | None:
    years = n.get("min_wage_years_per", {}).get(head)
    if not years:
        return None
    im, dr = _base(page, total)
    center_text(dr, (W / 2, 230), "최저임금으로 이 돈 벌려면?", font("display", 72), INK)
    _highlight(dr, (W / 2, 420), wage_text(years), 150, color=PINK)
    step = next(s for s in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 10 ** 9) if years / s <= 10)  # 칸은 10개까지
    boxes = min(10, math.ceil(years / step))
    gap = 18
    bw = min(150, (W - 160 - gap * (boxes - 1)) / boxes)
    x0 = (W - (boxes * bw + (boxes - 1) * gap)) / 2
    for i in range(boxes):
        x = x0 + i * (bw + gap)
        fill = max(0.0, min(1.0, years / step - i))
        dr.rounded_rectangle((x, 610, x + bw, 730), radius=18, outline=(200, 195, 185), width=3, fill=WHITE)
        if fill > 0:
            dr.rounded_rectangle((x, 610, x + bw * fill, 730), radius=18, fill=RED)
        lab = f"{(i + 1) * step}년" if step > 1 else f"{i + 1}년차"
        dr.text((x + bw / 2, 775), lab, font=font("b", 32 if bw > 110 else 26), fill=SOFT, anchor="mm")
    center_text(dr, (W / 2, 880), "주 40시간 꼬박 일해도 (최저임금 월 209시간 기준)", font("b", 38), INK)
    return im


def table_card(d: dict, n: dict, units: list[dict], head: str, page: int, total: int) -> Image.Image:
    im, dr = _base(page, total)
    title = f"한눈에 보는 {d.get('short_name') or d['player']} 영수증"
    center_text(dr, (W / 2, 190), title, fit(dr, title, "display", 64, W * 0.86), INK)
    pad, rh = 90, 100
    tw = W - 2 * pad
    cols = [0.34, 0.26, 0.40]
    xs = [pad]
    for c in cols:
        xs.append(xs[-1] + tw * c)
    top = 290
    rows = [("기준", "올 시즌", "1번에 받는 돈", False)] + [
        (word(u["label"]), f"{u['count']:,}", won(n["per"][u["key"]]), u["key"] == head) for u in units]
    rows.append(("올해 연봉", "", "약 " + won(n["salary_krw"]), False))
    for i, (a, b, c, hot) in enumerate(rows):
        y = top + i * rh
        bg = (238, 234, 225) if i == 0 else (HL if hot else WHITE)
        if i == len(rows) - 1:
            bg = (255, 236, 236)
        dr.rectangle((pad, y, pad + tw, y + rh), fill=bg)
        for j, cell in enumerate((a, b, c)):
            wt = "xb" if i == 0 or hot or i == len(rows) - 1 else "b"
            color = RED if i == len(rows) - 1 and j == 2 else INK
            center_text(dr, ((xs[j] + xs[j + 1]) / 2, y + rh / 2), cell, fit(dr, cell, wt, 40, tw * cols[j] * 0.9), color)
        dr.line((pad, y + rh, pad + tw, y + rh), fill=LINE, width=2)
    dr.rectangle((pad, top, pad + tw, top + rh * len(rows)), outline=(170, 165, 155), width=3)
    card = d.get("card") or []
    if card:
        stats = f"{d['season']} 시즌 · " + " · ".join(f"{c['label']} {c['value']}" for c in card[:5])
        center_text(dr, (W / 2, top + rh * len(rows) + 60), stats, fit(dr, stats, "b", 32, W * 0.86), SOFT)
    note = "성적·연봉 보도 기준" + (f" · 환율 {d['fx_krw_per_usd']:,}원" if d.get("fx_krw_per_usd") else "")
    center_text(dr, (W / 2, top + rh * len(rows) + 110), note, font("r", 28), SOFT)
    return im


def wage_text(years: float) -> str:
    y, m = int(years), round((years - int(years)) * 12)
    if m == 12:
        y, m = y + 1, 0
    return ((f"{y}년 " if y else "") + (f"{m}개월" if m or not y else "")).strip()


def story(d: dict, n: dict, units: list[dict], head: str, seed: str) -> dict:
    """클립 영상용 줄거리 (content/clip.py가 움직이는 화면으로 그린다). 카드와 같은 숫자만 쓴다."""
    name = d.get("short_name") or d["player"]
    q = quiz_unit(d, units, n["per"], head)
    opts, idx = options(n["per"][q["key"]], seed)
    rows = [[word(u["label"]), won(n["per"][u["key"]])] for u in units]
    years = n.get("min_wage_years_per", {}).get(head)
    return {"quiz": {"lines": [f"{name} {q['label']},", "얼마짜리일까?"], "options": ["약 " + won(v) for v in opts],
                     "answer": idx},
            "answer": {"big": won(n["per"][q["key"]]),
                       "line": f"올해 연봉 약 {won(n['salary_krw']).split(' ')[0]} ÷ {word(q['label'])} {q['count']:,}"},
            "table": {"title": f"{name} 1번에 받는 돈", "header": ["기준", "1번에"], "rows": rows,
                      "hot": [i for i, u in enumerate(units) if u["key"] == head]},
            "wage": {"title": "최저임금으로 이 돈 벌려면?", "big": wage_text(years)} if years else None}


def build_cards(d: dict, n: dict, units: list[dict], head: str, seed: str) -> dict[str, Image.Image]:
    """파일 이름 → 이미지. 썸네일이 1쪽, 카드가 2쪽부터."""
    q = quiz_unit(d, units, n["per"], head)
    has_wage = bool(n.get("min_wage_years_per", {}).get(head))
    total = 1 + 3 + (1 if has_wage else 0)
    out = {"card_quiz.png": quiz_card(d, q, n["per"][q["key"]], 2, total, seed),
           "card_answer.png": answer_card(d, n, q, 3, total, seed)}
    if has_wage:
        out["card_wage.png"] = wage_card(n, head, 4, total)
    out["card_table.png"] = table_card(d, n, units, head, total, total)
    return out
