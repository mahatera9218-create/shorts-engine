"""조선 화풍 모션그래픽 쇼츠 (2026-10-05, 대표 피드백 '캐릭터가 안 움직여 노잼'): AI 영상 없이 코드로 움직인다.

- 재료: GPT Image 2로 '투명 배경' 낱장 그림(장사꾼 4가지 자세, 호랑이, 금덩이, 엽전, 궤짝, 먹구름)과 빈 장터 배경.
  장사꾼은 기존 1번 장면을 참고 그림으로 넘겨 얼굴·옷을 맞춘다. 한 번 그린 재료는 다시 그리지 않는다.
- 움직임: 코드(종이 인형극처럼) — 등장·튀어오름·찌그러짐·흔들림·포물선으로 날아감·화면 흔들림·번개·도장 쾅.
- 숫자·자막은 코드로 얹는다(그림에 글자 없음). 목소리는 content/ai_short.voice (여자, 1.2배속, 캐시 재사용).
- 비용: 재료 그림 약 10장(중간 화질) 한 번. 영상 만들기는 0원.
결과: reports/쇼츠-시안/금값-출렁/M-모션그래픽.mp4
"""
from __future__ import annotations

import base64
import math
import random
import time
from datetime import date
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import ai_short as base
from .produce import mix, sfx, wav_seconds

W, H, FPS = 1080, 1920, 30
OUT = base.OUT
ART = OUT / "parts"
FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
INK = (28, 24, 20)
PAPER = (239, 230, 210)
RED = (179, 38, 30)

STYLE = ("Joseon-dynasty Korean genre painting style in the manner of Kim Hong-do and Korean minhwa folk painting: "
         "ink brush outlines, light ochre/indigo/vermilion washes. No text, no letters, no signature. ")
HERO_REF = ("Use the attached image only as the character reference: the same cheerful young merchant with the same "
            "round face, thin mustache, black gat hat, indigo jeogori and white baji. ")
PARTS = {  # 이름: (프롬프트, 크기, 투명, 참고 그림 사용)
    "bg": (STYLE + "Vertical background plate: an empty Joseon market street at morning with thatched stalls, "
           "baskets and distant mountains, NO people, soft and slightly faded so characters stand out in front.",
           "1024x1536", False, False),
    "hero_surprised": (STYLE + HERO_REF + "Full body, standing, both hands raised in surprise, mouth open, facing "
                       "the viewer. Isolated character only.", "1024x1536", True, True),
    "hero_point": (STYLE + HERO_REF + "Full body, confidently pointing to his right with one hand, smiling, "
                   "facing the viewer. Isolated character only.", "1024x1536", True, True),
    "hero_happy": (STYLE + HERO_REF + "Full body, laughing happily, hugging a small pile of gold bars. "
                   "Isolated character only.", "1024x1536", True, True),
    "hero_bow": (STYLE + HERO_REF + "Full body, bowing politely with hands together, friendly smile. "
                 "Isolated character only.", "1024x1536", True, True),
    "tiger": (STYLE + "A flat, humorous minhwa folk-painting tiger (magpie-and-tiger style, big round eyes) leaping "
              "to the right with all four legs stretched. Isolated, no background.", "1024x1024", True, False),
    "gold": (STYLE + "A single small Korean gold bar ingot, simple rectangular shape, shiny. Isolated, no background.",
             "1024x1024", True, False),
    "coins": (STYLE + "A string of Joseon yeopjeon brass coins (round with square holes) tied with red cord. "
              "Isolated, no background.", "1024x1024", True, False),
    "chest": (STYLE + "A small wooden Joseon coin chest with brass fittings. Isolated, no background.",
              "1024x1024", True, False),
    "cloud": (STYLE + "A dark swirling storm cloud in Korean folk-painting style with a lightning bolt. "
              "Isolated, no background.", "1024x1024", True, False),
}


# ---------------------------------------------------------------- 재료 그리기

