"""유튜브 쇼츠 전용 영상 A·B·C (대표 결정 2026-09-30, reports/2026-09-30-쇼츠-스타일-분석.md).

네이버 클립(1인 1주제 체감형)과 따로, 쇼츠 벤치마크에서 잘 된 형식을 매일 한 편씩 만든다. Claude를 쓰지 않는다(계산은 코드).
도입부에서 답을 주지 않는다 (대표 지적 2026-09-30): 첫 화면은 질문, 답은 맨 끝.
- A. 통장형 (약 25초): 오늘 ✅ 후보 글의 확인된 숫자로 "{선수} {기록} 1번에 얼마?" → 하루·월급·연봉… 작은 돈부터 → 답은 끝
- B. 비교형 (약 20초): 확인 연봉표(config/salaries.yaml)로 "누가 더?" → 한쪽씩 공개 → 막대 "N배"는 끝
- C. 순위 카운트다운 (약 9초): 확인 연봉표 순위, 첫 화면은 가린 칸(???) → 꼴찌부터 공개, 1위는 맨 끝 → 처음으로 이어짐

결과: shorts/<날짜>-<A|B|C>-<주제>/ video.mp4 · meta.txt(첫 줄 제목, 나머지 설명) · data.yaml
- 숫자는 모두 확인된 값(글의 facts, 연봉표)과 코드 계산. 달러는 오늘 글에서 뽑은 환율(3일 안)로만 원화 환산, 없으면 달러로 둔다.
- 선수 사진·경기 화면은 쓰지 않는다 (등판 그림만). 소리는 무음, 음악은 유튜브 앱에서.
- 같은 주제(B·C)는 사용 기록(shorts/log.yaml)을 보고 가장 오래전에 쓴 것부터 돌린다.
사용법: python -m content.shorts [--date YYYY-MM-DD] [--only A|B|C]
"""
from __future__ import annotations

import argparse
import math
import shutil
from datetime import date, timedelta
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from market.common import ROOT, load_yaml
from . import clip, jersey, mark
from .clip import (BG, FPS, GOLD, GRAY, GREEN, H, PANEL, RED, W, WHITE, Scene, clamp, ease_back, ease_out, label, pill,
                   put)
from .receipt import won
from .themes import count

OUT = ROOT / "shorts"
LOG = OUT / "log.yaml"
POSTS = ROOT / "posts"
KEEP_DAYS = 3  # 쇼츠 폴더는 최근 3일만 둔다 (올리는 건 대표가 앱으로, 기록은 log.yaml)
SEASON_GAMES = {"kbo": 144, "nba": 82, "mlb": 162}  # 정규시즌 경기 수 (리그 공식 일정)
BLOG = clip.BLOG


# ---------------------------------------------------------------- 자료

def salary_table(fx: float | None) -> list[dict]:
    """확인 연봉표 → [{name, short, sport, team, krw|None, usd|None, basis, source}]. 원화 금액은 환율이 있을 때만."""
    pool = {p["name"]: p for p in load_yaml("players.yaml")["players"]}
    out = []
    for name, s in load_yaml("salaries.yaml")["players"].items():
        p = pool.get(name, {})
        usd = s["amount"] if s["currency"] == "USD" else None
        krw = s["amount"] if s["currency"] == "KRW" else (usd * fx if usd and fx else None)
        out.append({"name": name, "short": p.get("short") or name.split(" ")[0], "sport": p.get("sport", ""),
                    "team": p.get("team", ""), "krw": krw, "usd": usd, "basis": s["basis"], "source": s["source"]})
    return out


def latest_fx(today: str) -> tuple[float | None, str]:
    """오늘 글에서 뽑은 원·달러 환율 (3일 안). 없으면 None."""
    best = (None, "")
    for f in sorted(POSTS.glob("*/data.yaml")) if POSTS.exists() else []:
        if f.parent.name[:10] < str(date.fromisoformat(today) - timedelta(days=3)):
            continue
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if d.get("fx_krw_per_usd") and d.get("fx_label"):
            best = (float(d["fx_krw_per_usd"]), d["fx_label"])
    return best


