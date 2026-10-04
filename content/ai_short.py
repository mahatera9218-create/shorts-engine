"""조선 화풍 AI 쇼츠 시험 (2026-10-04 대표 지시): 썸네일 1장 + 30초 쇼츠 두 가지 버전.

- 그림: GPT Image 2 중간 화질. 1번 장면을 기준 그림으로 삼아 나머지 장면을 그 그림을 참고해 그린다(인물 일관성 시험).
- A판: 그림 + 코드로 천천히 확대·이동(켄 번스). 추가 비용 0.
- B판: 같은 그림을 힉스필드 API의 클링(Kling)으로 움직이게 만든다. HF_API_KEY·HF_API_SECRET이 있을 때만.
- 숫자·글자(자막)는 그림에 넣지 않고 코드로 얹는다. 목소리는 구글 TTS(GOOGLE_TTS_API_KEY), 화면에 'AI 음성' 표기.
- 한 번 그린 그림·영상 조각은 reports/쇼츠-시안/<주제>/에 남겨 다시 돌릴 때 돈을 또 쓰지 않는다.
키는 GitHub Secrets에서만 읽는다.
"""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import time
from datetime import date
from pathlib import Path

import requests
from PIL import Image, ImageDraw

from .brand import font
from .produce import mix, tts, wav_seconds

W, H, FPS = 1080, 1920, 30
OUT = Path("reports/쇼츠-시안/금값-출렁")
MODEL = "gpt-image-2"
QUALITY = "medium"
KLING = "kling-video/v3.0-turbo/image-to-video"  # 힉스필드 모델 경로 (docs.higgsfield.ai, 2026-10 확인)

STYLE = (
    "A reinterpretation of Joseon-dynasty Korean genre painting in the manner of Kim Hong-do "
    "(danwon pungsokdo) and Korean folk painting (minhwa): ink brush outlines, light ochre/indigo/vermilion "
    "washes, aged hanji paper texture. Joseon-era Korean clothing and objects only (hanbok, gat, sangtu topknot, "
    "yeopjeon brass coins on strings, small Korean gold bars) — nothing Chinese or Japanese. "
    "No logos, no real people's faces, no watermark, no signature. "
)
HERO = ("the same main character in every scene: a cheerful young Joseon market merchant (gaekju) with a round "
        "face, thin mustache, black gat hat, indigo jeogori jacket and white baji trousers")

THUMB = {
    "title": "금값은 왜 하루에도 출렁일까?",
    "scene": ("Square 1:1 blog thumbnail. Scene: a flat, humorous minhwa-style tiger (like the classic "
              "magpie-and-tiger folk painting, big round eyes, playful) pouncing onto a market stall so that "
              "small Korean gold bars and strings of yeopjeon coins bounce into the air; " + HERO + " leans back "
              "in surprise. Leave the lower 35% as plain hanji paper for the title."),
}

