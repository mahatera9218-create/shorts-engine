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
# 색: 화투 팔레트 (대표 결정 2026-10-05) — 홍·먹·바탕 미색·솔잎 녹색·달 금색
INK = (22, 20, 18)
PAPER = (243, 235, 221)
RED = (200, 30, 40)
GREEN = (30, 90, 58)
GOLD = (232, 180, 34)

STYLE = ("Joseon-dynasty Korean genre painting style in the manner of Kim Hong-do and Korean minhwa folk painting: "
         "ink brush outlines, light ochre/indigo/vermilion washes. No text, no letters, no signature. ")
HWATU = ("A single vertical playing card with rounded corners in the style of a traditional Korean hwatu "
         "flower card: thick black outlines, flat vermilion red, black, cream, pine green and gold, no gradients, "
         "no text, no numbers. The card fills most of the frame. ")
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
    # 화투 모티프 카드 (전통 도안을 따라 새로 그림. 남의 카드 스캔 복제 안 함)
    "card_dollar": (HWATU + "Card art: a heavy string of brass yeopjeon coins hanging from a stylized black pine "
                    "branch, bright red sun disc behind.", "1024x1536", "magenta", False),
    "card_rate": (HWATU + "Card art: a wooden coin chest with a red tassel under stylized red maple leaves, "
                  "a small deer looking at it.", "1024x1536", "magenta", False),
    "card_mood": (HWATU + "Card art: like the classic 'rain' card — black willow branches, slanted rain lines, "
                  "a red lightning bolt, a small frog.", "1024x1536", "magenta", False),
}
HWATU_STYLE = ("in the bold flat graphic style of a traditional Korean hwatu flower card: thick black outlines, flat "
               "vermilion red, black, cream, pine green and gold only, no gradients, no shading. ")
THUMBS = {  # 화투 모티프 썸네일 시안 (제목 글자는 그림에 넣고 Claude가 대조)
    "thumb-hwatu-moon": ("Square 1:1 blog thumbnail " + HWATU_STYLE + "Upper 62%: a big hwatu-card-like panel "
                         "with rounded corners — bold red sky, a black stylized hill, the full moon drawn as a huge "
                         "shiny gold coin, three black geese flying. Lower area: plain cream paper with the title.", False),
    "thumb-hwatu-rain": ("Square 1:1 blog thumbnail " + HWATU_STYLE + "Upper 62%: a hwatu 'rain card' homage — "
                         "the same merchant character from the attached reference (black gat, indigo jeogori) "
                         "holding a red oil-paper umbrella while gold coins fall like rain, black willow branches, "
                         "a small frog. Lower area: plain cream paper with the title.", True),
}
THUMB_TITLE = "금값은 왜 하루에도 출렁일까?"


# ---------------------------------------------------------------- 재료 그리기

def draw_parts(log: list[str]) -> None:
    ART.mkdir(parents=True, exist_ok=True)
    hdr = {"Authorization": f"Bearer {base.key('OPENAI_API_KEY')}"}
    for name, (prompt, size, transparent, ref) in PARTS.items():
        out = ART / f"{name}.png"
        if out.exists():
            continue
        t0 = time.time()
        if transparent == "magenta":  # 초록(솔잎)이 들어가는 화투 카드는 자홍색 화면
            prompt += (" Place the card on a perfectly flat, solid, pure magenta background (#FF00FF), evenly lit, "
                       "no shadow, no magenta or purple anywhere on the card.")
        elif transparent:  # 투명 배경은 이 모델에서 아직 막혀 있음(2026-10-05 HTTP 400) → 초록 화면에 그리고 코드로 지운다
            prompt += (" Place it on a perfectly flat, solid, pure chroma-key green background (#00FF00), evenly lit, "
                       "no shadow, no ground, no paper texture, no green anywhere on the subject.")
        body = {"model": base.MODEL, "prompt": prompt, "size": size, "quality": base.QUALITY, "n": "1"}
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
        if transparent:
            out.with_name(f"{name}-green.png").write_bytes(out.read_bytes())  # 원본도 남겨 다시 지울 수 있게
            unscreen(out, "magenta" if transparent == "magenta" else "green")
        log.append(f"- 재료 {name} {time.time() - t0:.0f}초")