def used_log() -> list[dict]:
    return (yaml.safe_load(LOG.read_text(encoding="utf-8")) or []) if LOG.exists() else []


def pick(options: list[dict], kind: str) -> dict | None:
    """가장 오래전에 쓴(또는 안 쓴) 주제."""
    last = {x["key"]: x["date"] for x in used_log() if x["kind"] == kind}
    return min(options, key=lambda o: last.get(o["key"], "0000")) if options else None


def money(x: dict) -> str:
    return won(x["krw"]) if x["krw"] else f"{x['usd']:,.0f}달러"


# ---------------------------------------------------------------- 장면 (쇼츠 전용: 빠른 컷, 큰 글자, 움직이는 배경)

BG_MOVE = None


def bg(c, t):
    global BG_MOVE
    if clip.VIDEO:  # 실사 배경 영상 위에 그릴 때는 줄무늬를 칠하지 않는다
        return
    if BG_MOVE is None:
        BG_MOVE = Image.new("RGBA", (W + 240, H), BG + (255,))
        d = ImageDraw.Draw(BG_MOVE)
        for i in range(-H, W + H + 240, 120):
            d.line((i, 0, i + H, H), fill=(24, 29, 46, 255), width=40)
    off = int(t * 50) % 120
    c.paste(BG_MOVE.crop((off, 0, off + W, H)), (0, 0))


class Title(Scene):
    """첫 장면 = 쇼츠 표지. 처음부터 다 보이고 살짝 튄다."""

    def __init__(self, tag: str, lines: list[str], players: list[str] = (), dur: float = 2.2,
                 pics: list[Image.Image] = (), credit: str = "", say: str | None = None):
        self.tag, self.lines, self.dur, self.credit = tag, lines, dur, credit
        if pics:  # 선수 사진(위키미디어 자유 이용)이 있으면 등판 대신
            from .playerphoto import card
            js = [card(x, 540 if len(pics) < 2 else 400) for x in pics]
            self.js = list(zip(js, (-3, 3) if len(js) > 1 else (0,)))
        else:
            js = jersey.for_players(list(players), 520 if len(players) < 2 else 420)
            self.js = list(zip(js, (-5, 6) if len(js) > 1 else (-4,)))
        self.say = " ".join(lines) + "." if say is None else say

    def draw(self, c, t):
        bg(c, t)
        tag = label(self.tag, "display", 54, WHITE)
        box = Image.new("RGBA", (tag.width + 50, tag.height + 30), RED + (255,))
        box.alpha_composite(tag, (25, 15))
        put(c, box, W / 2, 330, 1.08 - 0.08 * ease_out(t / 0.2))
        xs = [W / 2] if len(self.js) == 1 else [W * 0.3, W * 0.7]
        for (j, rot), x in zip(self.js, xs):
            put(c, j.rotate(rot + 4 * math.sin(t * 2.4), resample=Image.BICUBIC, expand=True), x, 680)
        y = 1080 if self.js else 820
        if self.credit:
            put(c, label(self.credit, "r", 26, GRAY), W / 2, 975, 1, 0.8)
        for i, line in enumerate(self.lines):
            col = GOLD if i == len(self.lines) - 1 else WHITE
            put(c, label(line, "display", 118 if i == 0 else 104, col, 10), W / 2, y + i * 150,
                1 + 0.06 * math.sin(math.pi * clamp((t - 0.3 - i * 0.1) / 0.3)))


