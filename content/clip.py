"""네이버 클립용 세로 영상 (약 18초, 9:16, 30fps): 블로그 카드를 붙이는 게 아니라 같은 숫자로 움직이는 화면을 새로 그린다.

- 줄거리는 카드를 그릴 때 저장한 clip.json (훅 → 퀴즈 + 카운트다운 → 정답 공개 → 표 → 최저임금 → 블로그 안내).
- 움직임: 사진 천천히 확대, 유니폼 등판(content/jersey.py) 흔들림, 이름 쾅 등장, 보기 차례로 등장, 3·2·1 타이머, 정답 강조·흔들림, 표 한 줄씩, 진행 막대.
- 소리: 무음 트랙만 넣는다. 음악은 올릴 때 클립 에디터의 음원(네이버가 저작권 계약한 곡)으로 넣는다 (대표 결정 2026-09-30).
- 재료는 우리 숫자와 Pexels 사진뿐. 경기 영상·남의 영상·AI 목소리는 쓰지 않는다.
- 결과: posts/<글>/clip.mp4, clip.txt (설명 + 해시태그).

사용법: python -m content.clip [posts/폴더 ...]   (폴더를 안 주면 posts/ 아래 전부)
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import yaml
from PIL import Image, ImageDraw

from market.common import ROOT
from . import desk, jersey, photos
from .brand import font

W, H, FPS = 1080, 1920, 30
BG = (14, 17, 26)
PANEL = (28, 33, 48)
GOLD = (245, 190, 40)
WHITE = (245, 245, 245)
GRAY = (150, 158, 175)
RED = (226, 58, 58)
GREEN = (38, 170, 95)
BLOG = "억소리 나는 스포츠"
MAX_TAGS = 8
VIDEO = False  # 실사 배경 영상 위에 그릴 때 True (장면이 불투명 배경을 칠하지 않는다, content/produce.py)
SAFE_BOTTOM = 1480  # 클립 화면 아래쪽은 설명·버튼이 덮는다 → 중요한 글자는 이 위에


# ---------------------------------------------------------------- 움직임 도구

def clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def ease_out(t: float) -> float:
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_back(t: float) -> float:
    """살짝 튀어나왔다 자리 잡는 움직임 (쾅 등장)."""
    t = clamp(t)
    c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


@lru_cache(maxsize=512)
def label(text: str, weight: str, size: int, fill: tuple, stroke: int = 0, max_w: int = int(W * 0.88)) -> Image.Image:
    """글자 한 덩어리를 투명 이미지로 (너무 길면 줄인다)."""
    while size > 20:
        f = font(weight, size)
        x0, y0, x1, y1 = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, stroke_width=stroke)
        if x1 - x0 <= max_w:
            break
        size -= 4
    im = Image.new("RGBA", (x1 - x0 + 8, y1 - y0 + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - x0, 4 - y0), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
    return im


def put(canvas: Image.Image, im: Image.Image, cx: float, cy: float, scale: float = 1.0, alpha: float = 1.0,
        anchor: str = "c") -> None:
    if alpha <= 0.01 or scale <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if alpha < 0.99:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda a: int(a * alpha)))
    x = cx - im.width / 2 if anchor == "c" else cx
    canvas.alpha_composite(im, (int(x), int(cy - im.height / 2)))


def pill(w: int, h: int, fill: tuple, outline: tuple | None = None) -> Image.Image:
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(im).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=fill, outline=outline, width=4)
    return im


def cover(photo: Image.Image | None) -> Image.Image:
    """세로 배경: 사진을 꽉 채우고 어둡게 (사진이 없으면 남색)."""
    if photo is None:
        return Image.new("RGB", (W, H), BG)
    p = photo.convert("RGB")
    s = max(W / p.width, H / p.height) * 1.1
    p = p.resize((int(p.width * s), int(p.height * s)), Image.LANCZOS)
    x, y = (p.width - int(W * 1.1)) // 2, (p.height - int(H * 1.1)) // 2
    p = p.crop((x, y, x + int(W * 1.1), y + int(H * 1.1)))
    shade = Image.linear_gradient("L").resize(p.size).point(lambda v: int(90 + v * 0.55))
    return Image.composite(Image.new("RGB", p.size, (0, 0, 0)), p, shade)


# ---------------------------------------------------------------- 장면

class Scene:
    dur = 3.0

    def draw(self, c: Image.Image, t: float) -> None:  # t: 장면 안 시간(초)
        raise NotImplementedError


class Hook(Scene):
    """첫 프레임부터 전부 보인다 (첫 프레임이 클립 표지): 태그·등판·이름·기록·금액 → 금액 튕기며 번쩍. 사진은 천천히 확대."""
    dur = 2.4

    def __init__(self, h: dict, photo: Image.Image | None, pics: list[Image.Image] = (), credit: str = ""):
        self.h, self.bg, self.credit = h, cover(photo), credit
        n = len(h.get("players", []))
        if pics:  # 선수 사진(위키미디어 자유 이용)이 있으면 등판 대신 사진 카드
            from .playerphoto import card
            self.jerseys = [(card(p, 560 if len(pics) < 2 else 420), rot) for p, rot in zip(pics, (-3, 3) if len(pics) > 1 else (0,))]
        else:
            js = jersey.for_players(h.get("players", []), 560 if n < 2 else 440)
            self.jerseys = [(j, rot) for j, rot in zip(js, (-5, 6) if len(js) > 1 else (-4,))]
        self.say = f"{h['name']}, {h['label']} {h['big']}."
        self.sfx = [("boom", 0.35, 0.6)]

    def draw(self, c, t):
        if not VIDEO:
            z = 1 + 0.05 * t / self.dur
            bg = self.bg.resize((int(self.bg.width * z / 1.1), int(self.bg.height * z / 1.1)), Image.BILINEAR)
            c.paste(bg.crop(((bg.width - W) // 2, (bg.height - H) // 2, (bg.width - W) // 2 + W, (bg.height - H) // 2 + H)))
        tag = label(self.h["tag"], "display", 52, WHITE)
        box = Image.new("RGBA", (tag.width + 50, tag.height + 30), RED + (255,))
        box.alpha_composite(tag, (25, 15))
        put(c, box, 80, 250, anchor="l")
        xs = [W / 2] if len(self.jerseys) == 1 else [W * 0.3, W * 0.7]
        for (j, rot), x in zip(self.jerseys, xs):  # 등판이 먼저 툭 (첫 프레임부터 보임)
            wob = rot + 4 * math.sin(t * 2.2)
            put(c, j.rotate(wob, resample=Image.BICUBIC, expand=True), x, 610, 1.15 - 0.15 * ease_out(t / 0.25))
        y0 = 1010 if self.jerseys else 600
        if self.credit:
            put(c, label(self.credit, "r", 26, GRAY), W / 2, 905, 1, 0.8)
        put(c, label(self.h["name"], "display", 200, WHITE, 12), W / 2, y0, 1.1 - 0.1 * ease_out(t / 0.2))
        # 첫 프레임 = 클립 표지(네이버가 첫 장면을 표지로 씀) → 기록·금액도 처음부터 보이게, 등장 대신 튕김
        put(c, label(self.h["label"], "display", 90, WHITE, 6), W / 2, y0 + 190, 1.1 - 0.1 * ease_out(t / 0.2))
        s = 1 + 0.08 * math.sin(math.pi * clamp((t - 0.35) / 0.3))
        put(c, label(self.h["big"], "display", 190, GOLD, 10), W / 2, y0 + 370, s)
        if 0.35 < t < 0.5:  # 번쩍
            c.alpha_composite(Image.new("RGBA", (W, H), (255, 255, 255, int(110 * (1 - (t - 0.35) / 0.15)))))


class Quiz(Scene):
    """질문 → 보기 차례로 → 3·2·1 타이머 (막대가 줄어든다)."""
    dur = 5.2

    def __init__(self, q: dict):
        self.q = q
        self.say = " ".join(q["lines"])
        self.sfx = [("tick", 1.6, 0.5), ("tick", 2.7, 0.5), ("tick", 3.8, 0.5)]

    def draw(self, c, t):
        for i, ln in enumerate(self.q["lines"]):
            k = ease_out((t - i * 0.15) / 0.35)
            put(c, label(ln, "display", 104, WHITE), W / 2, 360 + i * 140 - 60 * (1 - k), 1, k)
        n = len(self.q["options"])
        for i, o in enumerate(self.q["options"]):
            k = ease_back((t - 0.6 - i * 0.22) / 0.35)
            y = 700 + i * 190 if n > 2 else 740 + i * 230
            p = pill(840, 150, PANEL + (255,), (70, 78, 100))
            num = label(str(i + 1), "display", 70, GOLD)
            p.alpha_composite(num, (60 - num.width // 2 + 20, 75 - num.height // 2))
            txt = label(o, "display", 78, WHITE, max_w=620)
            p.alpha_composite(txt, (470 - txt.width // 2, 75 - txt.height // 2))
            put(c, p, W / 2 + (1 - k) * 700, y, 1, clamp(k * 3))
        left = clamp((t - 1.6) / 3.3)  # 타이머 3.3초
        if t > 1.6:
            sec = 3 - min(2, int((t - 1.6) / 1.1))
            pulse = 1 + 0.15 * (1 - ((t - 1.6) % 1.1) / 1.1)
            d = ImageDraw.Draw(c)
            d.ellipse((W / 2 - 95, 1260 - 95, W / 2 + 95, 1260 + 95), fill=RED)
            put(c, label(str(sec), "display", 150, WHITE), W / 2, 1262, pulse)
            d.rounded_rectangle((140, 1400, W - 140, 1424), radius=12, fill=PANEL)
            d.rounded_rectangle((140, 1400, 140 + (W - 280) * (1 - left), 1424), radius=12, fill=GOLD)


class Answer(Scene):
    """정답 보기만 초록으로 남고, 큰 숫자가 흔들리며 등장 → 계산식."""
    dur = 3.6

    def __init__(self, q: dict, a: dict):
        self.q, self.a = q, a
        self.say = f"정답은 {a['big']}."
        self.sfx = [("ding", 0.9, 0.6)]

    def draw(self, c, t):
        n = len(self.q["options"])
        for i, o in enumerate(self.q["options"]):
            y = 700 + i * 190 if n > 2 else 740 + i * 230
            ok = i == self.q["answer"]
            k = ease_out(t / 0.4)
            p = pill(840, 150, (GREEN if ok else PANEL) + (255,), None if ok else (70, 78, 100))
            txt = label(o, "display", 78, WHITE, max_w=620)
            p.alpha_composite(txt, (420 - txt.width // 2, 75 - txt.height // 2))
            if ok:
                y = y + (330 - y) * ease_out((t - 0.5) / 0.4)
                put(c, p, W / 2, y, 1 + 0.08 * math.sin(clamp(t / 0.5) * math.pi))
            else:
                put(c, p, W / 2, y, 1, 1 - k)
        if t > 0.9:
            k = ease_back((t - 0.9) / 0.35)
            shake = 14 * math.sin((t - 0.9) * 60) * (1 - clamp((t - 0.9) / 0.4))
            if self.a.get("top"):
                put(c, label(self.a["top"], "display", 84, WHITE), W / 2, 620, 1, clamp((t - 0.9) / 0.2))
            big = label(self.a["big"], "display", 190, GOLD, 8)
            bar = Image.new("RGBA", (int((big.width + 60) * clamp((t - 1.0) / 0.3)) or 1, 70), GOLD + (90,))
            put(c, bar, W / 2, 870, 1, 1)
            put(c, big, W / 2 + shake, 820, 2 - k, clamp((t - 0.9) / 0.1))
        if t > 1.6:
            put(c, label(self.a["line"], "b", 50, GRAY), W / 2, 1040, 1, clamp((t - 1.6) / 0.4))


class Table(Scene):
    """제목 → 한 줄씩 미끄러져 들어온다. 강조 줄은 금색으로 깜빡."""

    def __init__(self, tb: dict):
        self.tb = tb
        self.say = tb["title"]
        self.rows = tb["rows"][:6]
        self.dur = 1.2 + 0.35 * len(self.rows) + 1.6

    def draw(self, c, t):
        put(c, label(self.tb["title"], "display", 88, WHITE), W / 2, 400, 1, ease_out(t / 0.2))
        cols = len(self.tb["header"])
        xs = [230, 560, 860] if cols == 3 else [W * 0.3, W * 0.68]
        size, cw = (52, 270) if cols == 3 else (60, 400)
        top, rh = 540, 140
        for j, h in enumerate(self.tb["header"]):
            put(c, label(str(h), "b", 44, GRAY, max_w=cw), xs[j], top, 1, ease_out((t - 0.3) / 0.3))
        d = ImageDraw.Draw(c)
        for i, row in enumerate(self.rows):
            k = ease_out((t - 0.8 - i * 0.35) / 0.35)
            if k <= 0:
                continue
            y = top + (i + 1) * rh
            hot = i in self.tb.get("hot", [])
            glow = hot and t > 0.8 + len(self.rows) * 0.35
            fill = GOLD if glow and int(t * 3) % 2 == 0 else PANEL
            dx = (1 - k) * -W
            d.rounded_rectangle((60 + dx, y - rh / 2 + 10, W - 60 + dx, y + rh / 2 - 10), radius=24, fill=fill)
            for j, cell in enumerate(row):
                col = BG if fill == GOLD else (WHITE if j else GRAY)
                put(c, label(str(cell), "display" if j else "b", size, col, max_w=cw), xs[j] + dx, y)


class Wage(Scene):
    dur = 2.6

    def __init__(self, w: dict):
        self.w = w
        self.say = f"{w['title']} {w['big']}."
        self.sfx = [("boom", 0.4, 0.5)]

    def draw(self, c, t):
        put(c, label(self.w["title"], "display", 84, WHITE), W / 2, 640, 1, ease_out(t / 0.3))
        put(c, label(self.w["big"], "display", 200, GOLD, 8), W / 2, 900, 1.8 - 0.8 * ease_back((t - 0.4) / 0.35),
            clamp((t - 0.4) / 0.1))
        put(c, label("주 40시간 꼬박 일해도", "b", 52, GRAY), W / 2, 1110, 1, clamp((t - 1.0) / 0.4))


class Outro(Scene):
    """끝은 댓글로 이어질 질문 (클립은 그 자리에서 소비된다: 블로그 예고가 아니라 대화로 끝낸다).
    youtube: 블로그 안내 대신 구독 한 줄 (유튜브에서는 네이버 블로그로 넘어가기 어렵다)."""
    dur = 2.6

    def __init__(self, question: str = "", youtube: bool = False):
        self.q, self.yt = question, youtube
        self.say = f"{question} 댓글로 알려 주세요." if question else "정답 맞히셨나요? 댓글로 알려 주세요."

    def draw(self, c, t):
        tail = ("구독하면 매일 새 몸값 퀴즈", "b", 44, GRAY) if self.yt else (f"계산 과정은 블로그 '{BLOG}'", "b", 44, GRAY)
        lines = ([(self.q, "display", 104, WHITE), ("댓글로 알려주세요", "b", 56, GOLD), ("", "b", 10, GRAY), tail] if self.q else
                 [("정답 맞히셨나요?", "display", 100, WHITE), ("댓글로 알려주세요", "display", 80, GOLD),
                  ("", "b", 10, GRAY), tail] if self.yt else
                 [("계산 과정과 출처는", "display", 100, WHITE), ("블로그에", "display", 100, WHITE),
                  (BLOG, "display", 86, GOLD), ("매일 새 몸값 퀴즈", "b", 50, GRAY)])
        for i, (txt, w, s, col) in enumerate(lines):
            if not txt:
                continue
            k = ease_out((t - i * 0.15) / 0.35)
            put(c, label(txt, w, s, col), W / 2, 700 + i * 140 + 40 * (1 - k), 1, k)


class LoopBack(Scene):
    """쇼츠 전용: 마지막 0.4초에 첫 장면으로 스르르 넘어간다 (다시 재생될 때 끊김 없이 이어져 반복 시청이 는다)."""
    dur = 0.4

    def __init__(self, last: Scene, first: Scene):
        self.last, self.first = last, first

    def draw(self, c, t):
        a, b = c.copy(), c.copy()
        self.last.draw(a, self.last.dur)
        self.first.draw(b, 0)
        c.paste(Image.blend(a, b, clamp(t / self.dur)))


def scenes(st: dict, photo: Image.Image | None, question: str = "", youtube: bool = False,
           pics: list[Image.Image] = (), credit: str = "") -> list[Scene]:
    out: list[Scene] = [Hook(st["hook"], photo, pics, credit), Quiz(st["quiz"]), Answer(st["quiz"], st["answer"]), Table(st["table"])]
    if st.get("wage"):
        out.append(Wage(st["wage"]))
    out.append(Outro(question, youtube))
    return out + [LoopBack(out[-1], out[0])] if youtube else out


def render(sc: list[Scene], rgba: bool = False, badge: Image.Image | None = None):
    """프레임을 차례로 만든다 (위쪽 진행 막대 + 블로그 이름은 모든 장면 공통).
    rgba=True: 투명 바탕(실사 배경 위에 얹을 전경, 실사면 글자가 읽히게 어두운 막을 깐다). badge: 'AI 음성' 표기."""
    total = sum(s.dur for s in sc)
    base = Image.new("RGBA", (W, H), ((8, 10, 18, 105) if VIDEO else (0, 0, 0, 0)) if rgba else BG + (255,))
    brand = label(BLOG, "b", 36, GRAY)
    t0 = 0.0
    for s in sc:
        for f in range(int(round(s.dur * FPS))):
            t = f / FPS
            c = base.copy()
            s.draw(c, t)
            d = ImageDraw.Draw(c)
            g = (t0 + t) / total
            d.rectangle((0, 0, W, 10), fill=(40, 44, 58))
            d.rectangle((0, 0, int(W * g), 10), fill=GOLD)
            put(c, brand, W / 2, 110, 1, 0.9)
            if badge is not None:
                put(c, badge, W - 60 - badge.width, 110, anchor="l")
            yield c if rgba else c.convert("RGB")
        t0 += s.dur


# ---------------------------------------------------------------- 파일

def ffmpeg() -> str | None:
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def search_tags(folder: Path) -> list[str]:
    """클립 검색에서 사람들이 치는 말을 해시태그 맨 앞에: 선수 이름, 이름+연봉(골프는 상금)."""
    f = folder / "data.yaml"
    d = (yaml.safe_load(f.read_text(encoding="utf-8")) or {}) if f.exists() else {}
    name = d.get("short_name") or d.get("player", "").split(" ")[0]
    if not name:
        return []
    return [name, name + ("상금" if "골프" in str(d.get("sport", "")) else "연봉")]


def caption(folder: Path, p: dict) -> str:
    """클립 설명: 글쓴이가 쓴 설명(clip_caption.txt, 없으면 제목 + 기본 문구) + 사진 출처(있으면) + 해시태그."""
    hook = next((t["text"] for t in p["titles"] if t["best"]), p["titles"][0]["text"] if p["titles"] else "")
    cf = folder / "clip_caption.txt"
    text = cf.read_text(encoding="utf-8").strip() if cf.exists() else \
        f"{hook}\n\n정답 맞히셨나요? 계산 과정과 출처는 블로그 '{BLOG}'에 있어요."
    tags = " ".join("#" + t.replace(" ", "") for t in dict.fromkeys(search_tags(folder) + p["tags"] + ["몸값퀴즈", "스포츠"]))
    tags = " ".join(tags.split()[:MAX_TAGS])
    from .produce import credits
    credit = "\n".join([x for x in [photos.credit(folder)] if x] + credits(folder))
    ai = "※ 이 영상의 목소리는 AI 음성입니다." if (folder / "clip.mp4").exists() and _has_voice(folder / "clip.mp4") else ""
    return "\n\n".join(x for x in [text, credit, ai, tags] if x) + "\n"


def _has_voice(mp4: Path) -> bool:
    """영상에 목소리를 넣었는지 (produce가 남긴 표시)."""
    return mp4.with_suffix(".voice").exists()


def encode(exe: str, sc: list[Scene], out: Path) -> str:
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",  # 무음 트랙 (음악은 각 앱에서)
           "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fr in render(sc):
            proc.stdin.write(fr.tobytes())
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        proc.wait()
    return err.strip()[-200:] if proc.returncode else ""


def make(folder: Path) -> str:
    """네이버 클립(clip.mp4·clip.txt)을 만든다. 유튜브 쇼츠는 따로 만든다 (content/shorts.py, 대표 결정 2026-09-30).
    결과 한 줄을 돌려준다 (실패해도 글쓰기는 멈추지 않는다)."""
    p = desk.parse(folder)
    if not p or not (folder / "clip.json").exists():
        return "클립: 줄거리(clip.json)가 없어 건너뜀 — 이미지 다시 그리기를 돌리면 생김"
    exe = ffmpeg()
    if not exe:
        return "클립: ffmpeg가 없어 영상을 만들지 못함"
    st = json.loads((folder / "clip.json").read_text(encoding="utf-8"))
    from . import playerphoto, produce
    d = yaml.safe_load((folder / "data.yaml").read_text(encoding="utf-8")) if (folder / "data.yaml").exists() else {}
    bg = produce.bg_video(folder, str(d.get("sport", "야구")), folder.name)  # A. 실사 배경 (없으면 사진·남색)
    photo = None if bg else (Image.open(folder / "photo.jpg") if (folder / "photo.jpg").exists() else None)
    pics = playerphoto.fetch(folder, st["hook"].get("players", []))  # C. 선수 사진 (없으면 등판)
    credit = " · ".join(f"사진 {i['artist'][:20]} ({i['license']})" for i in
                        (json.loads(f.read_text(encoding="utf-8")) for f in sorted(folder.glob("player*.json"))))
    qf = folder / "clip_question.txt"
    q = qf.read_text(encoding="utf-8").strip() if qf.exists() else ""
    sc = scenes(st, photo, q, pics=pics, credit=credit)
    err, info = produce.produce(exe, sc, folder / "clip.mp4", bg)  # B·D. 효과음·목소리
    if err:
        return f"클립: 영상 만들기 실패 ({err})"
    (folder / "clip.txt").write_text(caption(folder, p), encoding="utf-8")
    (folder / "bg.mp4").unlink(missing_ok=True)  # 배경 원본은 저장소에 두지 않는다 (출처는 bg.json)
    return (f"클립: 세로 영상 {info['seconds']:.0f}초 완성" + (" · 목소리" if info["voice"] else "")
            + (" · 실사 배경" if info["video_bg"] else "") + (f" · 선수 사진 {len(pics)}" if pics else ""))


def main() -> None:
    folders = [Path(a) for a in sys.argv[1:]] or sorted(p for p in (ROOT / "posts").iterdir() if (p / "post.md").exists())
    for f in folders:
        print(f"{f.name}: {make(f)}")


if __name__ == "__main__":
    main()