def draw_thumbs(log: list[str]) -> None:
    hdr = {"Authorization": f"Bearer {base.key('OPENAI_API_KEY')}"}
    for name, (prompt, ref) in THUMBS.items():
        out = OUT / f"{name}.png"
        if out.exists():
            continue
        p = (prompt + f' Title text, exactly as written, in bold black Korean brush lettering, two lines, centered '
             f'on the cream area: "{THUMB_TITLE}". Every Hangul character must be correct. A small red square seal '
             'with the single Hangul character "억" in the bottom-right corner. No other text.')
        body = {"model": base.MODEL, "prompt": p, "size": "1024x1024", "quality": base.QUALITY, "n": "1"}
        t0 = time.time()
        if ref:
            with (OUT / "scene-1.png").open("rb") as f:
                r = requests.post("https://api.openai.com/v1/images/edits", headers=hdr, data=body,
                                  files=[("image[]", ("ref.png", f, "image/png"))], timeout=300)
        else:
            r = requests.post("https://api.openai.com/v1/images/generations", headers=hdr,
                              json={**body, "n": 1}, timeout=300)
        if r.status_code != 200:
            log.append(f"- 썸네일 {name} 실패 HTTP {r.status_code}: {r.text[:160]}")
            continue
        out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
        log.append(f"- 썸네일 {name} {time.time() - t0:.0f}초")


def unscreen(path: Path, color: str = "green") -> None:
    """색 화면 지우기(크로마키): 그 색일수록 투명, 가장자리 번짐은 눌러 준다."""
    im = Image.open(path).convert("RGB")
    px = im.load()
    a = Image.new("L", im.size, 255)
    ap = a.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b = px[x, y]
            if color == "green":
                k = g - max(r, b)  # 초록이 얼마나 튀는가
                fix = (r, max(r, b), b)
            else:  # 자홍: 빨강·파랑이 함께 높고 초록이 낮음 → 번진 만큼 빨강·파랑을 뺀다
                k = min(r, b) - g
                fix = (max(0, r - max(k, 0)), g, max(0, b - max(k, 0)))
            if k > 90:
                ap[x, y] = 0
            elif k > 30:
                ap[x, y] = int(255 * (90 - k) / 60)
                px[x, y] = fix
            elif k > 0:
                px[x, y] = fix
    a = a.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
    out = im.convert("RGBA")
    out.putalpha(a)
    out.save(path)


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
    d.rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=28, fill=PAPER + (245,), outline=RED + (255,), width=7)
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


