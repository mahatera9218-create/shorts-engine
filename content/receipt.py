"""선수 몸값 영수증: 연봉을 경기·타수·안타·홈런 단위로 쪼개고, 홈판 썸네일과 본문 카드뉴스를 만든다.

계산은 코드로 한다 (14.1). 입력은 posts/<글>/data.yaml, 출력은 같은 폴더의 numbers.json과
이미지: thumb.png(홈판 카드, 1쪽) + card_quiz·card_answer·card_wage·card_table.png (content/cards.py).
사용법: BRAND_FONT_DIR=/path/to/fonts python -m content.receipt posts/<글>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from .brand import BG, GOLD, WHITE, fit, font
from .cards import build_cards

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


RED = (214, 40, 40)


def short_won(x: float) -> str:
    """썸네일용: 가장 큰 단위만 (2억 32만 원 → 2억원, 9,045만 원 → 9,045만원)."""
    return won(x).split(" ")[0] + "원"


def _cover(photo: Image.Image, w: int) -> Image.Image:
    """사진을 정사각형으로 가운데 잘라 w×w로."""
    side = min(photo.size)
    left, top = (photo.width - side) // 2, (photo.height - side) // 2
    return photo.crop((left, top, left + side, top + side)).resize((w, w), Image.LANCZOS).convert("RGB")


def _shade(im: Image.Image) -> Image.Image:
    """위(선수 이름)와 아래(금액)가 읽히게 위·아래를 어둡게, 가운데는 사진이 보이게."""
    w, h = im.size
    grad = Image.new("L", (1, h))
    for y in range(h):
        t = y / h
        top = max(0.0, 0.45 - t) / 0.45       # 위쪽 45%: 아래로 갈수록 옅어짐
        bottom = max(0.0, t - 0.45) / 0.55    # 아래쪽 55%: 아래로 갈수록 짙어짐
        grad.putpixel((0, y), int(80 + 120 * top + 160 * min(1.0, bottom * 1.2)))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, im, grad.resize((w, h)))


def thumb_image(d: dict, n: dict, w: int = 1080, photo: Image.Image | None = None) -> Image.Image:
    """홈판 카드: 선수 이름이 가장 크게(맨 위) → 기록 → 아주 큰 금액 → 최저임금 한 줄. 배경은 실사(없으면 남색)."""
    im = _shade(_cover(photo, w)) if photo is not None else Image.new("RGB", (w, w), BG)
    dr = ImageDraw.Draw(im)
    x0 = int(w * 0.07)
    tag = f"{d['season']} 연봉 영수증"
    tf = font("display", int(w * 0.045))
    l, t, r, b = dr.textbbox((0, 0), tag, font=tf)
    dr.rectangle((x0, w * 0.06, x0 + (r - l) + w * 0.05, w * 0.06 + (b - t) + w * 0.04), fill=RED)
    dr.text((x0 + w * 0.025, w * 0.06 + w * 0.02 - t), tag, font=tf, fill=WHITE)
    name = d["player"]
    dr.text((x0 - w * 0.005, w * 0.28), name, font=fit(dr, name, "display", int(w * 0.2), w * 0.88), fill=WHITE,
            anchor="lm", stroke_width=int(w * 0.012), stroke_fill=(0, 0, 0))
    head = headline(d)
    label = next(u["label"] for u in units(d) if u["key"] == head)
    dr.text((x0, w * 0.5), label, font=font("display", int(w * 0.085)), fill=WHITE, anchor="lm",
            stroke_width=int(w * 0.007), stroke_fill=(0, 0, 0))
    big = short_won(n["per"][head])
    dr.text((x0 - w * 0.005, w * 0.665), big, font=fit(dr, big, "display", int(w * 0.22), w * 0.88), fill=GOLD,
            anchor="lm", stroke_width=int(w * 0.01), stroke_fill=(0, 0, 0))
    years = n.get("min_wage_years_per", {}).get(head)
    line3 = f"최저임금 연봉 {years:.1f}년치" if years else f"올해 연봉 {won(n['salary_krw'])}"
    f3 = fit(dr, line3, "display", int(w * 0.06), w * 0.8)
    l, t, r, b = dr.textbbox((0, 0), line3, font=f3)
    y3 = int(w * 0.845)
    dr.rectangle((x0, y3, x0 + (r - l) + w * 0.04, y3 + (b - t) + w * 0.035), fill=RED)
    dr.text((x0 + w * 0.02, y3 + w * 0.0175 - t), line3, font=f3, fill=WHITE)
    return im


OLD_IMAGES = ("receipt.png", "table.png", "season.png", "compare.png")  # 예전 형식 (카드뉴스로 바뀜)


def build(folder: Path, d: dict) -> dict:
    """numbers.json + 썸네일 + 카드뉴스 4장."""
    n = compute(d)
    (folder / "numbers.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
    photo = Image.open(folder / "photo.jpg") if (folder / "photo.jpg").exists() else None
    thumb_image(d, n, photo=photo).save(folder / "thumb.png")
    for name, img in build_cards(d, n, units(d), headline(d), folder.name).items():
        img.save(folder / name)
    for name in OLD_IMAGES:
        (folder / name).unlink(missing_ok=True)
    return n


def main() -> None:
    folder = Path(sys.argv[1])
    d = yaml.safe_load((folder / "data.yaml").read_text(encoding="utf-8"))
    if "--photo" in sys.argv and not (folder / "photo.jpg").exists():  # 사진 새로 받기 (PEXELS_API_KEY 필요)
        from .photos import fetch
        fetch(folder, d.get("sport", "야구"), folder.name)
    n = build(folder, d)
    print(json.dumps({k: won(v) for k, v in n["per"].items()} | {"연봉": won(n["salary_krw"])}, ensure_ascii=False))
    for k, v in n.get("min_wage_years_per", {}).items():
        print(k, f"최저임금 연봉 {v:.1f}년치")


if __name__ == "__main__":
    main()
