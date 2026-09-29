"""선수 몸값 영수증: 연봉을 경기·타수·안타·홈런 단위로 쪼개고, 영수증 그래픽과 홈판 썸네일을 만든다.

계산은 코드로 한다 (14.1). 입력은 posts/<글>/data.yaml, 출력은 같은 폴더의 numbers.json과
이미지 4장: thumb.png(홈판 카드), receipt.png(영수증), compare.png(최저임금 비교), season.png(시즌 성적 카드).
사용법: BRAND_FONT_DIR=/path/to/fonts python -m content.receipt posts/<글>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from .brand import BG, GOLD, GRAY, WHITE, center_text, fit, font
from .sportsart import icon

PAPER = (250, 247, 238)
INK = (30, 32, 40)
UNITS = [("games", "1경기"), ("at_bats", "1타수"), ("hits", "1안타"), ("home_runs", "1홈런")]


def won(x: float) -> str:
    """사람이 읽는 금액: 1억 이상은 'X억 Y만 원', 그 아래는 'Y만 원'."""
    x = round(x)
    eok, man = divmod(x, 100_000_000)
    man = round(man / 10_000)
    if man == 10_000:
        eok, man = eok + 1, 0
    if eok and man:
        return f"{eok:,}억 {man:,}만 원"
    if eok:
        return f"{eok:,}억 원"
    return f"{man:,}만 원"


def units(d: dict) -> list[dict]:
    """쪼갤 단위 목록. 새 형식은 units: [{key, label, count}], 예전 형식(stats)은 타자 4단위로 바꾼다."""
    if d.get("units"):
        return [u for u in d["units"] if u.get("count")]
    return [{"key": k, "label": label, "count": d["stats"][k]} for k, label in UNITS if d["stats"].get(k)]


def effective_count(u: dict) -> float:
    """야구 이닝 표기 85.2 = 85와 2/3이닝. 이닝 단위만 소수 첫째 자리를 1/3로 바꾼다."""
    c = u["count"]
    if "inning" in u["key"]:
        whole = int(c)
        return whole + round((c - whole) * 10) / 3
    return c


def salary_krw(d: dict) -> float:
    return d["salary_krw"] if d.get("salary_krw") else d["salary_usd"] * d["fx_krw_per_usd"]


def headline(d: dict) -> str:
    keys = [u["key"] for u in units(d)]
    return d.get("headline_unit") if d.get("headline_unit") in keys else ("hits" if "hits" in keys else keys[-1])


def compute(d: dict) -> dict:
    salary = salary_krw(d)
    per = {u["key"]: salary / effective_count(u) for u in units(d)}
    out = {"salary_krw": salary, "per": per}
    if d.get("team_games"):
        out["per_team_game"] = salary / d["team_games"]
    if d.get("min_wage_monthly_krw"):
        yearly = d["min_wage_monthly_krw"] * 12
        out["min_wage_yearly_krw"] = yearly
        out["min_wage_years_per"] = {k: v / yearly for k, v in per.items()}
    return out


def receipt_image(d: dict, n: dict, w: int = 1080) -> Image.Image:
    h = int(w * 1.3)
    im = Image.new("RGB", (w, h), BG)
    dr = ImageDraw.Draw(im)
    px0, px1, py0, py1 = int(w * 0.12), int(w * 0.88), int(h * 0.06), int(h * 0.94)
    dr.rectangle((px0, py0, px1, py1), fill=PAPER)
    cx = w / 2
    y = py0 + h * 0.06
    center_text(dr, (cx, y), "선수 몸값 영수증", font("xb", int(w * 0.06)), INK)
    y += h * 0.05
    center_text(dr, (cx, y), f"{d['player']} · {d['season']} 시즌", font("b", int(w * 0.04)), INK)
    y += h * 0.045

    def dash(yy):
        for x in range(px0 + 30, px1 - 30, 22):
            dr.line((x, yy, x + 11, yy), fill=GRAY, width=3)

    dash(y)
    y += h * 0.05
    fl, fr = font("b", int(w * 0.045)), font("xb", int(w * 0.045))
    rows = [(f"{u['label']} ({u['count']:,})", won(n["per"][u["key"]])) for u in units(d)]
    for left, right in rows:
        dr.text((px0 + 50, y), left, font=fl, fill=INK, anchor="lm")
        dr.text((px1 - 50, y), right, font=fr, fill=INK, anchor="rm")
        y += h * 0.07
    dash(y - h * 0.02)
    y += h * 0.04
    dr.text((px0 + 50, y), "올해 연봉", font=fr, fill=INK, anchor="lm")
    dr.text((px1 - 50, y), "약 " + won(n["salary_krw"]), font=font("xb", int(w * 0.05)), fill=(190, 40, 40), anchor="rm")
    y += h * 0.06
    head = headline(d)
    if n.get("min_wage_years_per", {}).get(head):
        label = next(u["label"] for u in units(d) if u["key"] == head)
        line = f"{label} = 최저임금 연봉 {n['min_wage_years_per'][head]:.1f}년치"
        center_text(dr, (cx, y), line, font("b", int(w * 0.04)), INK)
        y += h * 0.06
    dash(y - h * 0.02)
    y += h * 0.03
    basis = f"{d['salary_usd'] / 1e4:,.0f}만 달러 · {d['fx_label']}" if d.get("salary_usd") else d.get("salary_label", "연봉 보도 기준")
    center_text(dr, (cx, y), basis, font("r", int(w * 0.03)), (90, 90, 100))
    y += h * 0.04
    center_text(dr, (cx, y), "성적·연봉은 보도 기준 · 최저임금 월 209시간", font("r", int(w * 0.03)), (90, 90, 100))
    end = int(y + h * 0.05)
    dr.rectangle((px0, end, px1, h), fill=BG)
    for x in range(px0, px1, 24):  # 톱니 모양 아래 끝
        dr.polygon([(x, end), (x + 12, end + 14), (x + 24, end)], fill=PAPER)
    return im.crop((0, 0, w, min(h, end + int(h * 0.05))))


RED = (214, 40, 40)
TILE = (28, 33, 48)


def short_won(x: float) -> str:
    """썸네일용: 가장 큰 단위만 (2억 32만 원 → 2억원, 9,045만 원 → 9,045만원)."""
    return won(x).split(" ")[0] + "원"


def thumb_image(d: dict, n: dict, w: int = 1080) -> Image.Image:
    """홈판 카드: 종목 아이콘 + 선수 이름 + 아주 큰 금액 + 빨간 띠(최저임금 비교)."""
    im = Image.new("RGB", (w, w), BG)
    ball = icon(d.get("sport", "야구"), int(w * 0.56)).rotate(18, resample=Image.BICUBIC)
    im.paste(ball, (int(w * 0.6), int(-w * 0.12)), ball)
    dr = ImageDraw.Draw(im)
    tag = f"{d['season']} 연봉 영수증"
    tf = font("xb", int(w * 0.045))
    l, t, r, b = dr.textbbox((0, 0), tag, font=tf)
    x0, y0 = int(w * 0.07), int(w * 0.08)
    dr.rectangle((x0, y0, x0 + (r - l) + w * 0.05, y0 + (b - t) + w * 0.04), fill=RED)
    dr.text((x0 + w * 0.025, y0 + w * 0.02 - t), tag, font=tf, fill=WHITE)
    name = d["player"]
    dr.text((x0, y0 + w * 0.2), name, font=fit(dr, name, "xb", int(w * 0.12), w * 0.5), fill=WHITE, anchor="lm")
    head = headline(d)
    label = next(u["label"] for u in units(d) if u["key"] == head)
    dr.text((x0, w * 0.45), label, font=font("xb", int(w * 0.085)), fill=WHITE, anchor="lm")
    big = short_won(n["per"][head])
    bf = fit(dr, big, "xb", int(w * 0.26), w * 0.88)
    dr.text((x0 - w * 0.01, w * 0.62), big, font=bf, fill=GOLD, anchor="lm", stroke_width=int(w * 0.008), stroke_fill=(0, 0, 0))
    band_y = int(w * 0.8)
    dr.rectangle((0, band_y, w, w), fill=RED)
    years = n.get("min_wage_years_per", {}).get(head)
    line = f"= 최저임금 연봉 {years:.1f}년치" if years else f"올해 연봉 {won(n['salary_krw'])}"
    center_text(dr, (w / 2, band_y + (w - band_y) * 0.42), line, fit(dr, line, "xb", int(w * 0.075), w * 0.9), WHITE)
    center_text(dr, (w / 2, band_y + (w - band_y) * 0.82), "억소리 나는 스포츠", font("b", int(w * 0.03)), (255, 215, 215))
    return im


def compare_image(d: dict, n: dict, w: int = 1080) -> Image.Image | None:
    """단위별 금액을 최저임금 연봉 몇 년치인지 막대로. 한 계열이라 한 색, 값은 막대 끝에 직접 표시."""
    years = n.get("min_wage_years_per")
    if not years:
        return None
    rows = sorted(((u["label"], years[u["key"]]) for u in units(d)), key=lambda x: -x[1])
    bar_h, gap = int(w * 0.06), int(w * 0.04)
    top = int(w * 0.3)
    h = top + len(rows) * (bar_h + gap) + int(w * 0.14)
    im = Image.new("RGB", (w, h), BG)
    dr = ImageDraw.Draw(im)
    dr.text((w * 0.07, w * 0.09), "최저임금으로 치면 몇 년치?", font=font("xb", int(w * 0.058)), fill=WHITE, anchor="lm")
    sub = f"{d['player']} {d['season']} · 최저임금 1년 = {won(n['min_wage_yearly_krw'])}"
    dr.text((w * 0.07, w * 0.16), sub, font=fit(dr, sub, "r", int(w * 0.034), w * 0.86), fill=GRAY, anchor="lm")
    lf, vf = font("b", int(w * 0.04)), font("xb", int(w * 0.042))
    widest = max(dr.textlength(f"{v:.1f}년", font=vf) for _, v in rows)
    x0, x1 = int(w * 0.3), int(w * 0.95 - widest - w * 0.02)  # 가장 긴 막대 끝의 값 글자까지 화면 안에
    scale = (x1 - x0) / max(max(v for _, v in rows), 1.2)
    ref = x0 + scale  # 1년 기준선
    for i in range(len(rows) + 1):  # 기준선은 막대 사이 빈칸에만 그어 값 글자와 겹치지 않게
        ys = top - int(w * 0.03) if i == 0 else top + i * (bar_h + gap) - gap
        for y in range(ys, ys + (int(w * 0.03) if i == 0 else gap), 14):
            dr.line((ref, y, ref, y + 7), fill=(90, 96, 112), width=2)
    dr.text((ref, top - int(w * 0.05)), "1년", font=font("b", int(w * 0.028)), fill=GRAY, anchor="mm")
    for i, (label, v) in enumerate(rows):
        y = top + i * (bar_h + gap)
        dr.text((x0 - w * 0.03, y + bar_h / 2), label, font=lf, fill=WHITE, anchor="rm")
        end = x0 + max(v * scale, 6)
        dr.rounded_rectangle((x0, y, end, y + bar_h), radius=8, fill=GOLD)
        dr.rectangle((x0, y, min(x0 + 8, end), y + bar_h), fill=GOLD)  # 기준선 쪽은 각지게
        dr.text((end + w * 0.02, y + bar_h / 2), f"{v:.1f}년", font=vf, fill=WHITE, anchor="lm")
    dr.text((w * 0.93, h - w * 0.05), "억소리 나는 스포츠", font=font("r", int(w * 0.028)), fill=GRAY, anchor="rm")
    return im


def season_image(d: dict, w: int = 1080) -> Image.Image | None:
    """올 시즌 성적 카드: 큰 숫자 타일 (차트가 아니라 숫자 자체가 주인공)."""
    card = d.get("card") or []
    if not card:
        return None
    card = card[:6]
    cols = 2 if len(card) > 3 else len(card)
    rows = -(-len(card) // cols)
    pad, gap = int(w * 0.07), int(w * 0.03)
    tw = (w - 2 * pad - (cols - 1) * gap) / cols
    th = int(w * 0.24)
    top = int(w * 0.25)
    h = top + rows * (th + gap) + int(w * 0.1)
    im = Image.new("RGB", (w, h), BG)
    dr = ImageDraw.Draw(im)
    ball = icon(d.get("sport", "야구"), int(w * 0.12))
    im.paste(ball, (int(w - pad - w * 0.12), int(w * 0.06)), ball)
    dr.text((pad, w * 0.09), f"{d['player']} {d['season']} 시즌", font=fit(dr, f"{d['player']} {d['season']} 시즌", "xb", int(w * 0.058), w * 0.7), fill=WHITE, anchor="lm")
    dr.text((pad, w * 0.16), f"보도 기준 · {d.get('card_date', '')}".rstrip(" ·"), font=font("r", int(w * 0.032)), fill=GRAY, anchor="lm")
    for i, c in enumerate(card):
        x = pad + (i % cols) * (tw + gap)
        y = top + (i // cols) * (th + gap)
        dr.rounded_rectangle((x, y, x + tw, y + th), radius=18, fill=TILE)
        val = str(c["value"])
        center_text(dr, (x + tw / 2, y + th * 0.42), val, fit(dr, val, "xb", int(w * 0.1), tw * 0.85), GOLD if i == 0 else WHITE)
        center_text(dr, (x + tw / 2, y + th * 0.78), c["label"], fit(dr, c["label"], "b", int(w * 0.038), tw * 0.85), GRAY)
    return im


def build(folder: Path, d: dict) -> dict:
    n = compute(d)
    (folder / "numbers.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
    receipt_image(d, n).save(folder / "receipt.png")
    thumb_image(d, n).save(folder / "thumb.png")
    for name, img in (("compare.png", compare_image(d, n)), ("season.png", season_image(d))):
        if img is not None:
            img.save(folder / name)
    return n


def main() -> None:
    folder = Path(sys.argv[1])
    d = yaml.safe_load((folder / "data.yaml").read_text(encoding="utf-8"))
    n = build(folder, d)
    print(json.dumps({k: won(v) for k, v in n["per"].items()} | {"연봉": won(n["salary_krw"])}, ensure_ascii=False))
    for k, v in n.get("min_wage_years_per", {}).items():
        print(k, f"최저임금 연봉 {v:.1f}년치")


if __name__ == "__main__":
    main()