def draw_parts(log: list[str]) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    hdr = {"Authorization": f"Bearer {base.key('OPENAI_API_KEY')}"}
    for name, (prompt, size, transparent, ref) in PARTS.items():
        out = ART / f"{name}.png"
        if out.exists():
            continue
        t0 = time.time()
        body = {"model": base.MODEL, "prompt": prompt, "size": size, "quality": base.QUALITY, "n": "1"}
        if transparent:
            body.update(background="transparent", output_format="png")
        if ref:
            with (OUT / "scene-1.png").open("rb") as f:
                r = requests.post("https://api.openai.com/v1/images/edits", headers=hdr, data=body,
                                  files=[("image[]", ("ref.png", f, "image/png"))], timeout=300)
        else:
            r = requests.post("https://api.openai.com/v1/images/generations", headers=hdr,
                              json={**body, "n": 1}, timeout=300)
        if r.status_code != 200:
            log.append(f"- 재료 {name} 실패 HTTP {r.status_code}: {r.text[:160]}")
            continue
        out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
        im = Image.open(out)
        log.append(f"- 재료 {name} {time.time() - t0:.0f}초 ({'투명' if im.mode == 'RGBA' and im.getextrema()[3][0] < 255 else '불투명'})")


# ---------------------------------------------------------------- 도구