def card_back(size) -> Image.Image:
    """화투 뒷면: 홍색 바탕에 검은 테두리."""
    w, h = size
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=int(w * 0.08), fill=RED + (255,), outline=INK + (255,), width=8)
    d.rounded_rectangle((22, 22, w - 23, h - 23), radius=int(w * 0.06), outline=(150, 20, 30, 255), width=4)
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
        self.hero = {k: sprite(f"hero_{k}", 1060) for k in ("surprised", "point", "happy", "bow")}
        self.tiger = sprite("tiger", 600)
        self.gold = sprite("gold", 170)
        self.coins = sprite("coins", 260)
        self.chest = sprite("chest", 300)
        self.cloud = sprite("cloud", 520)
        self.cards = [sprite(n, 560) for n in ("card_dollar", "card_rate", "card_mood")]
        self.card_back = card_back(self.cards[0].size)
        self.title = text_block("금값은 왜 하루에도 출렁일까?", 104, INK, stroke=2, sfill=INK)
        self.badge = text_block("AI 그림, AI 음성", 46, (90, 80, 66))
        self.seal = seal(230)
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
        d.line((0, 206, W, 206), fill=RED, width=8)
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
        s.put(self.tiger, -420 + 760 * k, 1330, sx=sq, sy=2 - sq)
        jump = 0 if t < hit else 180 * max(0, math.sin(min(math.pi, (t - hit) * 6)))
        s.put(self.hero["surprised"], 760, 1500 - jump, rot=6 * math.sin(t * 18) if t > hit else 0)
        return s

    def s1(self, t):  # 달러 저울: 달러 쪽이 내려가고 금은 들림
        s = Stage(self.backdrop(t, 1))
        s.put(self.hero["point"], 270, 1500, sy=1 + 0.02 * math.sin(t * 7))
        ang = 16 * ease_back(min(1, max(0, (t - 0.3) / 0.6)))  # 기울기: 달러 쪽(왼쪽)이 내려간다
        cx, cy, L = 730, 760, 210
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
        s.put(self.coins, lx, ly + 300, sx=0.8, sy=0.8)  # 달러(무거운 쪽): 엽전 꾸러미로
        s.put(self.gold, rx, ry + 150)
        lab = text_block("달러", 96, RED, stroke=2, sfill=RED)
        s.put(lab, lx, ly - 20)
        lab2 = text_block("금", 96, INK, stroke=2, sfill=INK)
        s.put(lab2, rx, ry - 20)
        return s

    def s2(self, t):  # 금리: 궤짝이 줄줄이 빠져나감
        s = Stage(self.backdrop(t, 2))
        s.put(self.hero["surprised"], 290, 1500, rot=8 * math.sin(t * 10))
        for j in range(4):
            u = t - 0.25 - j * 0.35
            if u > 0:
                x = 420 + 800 * ease_out(u / 1.3)
                y = 1250 - 380 * math.sin(min(math.pi, u / 1.3 * math.pi))
                s.put(self.chest, x, y, rot=-20 * u)
        arrow = text_block("이자 주는 곳으로!", 80, RED, stroke=2, sfill=RED)
        k = pop(t, 0.5)
        if k:
            s.put(arrow, 760, 640, sx=k, sy=k)
        return s

    def s3(self, t):  # 불안: 먹구름·번개, 금이 우르르 몰림
        flash = any(abs(t - f) < 0.06 for f in (0.35, 1.25))
        s = Stage(self.backdrop(t, 3, dark=0.45), shake=10 if flash else 0)
        s.put(self.cloud, 540 + 30 * math.sin(t * 9), 640)
        for x0, delay, vr in self.rain:
            u = t - delay * 0.8
            if u > 0:
                y = 560 + 1400 * u * u
                x = x0 + (540 - x0) * min(1, u * 1.5)
                if y < 1400:
                    s.put(self.gold, x, y, rot=vr * u)
        bounce = abs(math.sin(t * 7)) * 70
        s.put(self.hero["happy"], 540, 1560 - bounce, sx=1 + 0.04 * math.sin(t * 14), sy=1 - 0.04 * math.sin(t * 14))
        if flash:
            s.c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, 170)))
        return s

    def s4(self, t):  # 정리: 화투패 셋이 차례로 뒤집힘 (달러·금리·분위기)
        s = Stage(self.backdrop(t, 4))
        for j, lab in enumerate(("달러", "금리", "분위기")):
            u = (t - 0.15 - j * 0.45) / 0.34
            if u < 0:
                continue
            x, rot = 250 + j * 290, (-9, 0, 9)[j]
            k = pop(t, 0.15 + j * 0.45, 0.2)
            if u < 0.5:  # 뒷면(홍)이 접히고
                s.put(self.card_back, x, 1080, sx=k * (1 - 2 * u), sy=k, rot=rot)
            else:  # 앞면이 펴진다
                s.put(self.cards[j], x, 1080, sx=ease_back(min(1, (u - 0.5) * 2)), rot=rot)
                kk = pop(t, 0.15 + j * 0.45 + 0.2)
                s.put(text_block(lab, 110, RED if j == 0 else INK, stroke=2, sfill=RED if j == 0 else INK),
                      x, 1250, sx=kk, sy=kk)
        return s

    def s5(self, t):  # 인사 + 도장 쾅
        hit = 0.6
        s = Stage(self.backdrop(t, 5), shake=14 if hit < t < hit + 0.18 else 0)
        bow = 12 * max(0, math.sin(min(math.pi, t * 3)))
        s.put(self.hero["bow"], 540, 1540, rot=-bow * 0.3, sy=1 - bow / 200)
        k = pop(t, hit, 0.22)
        if k:
            s.put(self.seal, 860, 640, sx=k * (2.2 - 1.2 * min(1, (t - hit) / 0.22)), sy=k * (2.2 - 1.2 * min(1, (t - hit) / 0.22)),
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
        draw_thumbs(log)
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
        cues += [(sfx("ffmpeg", "tick"), starts[4] + 0.32 + j * 0.45, 0.7) for j in range(3)]  # 패 뒤집는 소리
        audio = mix("ffmpeg", cues, sum(durs), OUT / "m-voice.wav")
        err = base.encode(Scenes(durs).frames(), sum(durs), audio, OUT / "M-모션그래픽.mp4")
        audio.unlink(missing_ok=True)
        log.append("- M-모션그래픽.mp4: " + (f"실패 {err}" if err else f"{sum(durs):.0f}초 완성"))
    (OUT / f"모션-결과-{date.today()}.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