class Counter(Scene):
    """한 줄 질문 → 금액이 0부터 굴러 올라가 멈춘다 (통장에 꽂히는 느낌)."""
    dur = 3.2

    def __init__(self, top: str, value: float, sub: str = ""):
        self.top, self.value, self.sub = top, value, sub
        self.say = f"{top} {won(value)}." + (f" {sub}." if sub and "나눈" not in sub else "")
        self.sfx = [("ding", 1.55, 0.5)]

    def draw(self, c, t):
        bg(c, t)
        put(c, label(self.top, "display", 96, WHITE, 8), W / 2, 780, 1.15 - 0.15 * ease_out(t / 0.2))
        k = 0.15 + 0.85 * ease_out((t - 0.25) / 1.3)  # 0원부터가 아니라 조금 채운 데서 굴러 올라간다
        shown = won(self.value * k) if k < 0.999 else won(self.value)
        put(c, label(shown, "display", 150, GOLD, 10), W / 2, 1000, 1 + (0.12 * math.sin(math.pi * clamp((t - 1.55) / 0.3))))
        if 1.55 < t < 1.7:
            c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(90 * (1 - (t - 1.55) / 0.15)))))
        if self.sub:
            put(c, label(self.sub, "b", 56, GRAY), W / 2, 1180, 1, clamp((t - 1.7) / 0.3))


class Bars(Scene):
    """두 쪽 막대 대결: 막대가 자라고 끝에 'N배' 도장."""
    dur = 5.0

    def __init__(self, left: dict, right: dict, times: str):
        self.l, self.r, self.times = left, right, times
        self.say = f"{left['name']} {left['label']}, {right['name']} {right['label']}. 무려 {times}."
        self.sfx = [("boom", 2.2, 0.6)]

    def draw(self, c, t):
        bg(c, t)
        mx = max(self.l["v"], self.r["v"])
        for i, s in enumerate((self.l, self.r)):
            y = 640 + i * 360
            put(c, label(s["name"], "display", 76, WHITE), 90, y, anchor="l")
            k = ease_out((t - 0.3 - i * 0.2) / 1.4)
            w = max(8, int((W - 180) * s["v"] / mx * k))
            put(c, pill(w, 110, (GOLD if s["v"] == mx else GREEN) + (255,)), 90, y + 120, anchor="l")
            put(c, label(s["label"], "b", 54, WHITE), 90, y + 240, 1, clamp((t - 1.6) / 0.3), anchor="l")
        s = 1.6 - 0.6 * ease_back((t - 2.2) / 0.35)
        put(c, label(self.times, "display", 150, RED, 10), W / 2, 1420, s, clamp((t - 2.2) / 0.1))


class Board(Scene):
    """순위표 카운트다운: 첫 프레임은 제목 + 가린 칸(???) (표지), 꼴찌부터 한 줄씩 공개, 1위는 맨 끝에 번쩍.
    (대표 지적 2026-09-30: 처음부터 다 보이면 볼 이유가 없다)"""
    STEP, START, HOLD = 1.1, 0.9, 1.8

    def __init__(self, title: str, sub: str, rows: list[tuple[str, str]], dur: float | None = None):
        self.title, self.sub, self.rows = title, sub, rows
        self.dur = dur or self.START + self.STEP * len(rows) + self.HOLD
        self.say = f"{title}. " + ", ".join(f"{i + 1}위 {n} {v}" for i, (n, v) in reversed(list(enumerate(rows)))) + "."

    def shown_at(self, i: int) -> float:
        return self.START + self.STEP * (len(self.rows) - 1 - i)

    def draw(self, c, t):
        bg(c, t)
        put(c, label(self.title, "display", 92, WHITE, 8), W / 2, 340)
        put(c, label(self.sub, "b", 44, GRAY), W / 2, 440)
        top = 560
        step = min(150, 900 // max(1, len(self.rows)))
        for i, (name, val) in enumerate(self.rows):
            y = top + i * step
            t0 = self.shown_at(i)
            open_ = t >= t0
            glow = 1 + (0.12 if i == 0 else 0.06) * math.sin(math.pi * clamp((t - t0) / 0.3)) if open_ else 1
            put(c, pill(W - 120, step - 20, PANEL + (255,)), 60, y + step / 2, anchor="l")
            put(c, label(f"{i + 1}", "display", 64, GOLD if i == 0 else GRAY), 120, y + step / 2)
            put(c, label(name if open_ else "???", "b", 60, WHITE if open_ else GRAY, max_w=460), 200, y + step / 2, anchor="l")
            v = label(val if open_ else "???", "display", 64, (GOLD if i == 0 else WHITE) if open_ else GRAY, max_w=420)
            put(c, v, W - 90 - v.width * glow, y + step / 2, glow, anchor="l")
        if self.rows and 0 <= t - self.shown_at(0) < 0.15:  # 1위 공개 번쩍
            c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(100 * (1 - (t - self.shown_at(0)) / 0.15)))))


