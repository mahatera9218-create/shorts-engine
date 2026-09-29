"""선수 몸값 영수증: 연봉을 경기·타수·안타·홈런 단위로 쪼개고, 영수증 그래픽과 홈판 썸네일을 만든다.

계산은 코드로 한다 (14.1). 입력은 posts/<글>/data.yaml, 출력은 같은 폴더의 numbers.json과
이미지 4장: thumb.png(홈판 카드), receipt.png(영수증), table.png(흰 바탕 표), season.png(실사 사진 + 시즌 기록).
사용법: BRAND_FONT_DIR=/path/to/fonts python -m content.receipt posts/<글>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFilter

from .brand import BG, GOLD, GRAY, WHITE, center_text, fit, font

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


def _paper_shadow(card: Image.Image, bg=(233, 230, 224), angle: float = -1.8, pad: int = 70) -> Image.Image:
    """종이를 책상 위에 올려놓고 찍은 것처럼: 옅은 그림자 + 살짝 기울임."""
    W, H = card.width + pad * 2, card.height + pad * 2
    out = Image.new("RGB", (W, H), bg)
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rectangle((pad + 10, pad + 16, pad + card.width + 10, pad + card.height + 16), fill=90)
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    out.paste(Image.new("RGB", (W, H), (150, 145, 138)), (0, 0), shadow)
    out.paste(card, (pad, pad))
    return out.rotate(angle, resample=Image.BICUBIC, fillcolor=bg)


def receipt_image(d: dict, n: dict, w: int = 1080) -> Image.Image:
    """진짜 감열지 영수증처럼: 흰 종이, 고정폭 글꼴, 점선, 합계, 바코드."""
    cw = int(w * 0.72)
    h = int(w * 1.5)
    card = Image.new("RGB", (cw, h), (252, 252, 249))
    dr = ImageDraw.Draw(card)
    ink, soft = (35, 35, 38), (110, 110, 115)
    m = int(cw * 0.07)
    f, fb = font("mono", int(cw * 0.042)), font("monob", int(cw * 0.042))
    y = int(cw * 0.08)
    center_text(dr, (cw / 2, y), "** 선수 몸값 영수증 **", font("monob", int(cw * 0.055)), ink)
    y += int(cw * 0.08)
    center_text(dr, (cw / 2, y), "억소리 나는 스포츠", f, soft)
    y += int(cw * 0.09)

    def rule(ch="-"):
        nonlocal y
        dr.text((m, y), ch * 40, font=f, fill=soft, anchor="lm")
        y += int(cw * 0.06)

    def row(left, right, bold=False, color=ink):
        nonlocal y
        dr.text((m, y), left, font=fb if bold else f, fill=color, anchor="lm")
        dr.text((cw - m, y), right, font=fb if bold else f, fill=color, anchor="rm")
        y += int(cw * 0.07)

    row("선수", d["player"])
    row("시즌", f"{d['season']}")
    rule()
    row("품목", "단가", bold=True)
    for u in units(d):
        row(f"{u['label']} x{u['count']:,}", won(n["per"][u["key"]]))
    rule()
    row("합계 (올해 연봉)", "약 " + won(n["salary_krw"]), bold=True, color=(180, 30, 30))
    if d.get("salary_usd"):
        row("", f"{d['salary_usd'] / 1e4:,.0f}만 달러", color=soft)
        row("환율", f"{d['fx_krw_per_usd']:,}원", color=soft)
    rule("=")
    head = headline(d)
    if n.get("min_wage_years_per", {}).get(head):
        label = next(u["label"] for u in units(d) if u["key"] == head)
        center_text(dr, (cw / 2, y), f"{label} = 최저임금 {n['min_wage_years_per'][head]:.1f}년치", fb, ink)
        y += int(cw * 0.09)
    x = m + int(cw * 0.08)  # 바코드 (장식)
    seed = sum(map(ord, d["player"]))
    while x < cw - m - int(cw * 0.08):
        bw = 2 + (seed * 7 + x) % 5
        dr.rectangle((x, y, x + bw, y + int(cw * 0.12)), fill=ink)
        x += bw + 3 + (seed + x) % 4
    y += int(cw * 0.17)
    center_text(dr, (cw / 2, y), "성적·연봉 보도 기준 · 감사합니다", font("mono", int(cw * 0.034)), soft)
    y += int(cw * 0.07)
    card = card.crop((0, 0, cw, y))
    return _paper_shadow(card)


RED = (214, 40, 40)


def short_won(x: float) -> str:
    """썸네일용: 가장 큰 단위만 (2억 32만 원 → 2억원, 9,045만 원 → 9,045만원)."""
    return won(x).split(" ")[0] + "원"


def _cover(photo: Image.Image, w: int) -> Image.Image:
    """사진을 정사각형으로 가운데 잘라 w×w로."""
    side = min(photo.size)
    left, top = (photo.width - side) // 2, (photo.height - side) // 2
    return photo.crop((left, top, left + side, top + side)).resize((w, w), Image.LANCZOS).convert("RGB")


def _shade(im: Image.Image, start: float = 0.3, strength: int = 235) -> Image.Image:
    """아래로 갈수록 어두워지는 그라데이션 (글자가 사진 위에서도 읽히게)."""
    w, h = im.size
    grad = Image.new("L", (1, h))
    for y in range(h):
        t = max(0.0, (y / h - start) / (1 - start))
        grad.putpixel((0, y), int(70 + (strength - 70) * min(1.0, t * 1.3)))
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, im, grad.resize((w, h)))


def thumb_image(d: dict, n: dict, w: int = 1080, photo: Image.Image | None = None) -> Image.Image:
    """홈판 카드: 실사 배경(없으면 남색) + 굵은 제목 글꼴 + 아주 큰 금액 + 최저임금 한 줄."""
    im = _shade(_cover(photo, w)) if photo is not None else Image.new("RGB", (w, w), BG)
    dr = ImageDraw.Draw(im)
    x0 = int(w * 0.07)
    stroke = {"stroke_width": int(w * 0.007), "stroke_fill": (0, 0, 0)}
    tag = f"{d['season']} 연봉 영수증"
    tf = font("display", int(w * 0.05))
    l, t, r, b = dr.textbbox((0, 0), tag, font=tf)
    dr.rectangle((x0, w * 0.07, x0 + (r - l) + w * 0.05, w * 0.07 + (b - t) + w * 0.045), fill=RED)
    dr.text((x0 + w * 0.025, w * 0.07 + w * 0.0225 - t), tag, font=tf, fill=WHITE)
    head = headline(d)
    label = next(u["label"] for u in units(d) if u["key"] == head)
    line1 = f"{d['player']} {label}"
    dr.text((x0, w * 0.52), line1, font=fit(dr, line1, "display", int(w * 0.1), w * 0.86), fill=WHITE, anchor="lm", **stroke)
    big = short_won(n["per"][head])
    dr.text((x0 - w * 0.005, w * 0.69), big, font=fit(dr, big, "display", int(w * 0.25), w * 0.88), fill=GOLD,
            anchor="lm", stroke_width=int(w * 0.01), stroke_fill=(0, 0, 0))
    years = n.get("min_wage_years_per", {}).get(head)
    line3 = f"최저임금 연봉 {years:.1f}년치" if years else f"올해 연봉 {won(n['salary_krw'])}"
    f3 = fit(dr, line3, "display", int(w * 0.065), w * 0.8)
    l, t, r, b = dr.textbbox((0, 0), line3, font=f3)
    y3 = int(w * 0.84)
    dr.rectangle((x0, y3, x0 + (r - l) + w * 0.04, y3 + (b - t) + w * 0.035), fill=RED)
    dr.text((x0 + w * 0.02, y3 + w * 0.0175 - t), line3, font=f3, fill=WHITE)
    return im


def table_image(d: dict, n: dict, w: int = 1080) -> Image.Image:
    """블로그에 흔한 흰 바탕 표: 기준 | 올 시즌 | 1번에 받는 돈 | 최저임금 비교. 제목 기록 줄은 형광펜."""
    head = headline(d)
    rows = [(u["label"], f"{u['count']:,}", won(n["per"][u["key"]]),
             f"{n['min_wage_years_per'][u['key']]:.1f}년치" if n.get("min_wage_years_per") else "-", u["key"] == head)
            for u in units(d)]
    cols = [0.22, 0.2, 0.32, 0.26]
    pad = int(w * 0.05)
    tw = w - 2 * pad
    rh = int(w * 0.095)
    top = int(w * 0.2)
    h = top + rh * (len(rows) + 1) + int(w * 0.12)
    im = Image.new("RGB", (w, h), (255, 255, 255))
    dr = ImageDraw.Draw(im)
    ink, soft, line = (30, 30, 30), (120, 120, 120), (215, 215, 215)
    title = f"{d['player']} 연봉, 쪼개 보면"
    dr.text((pad, w * 0.07), title, font=fit(dr, title, "xb", int(w * 0.058), tw), fill=ink, anchor="lm")
    sub = f"올해 연봉 약 {won(n['salary_krw'])}" + (f" · 최저임금 1년 {won(n['min_wage_yearly_krw'])}" if n.get("min_wage_yearly_krw") else "")
    dr.text((pad, w * 0.13), sub, font=fit(dr, sub, "r", int(w * 0.034), tw), fill=soft, anchor="lm")
    xs = [pad]
    for c in cols:
        xs.append(xs[-1] + tw * c)
    header = ["기준", "올 시즌", "1번에 받는 돈", "최저임금 비교"]
    dr.rectangle((pad, top, pad + tw, top + rh), fill=(244, 244, 244))
    for i, (label, cnt, money, yrs, hot) in enumerate(rows, 1):
        y = top + i * rh
        if hot:
            dr.rectangle((pad, y, pad + tw, y + rh), fill=(255, 241, 168))
    for i, cells in enumerate([header] + [r[:4] for r in rows]):
        y = top + i * rh
        for j, cell in enumerate(cells):
            wt = "b" if i == 0 or (i and rows[i - 1][4]) else "r"
            f = fit(dr, cell, wt, int(w * 0.038), tw * cols[j] * 0.9)
            center_text(dr, ((xs[j] + xs[j + 1]) / 2, y + rh / 2), cell, f, ink)
    for i in range(len(rows) + 2):
        dr.line((pad, top + i * rh, pad + tw, top + i * rh), fill=line if 0 < i < len(rows) + 1 else (120, 120, 120), width=2)
    for x in xs[1:-1]:
        dr.line((x, top, x, top + rh * (len(rows) + 1)), fill=line, width=2)
    note = "성적·연봉 보도 기준" + (f" · 1달러 {d['fx_krw_per_usd']:,}원" if d.get("fx_krw_per_usd") else "")
    dr.text((pad, top + rh * (len(rows) + 1) + w * 0.05), note, font=font("r", int(w * 0.03)), fill=soft, anchor="lm")
    return im


def season_image(d: dict, w: int = 1080, photo: Image.Image | None = None) -> Image.Image | None:
    """실사 사진 + 아래 흰 띠에 올 시즌 기록 한 줄 (블로그에 올린 사진처럼). 사진이 없으면 흰 띠만."""
    card = (d.get("card") or [])[:5]
    if not card:
        return None
    ph = int(w * 0.66) if photo is not None else 0
    strip = int(w * 0.2)
    im = Image.new("RGB", (w, ph + strip), (255, 255, 255))
    if photo is not None:
        side_w, side_h = photo.width, int(photo.width * ph / w)
        if side_h > photo.height:
            side_h, side_w = photo.height, int(photo.height * w / ph)
        left, top = (photo.width - side_w) // 2, (photo.height - side_h) // 2
        im.paste(photo.crop((left, top, left + side_w, top + side_h)).resize((w, ph), Image.LANCZOS).convert("RGB"), (0, 0))
    dr = ImageDraw.Draw(im)
    pad = int(w * 0.05)
    dr.text((pad, ph + strip * 0.32), f"{d['player']} {d['season']} 시즌", font=font("xb", int(w * 0.045)), fill=(30, 30, 30), anchor="lm")
    stats = "  ·  ".join(f"{c['label']} {c['value']}" for c in card)
    dr.text((pad, ph + strip * 0.68), stats, font=fit(dr, stats, "b", int(w * 0.036), w - 2 * pad), fill=(70, 70, 70), anchor="lm")
    if d.get("card_date"):
        dr.text((w - pad, ph + strip * 0.32), f"{d['card_date']} 보도 기준", font=font("r", int(w * 0.026)), fill=(140, 140, 140), anchor="rm")
    return im


def build(folder: Path, d: dict) -> dict:
    n = compute(d)
    (folder / "numbers.json").write_text(json.dumps(n, ensure_ascii=False, indent=1), encoding="utf-8")
    receipt_image(d, n).save(folder / "receipt.png")
    photo = Image.open(folder / "photo.jpg") if (folder / "photo.jpg").exists() else None
    thumb_image(d, n, photo=photo).save(folder / "thumb.png")
    photo2 = Image.open(folder / "photo2.jpg") if (folder / "photo2.jpg").exists() else None
    table_image(d, n).save(folder / "table.png")
    season = season_image(d, photo=photo2)
    if season is not None:
        season.save(folder / "season.png")
    (folder / "compare.png").unlink(missing_ok=True)  # 예전 막대그래프 (표로 바뀜)
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