# 대사는 일반적인 원리만 말한다 (특정 날짜의 숫자·전망·권유 없음).
SCENES = [
    {"cap": "금값은 왜 출렁일까?",
     "say": "금은 안전자산이라는데, 왜 하루에도 크게 출렁일까요? 세 가지만 알면 보입니다.",
     "scene": HERO + " stands at his market stall holding a small gold bar, puzzled, while a crowd of villagers "
              "points at him; busy Joseon market street behind.",
     "move": "the merchant tilts his head, villagers gesture, slow camera push-in"},
    {"cap": "① 달러",
     "say": "첫째, 달러입니다. 금값은 달러로 매겨져서, 달러가 강해지면 금값은 눌리기 쉽습니다.",
     "scene": HERO + " weighs a gold bar on a traditional Korean balance scale against a heavy pile of foreign "
              "silver coins brought by a foreign trader; the scale tips toward the silver.",
     "move": "the balance scale slowly tips, coins clink, gentle camera drift"},
    {"cap": "② 금리",
     "say": "둘째, 금리입니다. 금은 이자가 없어서, 금리가 오를 것 같으면 돈이 이자 주는 곳으로 옮겨 갑니다.",
     "scene": "villagers carrying wooden coin chests away from " + HERO + "'s gold stall toward a large merchant "
              "house that pays interest; he watches with a wry face.",
     "move": "villagers walk carrying chests, slow pan right"},
    {"cap": "③ 불안",
     "say": "셋째, 불안입니다. 전쟁이나 위기 소식이 들리면 사람들이 금으로 몰리면서 값이 뛰기도 합니다.",
     "scene": "dark storm clouds over the market; a worried crowd rushes to " + HERO + "'s stall to buy gold, "
              "he looks overwhelmed but happy.",
     "move": "clouds roll, crowd surges forward, slight camera shake"},
    {"cap": "달러 · 금리 · 분위기",
     "say": "그래서 금값 뉴스를 볼 땐 달러, 금리, 세상 분위기를 같이 보면 이유가 보입니다.",
     "scene": "a village seodang classroom: a kindly teacher with a long pipe points with a stick at three objects "
              "on a low table (a silver coin, a coin chest, a storm-cloud painting) while " + HERO + " and students "
              "listen.",
     "move": "the teacher taps each object, students nod, slow push-in"},
    {"cap": "오늘의 이유는 블로그에서",
     "say": "오늘 금값이 왜 움직였는지는 블로그에 쉽게 정리해 둘게요.",
     "scene": HERO + " bows politely holding an unrolled blank paper scroll, standing in front of his tidy stall "
              "at sunset.",
     "move": "the merchant bows slowly, scroll flutters, gentle camera pull-back"},
]


def key(name: str) -> str:
    return os.environ.get(name, "").strip()


# ---------------------------------------------------------------- 그림 (GPT Image 2)

