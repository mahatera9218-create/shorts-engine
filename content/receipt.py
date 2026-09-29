"""선수 몸값 영수증: 연봉을 경기·타수·안타·홈런 단위로 쪼개고, 영수증 그래픽과 홈판 썸네일을 만든다.

계산은 코드로 한다 (14.1). 입력은 posts/<글>/data.yaml, 출력은 같은 폴더의 numbers.json·receipt.png·thumb.png.
사용법: BRAND_FONT_DIR=/path/to/fonts python -m content.receipt posts/<글>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from .brand import BG, GOLD, GRAY, WHITE, center_text, fit, font

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


def compute(d: dict) -> dict:
    salary = d["salary_usd"] * d["fx_krw_per_usd"]
    per = {key: salary / d["stats"][key] for key, _ in UNITS if d["stats"].get(key)}
    out = {"salary_krw": salary, "per": per, "per_team_game": salary / d["team_games"]}
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
    rows = [(f"{label} ({d['stats'][k]:,})", won(n["per"][k])) for k, label in UNITS if k in n["per"]]
    for left, right in rows:
        dr.text((px0 + 50, y), left, font=fl, fill=INK, anchor="lm")
        dr.text((px1 - 50, y), right, font=fr, fill=INK, anchor="rm")
        y += h * 0.07
    dash(y - h * 0.02)
    y += h * 0.04
    dr.text((px0 + 50, y), "올해 연봉", font=fr, fill=INK, anchor="lm")
    dr.text((px1 - 50, y), "약 " + won(n["salary_krw"]), font=font("xb", int(w * 0.05)), fill=(190, 40, 40), anchor="rm")
    y += h * 0.06
    if n.get("min_wage_years_per", {}).get("hits"):
        line = f"1안타 = 최저임금 연봉 {n['min_wage_years_per']['hits']:.1f}년치"
        center_text(dr, (cx, y), line, font("b", int(w * 0.04)), INK)
        y += h * 0.06
    dash(y - h * 0.02)
    y += h * 0.03
    center_text(dr, (cx, y), f"{d['salary_usd'] / 1e4:,.0f}만 달러 · {d['fx_label']}", font("r", int(w * 0.03)), (90, 90, 100))
    y += h * 0.04
    center_text(dr, (cx, y), "성적·연봉은 보도 기준 · 최저임금 월 209시간", font("r", int(w * 0.03)), (90, 90, 100))
    end = int(y + h * 0.05)
    dr.rectangle((px0, end, px1, h), fill=BG)
    for x in range(px0, px1, 24):  # 톱니 모양 아래 끝
        dr.polygon([(x, end), (x + 12, end + 14), (x + 24, end)], fill=PAPER)
    return im.crop((0, 0, w, min(h, end + int(h * 0.05))))


def thumb_image(d: dict, n: dict, w: int = 1080) -> Image.Image:
    im = Image.new("RGB", (w, w), BG)
    dr = ImageDraw.Draw(im)
    center_text(dr, (w / 2, w * 0.2), f"{d['player']} {d['season']} 연봉 영수증", fit(dr, f"{d['player']} {d['season']} 연봉 영수증", "b", int(w * 0.06), w * 0.85), WHITE)
    head = f"1안타 {won(n['per']['hits']).split(' ')[0]}"
    center_text(dr, (w / 2, w * 0.47), head, fit(dr, head, "xb", int(w * 0.2), w * 0.9), GOLD)
    sub = f"1경기 {won(n['per']['games'])} · 1홈런 {won(n['per']['home_runs'])}"
    center_text(dr, (w / 2, w * 0.72), sub, fit(dr, sub, "b", int(w * 0.05), w * 0.88), WHITE)
    center_text(dr, (w / 2, w * 0.86), "억소리 나는 스포츠", font("r", int(w * 0.035)), GRAY)
    return im


def main() -> None:
    folder = Path(sys.argv[1])
    d = yaml.safe_load((folder / "data.yaml").read_text(encoding="utf-8"))
    n = compute(d)
    (folder / "numbers.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
    receipt_image(d, n).save(folder / "receipt.png")
    thumb_image(d, n).save(folder / "thumb.png")
    print(json.dumps({k: won(v) for k, v in n["per"].items()} | {"연봉": won(n["salary_krw"]), "팀경기당": won(n["per_team_game"])}, ensure_ascii=False))
    for k, v in n.get("min_wage_years_per", {}).items():
        print(k, f"최저임금 연봉 {v:.1f}년치")


if __name__ == "__main__":
    main()