class Ask(Scene):
    """끝: 댓글 질문 + 구독 한 줄."""
    dur = 2.4

    def __init__(self, q: str):
        self.q = q
        self.say = f"{q} 댓글로 알려 주세요."

    def draw(self, c, t):
        bg(c, t)
        for i, (txt, w, s, col) in enumerate([(self.q, "display", 100, WHITE), ("댓글로 알려주세요", "b", 58, GOLD),
                                              ("구독하면 매일 새 몸값", "b", 46, GRAY)]):
            k = ease_out((t - i * 0.12) / 0.3)
            put(c, label(txt, w, s, col, 8 if i == 0 else 0), W / 2, 820 + i * 150 + 40 * (1 - k), 1, k)


class Banner(Scene):
    """모든 장면 위쪽에 제목을 고정한다 (대표 요청 2026-09-30): 유튜브가 영상 중간 장면을 썸네일로 골라도,
    피드에서 어느 순간에 봐도 무슨 영상인지 보이게. 첫 장면(Title)에는 제목이 이미 크게 있어 겹치지 않게 뺀다."""

    def __init__(self, scene: Scene, text: str):
        self.scene, self.dur = scene, scene.dur
        self.say, self.sfx = getattr(scene, "say", None), getattr(scene, "sfx", [])
        words, lines, cur = text.split(), [], ""
        for w in words:  # 두 줄로 나눈다 (한 줄이 너무 길면)
            if cur and len(cur) + len(w) + 1 > max(10, len(text) // 2 + 2):
                lines.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
        lines.append(cur)
        ims = [label(x, "display", 70, WHITE if i == 0 else GOLD, 6, max_w=int(W * 0.86)) for i, x in enumerate(lines[:2])]
        h = sum(im.height for im in ims) + 20 * (len(ims) - 1) + 50
        box = pill(int(W * 0.92), h, (10, 12, 20, 215))
        box = Image.new("RGBA", box.size, (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle((0, 0, box.width - 1, h - 1), radius=36, fill=(10, 12, 20, 215))
        y = 25
        for im in ims:
            box.alpha_composite(im, ((box.width - im.width) // 2, y))
            y += im.height + 20
        self.box = box

    def draw(self, c, t):
        self.scene.draw(c, t)
        put(c, self.box, W / 2, 190 + self.box.height / 2)


def with_banner(sc: list[Scene], text: str) -> list[Scene]:
    return [s if isinstance(s, (Title, Board)) else Banner(s, text) for s in sc]


# ---------------------------------------------------------------- A · B · C

def plan_a(today: str) -> dict | None:
    """오늘 ✅ 후보 글(생활 물가·연고지·여행·유니폼·영수증: 기록 단위가 있는 글) 중 하나로 통장형."""
    for f in sorted(POSTS.glob(f"{today}-*/data.yaml")) if POSTS.exists() else []:
        post = (f.parent / "post.md").read_text(encoding="utf-8")
        if "✅ 자동 검사 통과" not in post or mark.status(f.parent).get("status") == "rejected":
            continue
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        sal = d.get("salary_krw") or (d.get("salary_usd", 0) * d.get("fx_krw_per_usd", 0))
        units = [u for u in d.get("units", []) if u.get("count")]
        if not sal or len(units) < 2 or " vs " in d.get("player", ""):
            continue
        name = d.get("short_name") or d["player"]
        if not domestic(d["player"], "kbo" if "프로야구" in str(d.get("sport", "")) else ""):
            continue  # A는 국내 선수만 (해외 선수는 B에서 국내 기준과 비교)
        key = f"A-{name}"
        if any(x["key"] == key and x["date"] >= str(date.fromisoformat(today) - timedelta(days=30)) for x in used_log()):
            continue
        head = d.get("headline_unit")
        pick_u = [u for u in units if u["key"] == "games"][:1] + [u for u in units if u["key"] == head and u["key"] != "games"]
        pick_u += [u for u in units if u not in pick_u][:3 - len(pick_u)]
        per = [(u["label"], sal / u["count"]) for u in pick_u]
        wage_year = d.get("min_wage_monthly_krw", 0) * 12
        head_lab = per[1][0] if len(per) > 1 else per[0][0]  # 질문 = 대표 기록 1번에 얼마 (끝에서 공개)
        return {"kind": "A", "key": key, "name": name, "player": d["player"], "salary": sal, "per": per,
                "head": head_lab, "wage_year": wage_year, "source": f.parent.name, "fx_label": d.get("fx_label", ""),
                "title": f"{name} {head_lab}에 버는 돈, 얼마?"}
    return None


def _josa(name: str, a: str, b: str) -> str:
    """받침 있으면 a(이·은), 없으면 b(가·는)."""
    ch = name[-1]
    if "가" <= ch <= "힣":
        return a if (ord(ch) - 0xAC00) % 28 else b
    return b


def domestic(name: str, sport: str = "") -> bool:
    """국내 선수 = KBO 선수 또는 한국 선수(해외파 포함). 해외 선수 = 해외 리그의 외국 선수 (이름에 띄어쓰기: 오타니 쇼헤이)."""
    return sport == "kbo" or (" " not in name and len(name) <= 4)


def options_b(table: list[dict]) -> list[dict]:
    """해외 선수 1명 vs 국내 기준 (대표 결정 2026-09-30: 쇼츠는 국내 2 + 해외 1, 비교는 국내 시청자 체감용으로 국내 선수 기준).
    확인 연봉표의 해외 스타(NBA·MLB 외국 선수) × 국내 기준(KBO 1위, KBO TOP 5 합계, 한국인 메이저리거)."""
    has = [x for x in table if x["krw"]]
    kbo = sorted((x for x in has if x["sport"] == "kbo"), key=lambda x: -x["krw"])
    stars = sorted((x for x in has if x["sport"] in ("nba", "mlb") and not domestic(x["name"], x["sport"])
                    and x["name"] != "오타니 쇼헤이"),  # 오타니는 연봉 대부분이 지급 유예라 '올해 받는 돈' 비교가 오해를 부른다
                   key=lambda x: -x["krw"])
    kor_mlb = sorted((x for x in has if x["sport"] == "mlb" and domestic(x["name"], x["sport"])), key=lambda x: -x["krw"])
    out = []
    for s in stars:
        slug = s["short"].replace(" ", "")
        if kbo:
            out.append({"key": f"B-kbo1-{slug}", "left": [kbo[0]], "right": [s],
                        "title": f"KBO 연봉 1위 vs {s['short']}", "q": "이 차이, 납득 되나요?"})
        if len(kbo) >= 5:
            out.append({"key": f"B-kbo5-{slug}", "left": kbo[:5], "right": [s], "ln": "KBO 연봉 TOP 5 합계",
                        "title": f"KBO 연봉 TOP 5 합계 vs {s['short']}", "q": "누가 더 받아야 할까요?"})
        if kor_mlb:
            k = kor_mlb[0]
            out.append({"key": f"B-{k['short']}-{slug}", "left": [k], "right": [s],
                        "title": f"{k['short']} vs {s['short']}", "q": "몇 배일 것 같았나요?"})
    return out


def options_c(table: list[dict]) -> list[dict]:
    """국내 선수 순위표 × 단위 (연봉·월급·1경기·하루)."""
    lists = []
    kbo = sorted((x for x in table if x["sport"] == "kbo" and x["krw"]), key=lambda x: -x["krw"])[:5]
    if len(kbo) >= 5:
        lists.append(("kbo", "2026 KBO 연봉 TOP 5", kbo))
    kor = sorted((x for x in table if x["sport"] == "mlb" and x["krw"] and domestic(x["name"], "mlb")), key=lambda x: -x["krw"])
    if len(kor) >= 3:  # 국내 선수만 (대표 결정 2026-09-30): 해외 리그 목록은 B(해외 vs 국내)에서만
        lists.append(("mlb", f"한국인 메이저리거 연봉 TOP {len(kor)}", kor))
    units = [("year", "연봉", 1), ("month", "월급으로 치면", 12), ("day", "하루에 버는 돈", 365)]
    out = []
    for lk, title, rows in lists:
        for uk, un, div in units + [("game", "1경기에 버는 돈", SEASON_GAMES.get(lk, 0))]:
            if div:
                out.append({"key": f"C-{lk}-{uk}", "title": title if uk == "year" else f"{title.split(' TOP')[0]} TOP {len(rows)} {un}",
                            "unit": un, "div": div, "rows": rows, "league": lk})
    return out


def pics_for(folder: Path | None, names: list[str]) -> tuple[list[Image.Image], str]:
    """선수 사진 (위키미디어 자유 이용) + 화면 출처 한 줄. folder가 없으면(시험) 사진 없이."""
    if folder is None:
        return [], ""
    from . import playerphoto
    import json as _json
    pics = playerphoto.fetch(folder, names)
    credit = " · ".join(f"사진 {i['artist'][:20]} ({i['license']})" for i in
                        (_json.loads(f.read_text(encoding="utf-8")) for f in sorted(folder.glob("player*.json"))))
    return pics, credit


def build(kind: str, today: str, folder: Path | None = None) -> tuple[dict, list[Scene]] | None:
    fx, fx_label = latest_fx(today)
    table = salary_table(fx)
    if kind == "A":
        p = plan_a(today)
        if not p:
            return None
        pics, cr = pics_for(folder, [p["player"]])
        # 도입부에서 답을 주지 않는다 (대표 지적 2026-09-30): 질문(대표 기록 1번에 얼마?) → 작은 돈부터 쌓아 올리고 → 답은 맨 끝
        steps = [("하루에", p["salary"] / 365, "쉬는 날까지 365일로 나눈 값"), ("월급으로 치면", p["salary"] / 12, "12로 나눈 값"),
                 ("올해 연봉", p["salary"], "1년 동안 들어오는 돈")]
        steps += [(f"{lab}에", v, "") for lab, v in p["per"] if lab != p["head"] and lab == "1경기"]  # 너무 길지 않게 (약 20초)
        sc = [Title("통장 체크", [p["name"], f"{p['head']}에 얼마?"], [p["player"]], 2.2, pics, cr)]
        sc += [Counter(a, v, sub) for a, v, sub in sorted(steps, key=lambda x: x[1])]
        v = dict(p["per"])[p["head"]]
        yrs = v / p["wage_year"] if p["wage_year"] else 0
        sc.append(Counter(f"그래서 {p['head']}에", v, f"최저임금으로 {count(yrs)}년 일해야 버는 돈" if yrs >= 0.1 else ""))
        sc.append(Ask("이 몸값, 적당한가요?"))
        p["q"] = "이 몸값, 적당한가요?"
        p["basis"] = f"오늘 글({p['source']})의 확인된 연봉·기록으로 계산" + (f", 환율 {p['fx_label']}" if p["fx_label"] else "")
        sc = with_banner(sc, p["title"])
        return p, sc + [clip.LoopBack(sc[-1], sc[0])]
    if kind == "B":
        o = pick(options_b(table), "B")
        if not o:
            return None
        lv, rv = sum(x["krw"] for x in o["left"]), sum(x["krw"] for x in o["right"])
        ln = o.get("ln") or o["left"][0]["short"]
        rn = o.get("rn") or o["right"][0]["short"]
        big, small = max(lv, rv), min(lv, rv)
        times = f"{count(big / small)}배"
        players = ([o["left"][0]["name"]] if len(o["left"]) == 1 else []) + [o["right"][0]["name"]]  # 합계 쪽은 한 사람 얼굴을 쓰지 않는다
        pics, cr = pics_for(folder, players)
        # 도입부에서 답을 주지 않는다 (대표 지적 2026-09-30): 누가 더? → 한쪽씩 공개 → 몇 배는 맨 끝 막대에서
        sc = [Title("연봉 대결", [o["title"].split(" vs ")[0], f"vs {o['title'].split(' vs ')[1]}" if " vs " in o["title"]
                               else f"vs {rn} 1명", "누가 더 받을까?"], players, 2.2, pics, cr,
                    say=o["title"].replace(" vs ", " 대 ") + ", 누가 더 받을까요?"),
              Counter(ln, lv, f"{len(o['left'])}명 연봉 합계" if len(o["left"]) > 1 else "올해 연봉"),
              Counter(rn, rv, "올해 연봉"),
              Bars({"name": ln, "v": lv, "label": won(lv)}, {"name": rn, "v": rv, "label": won(rv)}, times),
              Ask(o["q"])]
        o |= {"kind": "B", "q": o["q"], "times": times, "lv": lv, "rv": rv,
              "basis": "확인 연봉표(config/salaries.yaml, 발표·보도)" + (f", 환율 {fx_label}" if fx_label else ""),
              "names": [x["name"] for x in o["left"] + o["right"]]}
        sc = with_banner(sc, meta_text(o | {"kind": "B"}).split("\n")[0])
        return o, sc + [clip.LoopBack(sc[-1], sc[0])]
    if kind == "C":
        opts = [o for o in options_c(table)]
        o = pick(opts, "C")
        if not o:
            return None
        rows = [(x["short"], won(x["krw"] / o["div"])) for x in o["rows"]]
        sub = "2026 연봉 기준" + (" · 달러는 " + fx_label if o["league"] != "kbo" and fx_label else "")
        board = Board(o["title"], sub, rows)
        o |= {"kind": "C", "q": "1위 예상했나요?", "basis": "확인 연봉표(config/salaries.yaml, 발표·보도)" + (f", 환율 {fx_label}" if fx_label else ""),
              "names": [x["name"] for x in o["rows"]]}
        return o, [board, clip.LoopBack(board, board)]
    return None


def meta_text(p: dict) -> str:
    """meta.txt: 첫 줄 제목(20자대), 나머지 설명(질문 + 계산 기준 + 블로그 이름 + 해시태그)."""
    title = p["title"] if p["kind"] != "B" else p["title"] + (" 몇 배?" if p["title"].endswith("합쳐도") else "")
    names = p.get("names") or [p.get("player", "")]
    tags = ["#" + n.replace(" ", "") for n in names[:4] if n] + ["#연봉", "#몸값", "#shorts"]
    desc = [f"{p['q']} 댓글로 알려주세요.", f"기준: {p['basis']}.", f"계산 과정은 네이버 블로그 '{BLOG}'에서.", " ".join(tags)]
    return f"{title}\n" + "\n\n".join(desc) + "\n"


def folder_of(x: dict) -> str:
    """로그 항목 → 쇼츠 폴더 이름."""
    return x.get("folder") or f"{x['date']}-{x['kind']}-{x['key'].split('-', 1)[1].replace(' ', '')}"


def pending(kind: str) -> list[str]:
    """아직 올리지 않은 쇼츠 폴더 (대표 결정 2026-09-30: 올림 처리가 안 되면 그 형식은 새로 만들지 않는다)."""
    done = {folder_of(x) for x in used_log() if x.get("video_id") or x.get("discarded")}
    return [f.name for f in sorted(OUT.glob(f"*-{kind}-*")) if f.is_dir() and (f / "video.mp4").exists()
            and "-preview-" not in f.name and f.name not in done]


def cleanup(today: str) -> list[str]:
    """올린(또는 버린) 쇼츠 폴더와 지난 미리보기를 지운다. 올리지 않은 쇼츠는 남겨 둔다 (기록은 log.yaml)."""
    done = {folder_of(x) for x in used_log() if x.get("video_id") or x.get("discarded")}
    gone = []
    for f in (x for x in OUT.iterdir() if x.is_dir()) if OUT.exists() else []:
        old_preview = "-preview-" in f.name and f.name[:10] < today
        if f.name in done or old_preview or f.name.startswith(".work"):
            shutil.rmtree(f)
            gone.append(f.name)
    return gone


def discard(name: str) -> str:
    """도우미 '이 쇼츠 버리기' 버튼: 폴더를 지우고 기록에 버림 표시 (그 형식이 다시 만들어진다)."""
    log = used_log()
    hit = [x for x in log if folder_of(x) == name]
    for x in hit:
        x["discarded"] = True
    if hit:
        LOG.write_text(yaml.safe_dump(log, allow_unicode=True, sort_keys=False), encoding="utf-8")
    shutil.rmtree(OUT / name, ignore_errors=True)
    return f"버림: {name}" if hit else f"기록에 없는 폴더: {name}"


SPORT_OF = {"kbo": "야구", "mlb": "야구", "nba": "농구", "golf": "골프", "epl": "축구", "laliga": "축구", "soccer": "축구"}


def make(kind: str, today: str, preview: bool = False) -> str:
    from . import produce
    exe = clip.ffmpeg()
    if not exe:
        return f"{kind}: ffmpeg 없음"
    work = OUT / f".work-{kind}"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    got = build(kind, today, work)
    if not got:
        shutil.rmtree(work, ignore_errors=True)
        return f"{kind}: 만들 재료 없음 (건너뜀)"
    p, sc = got
    slug = p["key"].split("-", 1)[1].replace(" ", "")
    folder = OUT / f"{today}-{kind}-{'preview-' if preview else ''}{slug}"  # 미리보기는 기록에 남기지 않는다
    shutil.rmtree(folder, ignore_errors=True)
    work.rename(folder)
    sport = next((SPORT_OF[x["sport"]] for x in p.get("left", []) + p.get("rows", []) if x.get("sport") in SPORT_OF), None) \
        or str(p.get("sport") or "야구")
    bg = produce.bg_video(folder, sport, folder.name)  # A. 실사 배경
    err, info = produce.produce(exe, sc, folder / "video.mp4", bg)  # B·D. 효과음·목소리
    if err:
        return f"{kind}: 영상 실패 ({err})"
    meta = meta_text(p)
    extra = produce.credits(folder) + (["※ 이 영상의 목소리는 AI 음성입니다."] if info["voice"] else [])
    title, _, desc = meta.partition("\n")
    if preview:
        title = "[미리보기 · 올리지 마세요] " + title
    (folder / "meta.txt").write_text(f"{title}\n" + "\n\n".join([desc.strip()] + extra) + "\n", encoding="utf-8")
    (folder / "bg.mp4").unlink(missing_ok=True)  # 배경 원본은 저장소에 두지 않는다
    keep = {k: v for k, v in p.items() if k not in ("left", "right", "rows")}
    (folder / "data.yaml").write_text(yaml.safe_dump(keep, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if not preview:
        log = used_log() + [{"date": today, "kind": kind, "key": p["key"], "title": title, "folder": folder.name}]
        LOG.write_text(yaml.safe_dump(log, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return (f"{kind}: {title} ({info['seconds']:.0f}초" + (", 목소리" if info["voice"] else "")
            + (", 실사 배경" if info["video_bg"] else "") + ")")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=str(date.today()))
    ap.add_argument("--only")
    ap.add_argument("--preview", action="store_true", help="기록에 남기지 않는 미리보기 (제작 방식 확인용)")
    ap.add_argument("--discard", help="이 쇼츠 폴더를 버린다 (도우미 버튼)")
    a = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    if a.discard:
        print(discard(a.discard))
        return
    gone = cleanup(a.date)
    lines = []
    for k in (a.only or "ABC"):
        wait = [] if a.preview else pending(k)
        lines.append(f"{k}: 아직 안 올린 쇼츠가 있어 새로 만들지 않음 ({', '.join(wait)})" if wait else make(k, a.date, a.preview))
    print("쇼츠: " + " / ".join(lines) + (f" (지난 쇼츠 {len(gone)}개 정리)" if gone else ""))


if __name__ == "__main__":
    main()
