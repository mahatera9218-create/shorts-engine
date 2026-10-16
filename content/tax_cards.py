"""세무 글용 도식(이미지) 생성기 — 숫자는 config/tax.yaml에서 읽어 코드로 정확히 그린다.

AI 이미지는 숫자를 틀리기 쉬워, 세율표·계산 예시처럼 숫자가 든 도식은 여기서 그린다(대표 결정 2026-10-15).
글꼴·색은 content/brand.py(블로그 브랜드 시스템)를 재사용한다. 출처·수치는 config/tax.yaml.

사용:
  python -m content.tax_cards                 # 샘플 2장을 reports/sample-cards/에 저장
  python -m content.tax_cards <과세표준원> <출력폴더>
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from .brand import BG, GOLD, GRAY, WHITE, center_text, font

ROOT = Path(__file__).resolve().parent.parent
CARD = (28, 32, 46)        # 표 카드 바탕(본문 BG보다 살짝 밝게)
ROW_ALT = (22, 26, 38)     # 줄무늬
LINE = (52, 58, 78)


def _cfg() -> dict:
    with open(ROOT / "config" / "tax.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def won_label(w: int) -> str:
    """원 금액을 '1억 5,000만원' 식 한글 라벨로."""
    if w <= 0:
        return "0원"
    eok, man = w // 100_000_000, (w % 100_000_000) // 10_000
    parts = []
    if eok:
        parts.append(f"{eok}억")
    if man:
        parts.append(f"{man:,}만")
    return (" ".join(parts) + "원") if parts else "0원"


def _bracket_rows(cfg: dict) -> list[tuple[str, str, str]]:
    """config brackets → (과세표준 범위, 세율, 누진공제) 문자열 줄."""
    rows, prev = [], 0
    for i, (upper, rate, deduct) in enumerate(cfg["brackets"]):
        pct = f"{round(rate * 100)}%"
        ded = won_label(deduct) if deduct else "—"
        if i == 0:
            rng = f"{won_label(upper)} 이하"
        elif upper is None:
            rng = f"{won_label(prev)} 초과"
        else:
            rng = f"{won_label(prev)} 초과 ~ {won_label(upper)}"
        rows.append((rng, pct, ded))
        prev = upper
    return rows


def rate_table_card(out: Path, year: str = "2026", w: int = 1080, h: int = 1080) -> Path:
    """종합소득세 8구간 세율표 카드."""
    cfg = _cfg()
    rows = _bracket_rows(cfg)
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    pad = int(w * 0.06)
    # 제목
    center_text(d, (w / 2, int(h * 0.09)), f"{year} 종합소득세 세율표", font("display", int(w * 0.055)), WHITE)
    center_text(d, (w / 2, int(h * 0.155)), "과세표준 구간별 세율 · 누진공제", font("mono", int(w * 0.03)), GOLD)
    # 표 영역
    top, bottom = int(h * 0.21), int(h * 0.9)
    n = len(rows) + 1  # 헤더 포함
    rh = (bottom - top) / n
    cols = [pad, int(w * 0.52), int(w * 0.74), w - pad]  # 과세표준 | 세율 | 누진공제 경계
    # 헤더
    d.rectangle((pad, top, w - pad, top + rh), fill=(38, 44, 62))
    heads = ["과세표준", "세율", "누진공제"]
    centers = [(cols[0] + cols[1]) / 2, (cols[1] + cols[2]) / 2, (cols[2] + cols[3]) / 2]
    for c, head in zip(centers, heads):
        center_text(d, (c, top + rh / 2), head, font("monob", int(w * 0.028)), GOLD)
    # 줄
    for i, (rng, pct, ded) in enumerate(rows):
        y0 = top + rh * (i + 1)
        if i % 2 == 0:
            d.rectangle((pad, y0, w - pad, y0 + rh), fill=ROW_ALT)
        # 과세표준(왼쪽 정렬·필요시 축소), 세율·누진공제(가운데)
        from .brand import fit
        f_rng = fit(d, rng, "mono", int(w * 0.026), cols[1] - cols[0] - 24)
        _, t, _, b = d.textbbox((0, 0), rng, font=f_rng)
        d.text((cols[0] + 16, y0 + rh / 2 - (b - t) / 2 - t), rng, font=f_rng, fill=WHITE)
        center_text(d, (centers[1], y0 + rh / 2), pct, font("display", int(w * 0.032)), GOLD)
        center_text(d, (centers[2], y0 + rh / 2), ded, font("mono", int(w * 0.024)), WHITE)
    # 격자 선
    d.rectangle((pad, top, w - pad, top + rh * n), outline=LINE, width=2)
    for c in cols[1:3]:
        d.line((c, top, c, top + rh * n), fill=LINE, width=2)
    # 출처
    center_text(d, (w / 2, int(h * 0.955)), f"출처: 국세청 · {year}년 기준", font("mono", int(w * 0.022)), GRAY)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def _calc(base: int, cfg: dict) -> dict:
    """과세표준 base에 대한 산출세액·지방소득세 (코드 계산, 정확)."""
    for upper, rate, deduct in cfg["brackets"]:
        if upper is None or base <= upper:
            tax = round(base * rate - deduct)
            local = round(tax * cfg["local_rate"])
            return {"rate": rate, "deduct": deduct, "tax": tax, "local": local, "total": tax + local}
    raise ValueError(base)


def calc_card(out: Path, base: int, w: int = 1080, h: int = 720) -> Path:
    """과세표준 → 산출세액 계산 예시 카드 (지방소득세 포함)."""
    cfg = _cfg()
    r = _calc(base, cfg)
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    center_text(d, (w / 2, int(h * 0.13)), "종합소득세 계산 예시", font("display", int(w * 0.05)), WHITE)
    center_text(d, (w / 2, int(h * 0.30)), f"과세표준 {won_label(base)}", font("display", int(w * 0.06)), GOLD)
    line = f"{won_label(base)} × {round(r['rate']*100)}% - {won_label(r['deduct'])}"
    from .brand import fit
    center_text(d, (w / 2, int(h * 0.46)), line, fit(d, line, "mono", int(w * 0.036), w * 0.86), WHITE)
    center_text(d, (w / 2, int(h * 0.60)), f"산출세액 = {won_label(r['tax'])}", font("display", int(w * 0.05)), WHITE)
    sub = f"+ 지방소득세(10%) {won_label(r['local'])}  →  총 약 {won_label(r['total'])}"
    center_text(d, (w / 2, int(h * 0.74)), sub, fit(d, sub, "mono", int(w * 0.03), w * 0.9), GOLD)
    center_text(d, (w / 2, int(h * 0.92)), "출처: 국세청 · 2026년 기준 · 공제 전 가정 예시", font("mono", int(w * 0.02)), GRAY)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


def _wrap(d: ImageDraw.ImageDraw, text: str, f, max_w: float) -> list[str]:
    """한글 제목을 폭에 맞춰 줄바꿈(글자 단위, 공백 우선)."""
    lines: list[str] = []
    cur = ""
    for ch in text:
        trial = cur + ch
        if d.textlength(trial, font=f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def cover_card(out: Path, title: str, w: int = 1200, h: int = 630) -> Path:
    """글 제목을 브랜드(남색·금색)로 그린 대표 이미지/썸네일. 저작권 0, 글자만 정확히."""
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    pad = 84
    d.text((pad, 74), "Yield Briefing", font=font("b", 40), fill=GOLD)
    d.rectangle((pad, 140, pad + 128, 150), fill=GOLD)
    size = 76
    f = font("xb", size)
    lines = _wrap(d, title.strip(), f, w - 2 * pad)
    while len(lines) > 3 and size > 46:
        size -= 6
        f = font("xb", size)
        lines = _wrap(d, title.strip(), f, w - 2 * pad)
    lh = size * 1.32
    y = (h - lh * len(lines)) / 2 + 36
    for ln in lines:
        d.text((pad, y), ln, font=f, fill=WHITE)
        y += lh
    d.text((pad, h - 86), "재테크·세금·연금 정보", font=font("b", 30), fill=GRAY)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, "PNG")
    return out


def main() -> None:
    args = sys.argv[1:]
    out_dir = ROOT / "reports" / "sample-cards"
    base = 60_000_000
    if args:
        base = int(args[0])
    if len(args) > 1:
        out_dir = Path(args[1])
    t = rate_table_card(out_dir / "sodeukse-yulpyo-2026.png")
    c = calc_card(out_dir / f"sodeukse-gyesan-{base//10000}man.png", base)
    print("저장:", t, c)


if __name__ == "__main__":
    main()