def ease_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_back(t: float) -> float:
    t = max(0.0, min(1.0, t))
    c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def fnt(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def sprite(name: str, height: int) -> Image.Image:
    im = Image.open(ART / f"{name}.png").convert("RGBA")
    bb = im.getbbox()  # 투명 여백 잘라내기
    if bb:
        im = im.crop(bb)
    r = height / im.height
    return im.resize((max(1, int(im.width * r)), height), Image.LANCZOS)


class Stage:
    """한 프레임 그리기: 배경 위에 인형(그림 조각)을 놓는다."""

    def __init__(self, bg: Image.Image, shake: float = 0.0):
        self.c = bg.copy()
        self.dx = self.dy = 0
        if shake:
            self.dx, self.dy = int(random.uniform(-shake, shake)), int(random.uniform(-shake, shake))

    def put(self, im: Image.Image, cx: float, by: float, sx: float = 1.0, sy: float = 1.0, rot: float = 0.0,
            alpha: float = 1.0) -> None:
        """cx: 가운데 x, by: 발바닥(아래) y. sx·sy: 늘림/찌그러짐, rot: 기울기(도)."""
        if alpha <= 0 or sx <= 0.01 or sy <= 0.01:
            return
        w, h = max(1, int(im.width * sx)), max(1, int(im.height * sy))
        p = im.resize((w, h), Image.BILINEAR) if (w, h) != im.size else im
        if rot:
            p = p.rotate(rot, resample=Image.BICUBIC, expand=True)
        if alpha < 1:
            a = p.getchannel("A").point(lambda v: int(v * alpha))
            p = p.copy()
            p.putalpha(a)
        self.c.alpha_composite(p, (int(cx - p.width / 2) + self.dx, int(by - p.height) + self.dy))


def text_block(text: str, size: int, fill=INK, font="NanumBrushScript-Regular.ttf", stroke=0, sfill=PAPER):
    f = fnt(font, size)
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, stroke_width=stroke)
    im = Image.new("RGBA", (x1 - x0 + 16, y1 - y0 + 16), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((8 - x0, 8 - y0), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=sfill)
    return im


def caption(text: str) -> Image.Image:
    """자막: 한지 띠 위에 붓글씨."""
    t = text_block(text, 124, INK, stroke=2, sfill=INK)  # 붓글씨를 조금 두껍게
    pad = 36
    im = Image.new("RGBA", (t.width + pad * 2, t.height + pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=28, fill=PAPER + (240,), outline=INK + (255,), width=5)
    im.alpha_composite(t, (pad, pad // 2))
    return im


def seal(size: int = 150) -> Image.Image:
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=14, fill=RED + (255,))
    d.rounded_rectangle((10, 10, size - 11, size - 11), radius=10, outline=PAPER + (255,), width=5)
    t = text_block("억", int(size * 0.62), PAPER, font="SongMyung-Regular.ttf")
    im.alpha_composite(t, ((size - t.width) // 2, (size - t.height) // 2))
    return im


def pop(t: float, start: float, dur: float = 0.28) -> float:
    """0 → 살짝 크게 → 1 (쾅 등장)."""
    if t < start:
        return 0.0
    return ease_back((t - start) / dur)


# ---------------------------------------------------------------- 장면

class Scenes:
    def __init__(self, durs: list[float]):
        self.durs = durs
        bg = Image.open(ART / "bg.png").convert("RGB")
        r = max((W + 80) / bg.width, H / bg.height)
        self.bg = bg.resize((int(bg.width * r), int(bg.height * r)), Image.LANCZOS)
        self.paper = Image.new("RGBA", (W, H), PAPER + (255,))
        self.hero = {k: sprite(f"hero_{k}", 900) for k in ("surprised", "point", "happy", "bow")}
        self.tiger = sprite("tiger", 520)
        self.gold = sprite("gold", 120)
        self.coins = sprite("coins", 260)
        self.chest = sprite("chest", 230)
        self.cloud = sprite("cloud", 520)
        self.icons = {"coins": sprite("coins", 230), "chest": sprite("chest", 200), "cloud": sprite("cloud", 230)}
        self.title = text_block("금값은 왜 하루에도 출렁일까?", 104, INK, stroke=2, sfill=INK)
        self.badge = text_block("AI 그림, AI 음성", 46, (90, 80, 66))
        self.seal = seal()
        self.caps = [caption(c) for c in ("금, 왜 출렁일까?", "① 달러 세지면 금은 눌림", "② 금리 오르면 돈이 빠짐",
                                          "③ 불안하면 금으로 우르르", "달러, 금리, 분위기", "자세한 건 블로그에서!")]
        rnd = random.Random(7)
        self.burst = [(rnd.uniform(-520, 520), rnd.uniform(-1500, -1050), rnd.uniform(-400, 400)) for _ in range(9)]
        self.rain = [(rnd.uniform(140, 940), rnd.uniform(0, 1.6), rnd.uniform(-200, 200)) for _ in range(14)]

    def backdrop(self, t: float, i: int, dark: float = 0.0) -> Image.Image:
        ox = int(40 - 80 * (sum(self.durs[:i]) + t) / sum(self.durs))  # 아주 천천히 옆으로 (패럴랙스)
        c = self.bg.crop((40 + ox, 0, 40 + ox + W, H)).convert("RGBA")
        c = Image.blend(c, self.paper, 0.25)
        if dark:
            c = Image.blend(c, Image.new("RGBA", (W, H), (30, 30, 45, 255)), dark)
        return c

    def chrome(self, s: Stage, i: int, t: float) -> None:
        d = ImageDraw.Draw(s.c)
        d.rectangle((0, 0, W, 210), fill=PAPER + (235,))
        d.line((0, 210, W, 210), fill=INK, width=4)
        s.c.alpha_composite(self.title, ((W - self.title.width) // 2, 105 - self.title.height // 2))
        s.c.alpha_composite(self.badge, (30, 222))
        k = pop(t, 0.08)
        if k:
            cap = self.caps[i]
            s.put(cap, W / 2, 1460, sx=k, sy=k)

    # 장면별 ------------------------------------------------------------
    def s0(self, t):  # 호랑이 쾅 → 금덩이 튀어 오름 → 장사꾼 깜짝
        hit = 0.45
        s = Stage(self.backdrop(t, 0), shake=18 if hit < t < hit + 0.25 else 0)
        if t >= hit:  # 금덩이 포물선
            for vx, vy, vr in self.burst:
                u = t - hit
                x, y = 360 + vx * u, 1150 + vy * u + 1500 * u * u
                if y < 1500:
                    s.put(self.gold, x, y, rot=vr * u)
        k = ease_out(t / hit)
        sq = 1.0 if t < hit else 1 + 0.25 * math.exp(-8 * (t - hit)) * math.cos(30 * (t - hit))
        s.put(self.tiger, -400 + 760 * k, 1250, sx=sq, sy=2 - sq)
        jump = 0 if t < hit else 180 * max(0, math.sin(min(math.pi, (t - hit) * 6)))
        s.put(self.hero["surprised"], 790, 1420 - jump, rot=6 * math.sin(t * 18) if t > hit else 0)
        return s

    def s1(self, t):  # 달러 저울: 달러 쪽이 내려가고 금은 들림
        s = Stage(self.backdrop(t, 1))
        s.put(self.hero["point"], 300, 1430, sy=1 + 0.02 * math.sin(t * 7))
        ang = -16 * ease_back(min(1, max(0, (t - 0.3) / 0.6)))  # 기울기
        cx, cy, L = 780, 820, 260
        d = ImageDraw.Draw(s.c)
        d.line((cx, cy, cx, 1150), fill=INK, width=14)
        d.polygon([(cx - 70, 1160), (cx + 70, 1160), (cx, 1100)], fill=INK)
        a = math.radians(ang)
        lx, ly = cx - L * math.cos(a), cy + L * math.sin(a)
        rx, ry = cx + L * math.cos(a), cy - L * math.sin(a)
        d.line((lx, ly, rx, ry), fill=INK, width=12)
        for x, y in ((lx, ly), (rx, ry)):
            d.line((x, y, x - 60, y + 120), fill=INK, width=4)
            d.line((x, y, x + 60, y + 120), fill=INK, width=4)
            d.arc((x - 90, y + 80, x + 90, y + 160), 0, 180, fill=INK, width=8)
        s.put(self.coins, lx, ly + 140, sx=0.75, sy=0.75)  # 달러(무거운 쪽): 엽전 꾸러미로
        s.put(self.gold, rx, ry + 140)
        lab = text_block("달러", 70, RED)
        s.put(lab, lx, ly - 10)
        lab2 = text_block("금", 70, INK)
        s.put(lab2, rx, ry - 10)
        return s

    def s2(self, t):  # 금리: 궤짝이 줄줄이 빠져나감
        s = Stage(self.backdrop(t, 2))
        s.put(self.hero["surprised"], 300, 1430, rot=8 * math.sin(t * 10))
        for j in range(4):
            u = t - 0.25 - j * 0.35
            if u > 0:
                x = 420 + 900 * ease_out(u / 0.9)
                y = 1200 - 260 * math.sin(min(math.pi, u / 0.9 * math.pi))
                s.put(self.chest, x, y, rot=-20 * u)
        arrow = text_block("이자 주는 곳으로!", 80, RED, stroke=2, sfill=RED)
        k = pop(t, 0.5)
        if k:
            s.put(arrow, 760, 760, sx=k, sy=k)
        return s

    def s3(self, t):  # 불안: 먹구름·번개, 금이 우르르 몰림
        flash = any(abs(t - f) < 0.06 for f in (0.35, 1.25))
        s = Stage(self.backdrop(t, 3, dark=0.45), shake=10 if flash else 0)
        s.put(self.cloud, 540 + 30 * math.sin(t * 9), 820)
        for x0, delay, vr in self.rain:
            u = t - delay * 0.8
            if u > 0:
                y = 700 + 1400 * u * u
                x = x0 + (540 - x0) * min(1, u * 1.5)
                if y < 1400:
                    s.put(self.gold, x, y, rot=vr * u)
        bounce = abs(math.sin(t * 7)) * 70
        s.put(self.hero["happy"], 540, 1440 - bounce, sx=1 + 0.04 * math.sin(t * 14), sy=1 - 0.04 * math.sin(t * 14))
        if flash:
            s.c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 170)))
        return s

    def s4(self, t):  # 정리: 아이콘 셋이 차례로 쾅
        s = Stage(self.backdrop(t, 4))
        s.put(self.hero["point"], 280, 1440, sy=1 + 0.02 * math.sin(t * 7))
        for j, (ic, lab) in enumerate((("coins", "달러"), ("chest", "금리"), ("cloud", "분위기"))):
            k = pop(t, 0.2 + j * 0.45)
            if k:
                y = 560 + j * 290
                s.put(self.icons[ic], 700, y + 120, sx=k * 0.8, sy=k * 0.8)
                s.put(text_block(lab, 80, INK), 910, y + 70, sx=k, sy=k)
        return s

    def s5(self, t):  # 인사 + 도장 쾅
        hit = 0.6
        s = Stage(self.backdrop(t, 5), shake=14 if hit < t < hit + 0.18 else 0)
        bow = 12 * max(0, math.sin(min(math.pi, t * 3)))
        s.put(self.hero["bow"], 540, 1440, rot=-bow * 0.3, sy=1 - bow / 200)
        k = pop(t, hit, 0.22)
        if k:
            s.put(self.seal, 860, 760, sx=k * (2.2 - 1.2 * min(1, (t - hit) / 0.22)), sy=k * (2.2 - 1.2 * min(1, (t - hit) / 0.22)),
                  rot=-8)
        return s

    def frames(self):
        prev = None
        for i, d in enumerate(self.durs):
            fn = getattr(self, f"s{i}")
            n = int(d * FPS)
            for f in range(n):
                t = f / FPS
                s = fn(t)
                self.chrome(s, i, t)
                fr = s.c
                if prev is not None and t < 0.25:  # 먹물 원으로 번지며 다음 장면
                    m = Image.new("L", (W, H), 0)
                    rr = ease_out(t / 0.25) * 1300
                    ImageDraw.Draw(m).ellipse((W / 2 - rr, H / 2 - rr, W / 2 + rr, H / 2 + rr), fill=255)
                    m = m.filter(ImageFilter.GaussianBlur(25))
                    fr = Image.composite(fr, prev, m)
                if f == n - 1:
                    prev = fr
                yield fr.convert("RGB")


def main() -> None:
    log = [f"# 조선 화풍 모션그래픽 쇼츠 시험 ({date.today()})", "", "## 진행 기록", ""]
    if base.key("OPENAI_API_KEY"):
        draw_parts(log)
    missing = [n for n in PARTS if not (ART / f"{n}.png").exists()]
    if missing:
        log.append(f"- 재료가 모자라 영상은 못 만듦: {', '.join(missing)}")
    else:
        voices = [base.voice(s["say"]) for s in base.SCENES]
        durs = [max(3.0, wav_seconds(v) + 0.35) if v else 3.5 for v in voices]
        durs[0] = max(durs[0], 3.2)
        starts = [sum(durs[:i]) for i in range(len(durs))]
        cues = [(v, st + 0.15, 1.0) for v, st in zip(voices, starts) if v]
        for i, st in enumerate(starts):
            if i:
                cues.append((sfx("ffmpeg", "whoosh"), st, 0.35))
        cues += [(sfx("ffmpeg", "boom"), 0.45, 0.9), (sfx("ffmpeg", "ding"), starts[5] + 0.6, 0.6)]
        cues += [(sfx("ffmpeg", "tick"), starts[4] + 0.2 + j * 0.45, 0.6) for j in range(3)]
        audio = mix("ffmpeg", cues, sum(durs), OUT / "m-voice.wav")
        err = base.encode(Scenes(durs).frames(), sum(durs), audio, OUT / "M-모션그래픽.mp4")
        audio.unlink(missing_ok=True)
        log.append("- M-모션그래픽.mp4: " + (f"실패 {err}" if err else f"{sum(durs):.0f}초 완성"))
    (OUT / f"모션-결과-{date.today()}.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