def gpt_generate(prompt: str, size: str) -> bytes:
    r = requests.post("https://api.openai.com/v1/images/generations",
                      headers={"Authorization": f"Bearer {key('OPENAI_API_KEY')}"},
                      json={"model": MODEL, "prompt": prompt, "size": size, "quality": QUALITY, "n": 1}, timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    import base64
    return base64.b64decode(r.json()["data"][0]["b64_json"])


def gpt_edit(prompt: str, ref: Path, size: str) -> bytes:
    """기준 그림을 참고해 새 장면 (인물 일관성)."""
    with ref.open("rb") as f:
        r = requests.post("https://api.openai.com/v1/images/edits",
                          headers={"Authorization": f"Bearer {key('OPENAI_API_KEY')}"},
                          data={"model": MODEL, "prompt": prompt, "size": size, "quality": QUALITY, "n": "1"},
                          files=[("image[]", (ref.name, f, "image/png"))], timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    import base64
    return base64.b64decode(r.json()["data"][0]["b64_json"])


def draw_images(log: list[str]) -> None:
    thumb = OUT / "thumb.png"
    if not thumb.exists():
        p = (STYLE + THUMB["scene"] + f' Title text, exactly as written, in bold black Korean brush-calligraphy '
             f'lettering, two lines, centered in the lower area: "{THUMB["title"]}". Every Hangul character must '
             'be correct and fully legible. Add a small red square seal stamp with the single Hangul character '
             '"억" in the bottom-right corner. No other text.')
        t0 = time.time()
        thumb.write_bytes(gpt_generate(p, "1024x1024"))
        log.append(f"- 썸네일(중간 화질) {time.time() - t0:.0f}초")
    for i, s in enumerate(SCENES, 1):
        out = OUT / f"scene-{i}.png"
        if out.exists():
            continue
        base = (STYLE + "Vertical 2:3 illustration for a mobile short video, no text or letters anywhere in the "
                "image. Keep the important figures in the middle 70% of the frame. Scene: " + s["scene"])
        t0 = time.time()
        how = "새로 그림"
        if i == 1:
            out.write_bytes(gpt_generate(base, "1024x1536"))
        else:
            try:
                out.write_bytes(gpt_edit(base + " Use the attached image only as the character and style reference: "
                                         "keep the same main character's face, clothes and the same painting style, "
                                         "but draw a completely new scene.", OUT / "scene-1.png", "1024x1536"))
                how = "1번 그림 참고"
            except Exception as e:
                log.append(f"  - {i}번 참고 그리기 실패 → 새로 그림 ({str(e)[:120]})")
                out.write_bytes(gpt_generate(base, "1024x1536"))
        log.append(f"- 장면 {i} ({how}) {time.time() - t0:.0f}초")


# ---------------------------------------------------------------- 움직임 (힉스필드 · 클링)

def kling_clips(durs: list[float], log: list[str]) -> bool:
    if not (key("HF_API_KEY") and key("HF_API_SECRET")):
        log.append("- 힉스필드 키(HF_API_KEY, HF_API_SECRET)가 없어 B판(클링)은 건너뜀")
        return False
    ok = True
    for i, (s, d) in enumerate(zip(SCENES, durs), 1):
        out = OUT / f"kling-{i}.mp4"
        if out.exists():
            continue
        import higgsfield_client as hf  # 공식 SDK (pip install higgsfield-client). 키: HF_API_KEY + HF_API_SECRET
        t0 = time.time()
        try:
            url = hf.upload_file(str(OUT / f"scene-{i}.png"))
            res = hf.subscribe(KLING, arguments={
                "image_url": url, "duration": max(3, min(15, math.ceil(d))),
                "prompt": s["move"] + ". Keep the Joseon ink-and-wash painting style exactly, painted texture, "
                          "no text, no new characters, no morphing faces."})
            vid = find_url(res)
            if not vid:
                raise RuntimeError("결과에 영상 주소가 없음: " + json.dumps(res, ensure_ascii=False)[:200])
            out.write_bytes(requests.get(vid, timeout=300).content)
            log.append(f"- 클링 {i} ({math.ceil(d)}초 영상) {time.time() - t0:.0f}초")
        except Exception as e:
            ok = False
            log.append(f"- 클링 {i} 실패: {str(e)[:200]}")
    return ok


def find_url(obj) -> str | None:
    if isinstance(obj, dict):
        for k in ("video", "videos", "output", "result"):
            if k in obj:
                u = find_url(obj[k])
                if u:
                    return u
        for v in obj.values():
            u = find_url(v)
            if u:
                return u
    elif isinstance(obj, list):
        for v in obj:
            u = find_url(v)
            if u:
                return u
    elif isinstance(obj, str) and obj.startswith("http") and ".mp4" in obj:
        return obj
    return None


# ---------------------------------------------------------------- 화면 (자막 · 표기)

def text_im(text: str, size: int, fill=(255, 255, 255), stroke=6) -> Image.Image:
    f = font("xb", size)
    x0, y0, x1, y1 = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=f, stroke_width=stroke)
    im = Image.new("RGBA", (x1 - x0 + 8, y1 - y0 + 8), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((4 - x0, 4 - y0), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=(20, 16, 12))
    return im


def overlay(i: int) -> Image.Image:
    """장면 위에 얹을 투명 층: 위 제목 띠, 가운데 아래 자막, 'AI 그림·AI 음성' 표기."""
    o = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(o)
    d.rectangle((0, 0, W, 230), fill=(239, 230, 210, 235))
    t = text_im(THUMB["title"], 64, fill=(28, 26, 23), stroke=0)
    o.alpha_composite(t, ((W - t.width) // 2, 120 - t.height // 2))
    cap = text_im(SCENES[i]["cap"], 92)
    o.alpha_composite(cap, ((W - cap.width) // 2, 1330 - cap.height // 2))
    b = text_im("AI 그림 · AI 음성", 30, stroke=3)
    o.alpha_composite(b, (36, 250))
    return o


def cover(im: Image.Image, scale: float) -> Image.Image:
    r = max(W / im.width, H / im.height) * scale
    return im.resize((math.ceil(im.width * r), math.ceil(im.height * r)), Image.LANCZOS)


def kenburns(i: int, dur: float):
    base = cover(Image.open(OUT / f"scene-{i + 1}.png").convert("RGB"), 1.12)
    ov = overlay(i)
    n = int(dur * FPS)
    dx = 1 if i % 2 == 0 else -1
    for f in range(n):
        p = f / max(1, n - 1)
        z = 1.0 + 0.10 * p  # 천천히 다가가기
        cw = W * 1.12 / z
        ch = cw * H / W
        cx = base.width / 2 + dx * (base.width - cw) / 2 * (p - 0.5) * 0.8
        cy = min(base.height - ch / 2, max(ch / 2, base.height / 2))
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        fr = base.resize((W, H), Image.BILINEAR, box=box).convert("RGBA")
        fr.alpha_composite(ov)
        yield fr.convert("RGB")


def video_frames(i: int, dur: float):
    src = OUT / f"kling-{i + 1}.mp4"
    cmd = ["ffmpeg", "-loglevel", "error", "-i", str(src), "-vf",
           f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},tpad=stop_mode=clone:stop_duration=15",
           "-t", f"{dur:.2f}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    ov = overlay(i)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    size = W * H * 3
    for _ in range(int(dur * FPS)):
        buf = p.stdout.read(size)
        if len(buf) < size:
            break
        fr = Image.frombytes("RGB", (W, H), buf).convert("RGBA")
        fr.alpha_composite(ov)
        yield fr.convert("RGB")
    p.stdout.close()
    p.wait()


def encode(frames, total: float, audio: Path | None, out: Path) -> str:
    au = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", *au, "-map", "0:v", "-map", "1:a", "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "25", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fr in frames:
            proc.stdin.write(fr.tobytes())
    except BrokenPipeError:
        pass
    proc.stdin.close()
    err = proc.stderr.read().decode(errors="ignore")
    proc.wait()
    return err.strip()[-300:] if proc.returncode else ""


def build(kind: str, durs: list[float], audio: Path | None) -> str:
    total = sum(durs)
    src = kenburns if kind == "A" else video_frames

    def frames():
        for i, d in enumerate(durs):
            yield from src(i, d)

    name = "A-그림움직임.mp4" if kind == "A" else "B-클링.mp4"
    err = encode(frames(), total, audio, OUT / name)
    return f"- {name}: " + (f"실패 {err}" if err else f"{total:.0f}초 완성")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    log = [f"# 조선 화풍 AI 쇼츠 시험 ({date.today()})", "",
           "주제: 금값은 왜 하루에도 출렁일까? (원리 설명, 특정 날짜 숫자 없음)", "", "## 진행 기록", ""]
    if not key("OPENAI_API_KEY"):
        log.append("- OPENAI_API_KEY가 없어 그림을 못 그림")
    else:
        try:
            draw_images(log)
        except Exception as e:
            log.append(f"- 그림 실패: {str(e)[:300]}")
    ready = all((OUT / f"scene-{i}.png").exists() for i in range(1, len(SCENES) + 1))
    if ready and shutil.which("ffmpeg"):
        voices = [tts(s["say"]) for s in SCENES]
        durs = [max(4.0, wav_seconds(v) + 0.5) if v else 5.0 for v in voices]
        cues, t = [], 0.0
        for v, d in zip(voices, durs):
            if v:
                cues.append((v, t + 0.15, 1.0))
            t += d
        log.append(f"- 목소리: {'구글 TTS' if any(voices) else '없음(키 없음 또는 실패) → 무음'}")
        audio = mix("ffmpeg", cues, sum(durs), OUT / "voice.wav") if cues else None
        log.append(build("A", durs, audio))
        if kling_clips(durs, log) and all((OUT / f"kling-{i}.mp4").exists() for i in range(1, len(SCENES) + 1)):
            log.append(build("B", durs, audio))
        if audio:
            audio.unlink(missing_ok=True)
    log += ["", "## 대사", ""] + [f"{i}. {s['say']}" for i, s in enumerate(SCENES, 1)]
    (OUT / f"결과-{date.today()}.md").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
