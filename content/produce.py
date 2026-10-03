"""영상 제작 층 (대표 결정 2026-09-30: 클립·쇼츠 품질 A~D): 실사 배경 영상 · 효과음·편집 · 선수 사진 · AI 목소리.

- A. 실사 배경: Pexels 무료 영상(공식 API, PEXELS_API_KEY) — 경기장·관중석 등 사람이 주인공이 아닌 영상. 어둡게 깔고 그 위에 그래픽.
- B. 효과음: ffmpeg로 직접 만든 소리(슉·띵·째깍·쿵) → 저작권 걱정 없음. 배경 음악은 계속 각 앱에서.
- C. 선수 사진: content/playerphoto.py (위키미디어 공용 자유 이용 사진, 출처 표기).
- D. AI 목소리: 구글 클라우드 Text-to-Speech (GOOGLE_TTS_API_KEY, 월 무료 한도 안). 화면에 'AI 음성' 표기 (네이버 클립 규칙).
키가 없거나 받기에 실패하면 그 부분만 빼고 예전처럼 만든다 (영상 제작은 멈추지 않는다).
"""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import wave
from pathlib import Path

import requests
from PIL import Image

from market.common import ROOT, load_yaml, secret

TTS_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"
PEXELS_VIDEO = "https://api.pexels.com/videos/search"
CACHE = ROOT / ".cache" / "media"  # 효과음·목소리 캐시 (저장소에 올리지 않음)
VIDEO_QUERIES = {"야구": ["baseball stadium", "baseball stadium lights", "baseball field aerial"],
                 "축구": ["soccer stadium", "soccer match", "soccer field aerial"],  # football은 미식축구가 섞여 뺀다 (2026-10-03)
                 "농구": ["basketball court", "basketball arena"], "골프": ["golf course", "golf course aerial"]}


def cfg() -> dict:
    return load_yaml("media.yaml") if (ROOT / "config" / "media.yaml").exists() else {}


# ---------------------------------------------------------------- D. 목소리

def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / float(w.getframerate())


def tts(text: str) -> Path | None:
    """문장 → wav (캐시). 키가 없거나 실패하면 None. 'vs'는 '대'로 읽힌다."""
    key = secret("GOOGLE_TTS_API_KEY")
    text = text.replace(" vs ", " 대 ").replace("vs", "대").strip()
    if not key or not text:
        return None
    c = cfg().get("tts", {})
    voices = [c.get("voice", "ko-KR-Chirp3-HD-Charon"), c.get("fallback", "ko-KR-Neural2-C")]
    rate = c.get("rate", 1.12)
    h = hashlib.sha1(f"{voices}|{rate}|{text}".encode()).hexdigest()[:16]
    out = CACHE / "tts" / f"{h}.wav"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    for v in voices:
        body = {"input": {"text": text}, "voice": {"languageCode": "ko-KR", "name": v},
                "audioConfig": {"audioEncoding": "LINEAR16", "sampleRateHertz": 44100, "speakingRate": rate}}
        try:
            r = requests.post(TTS_URL, params={"key": key}, json=body, timeout=30)
            if r.status_code == 400 and v != voices[-1]:
                continue  # 목소리 이름·속도 설정이 안 맞으면 다음 목소리로
            r.raise_for_status()
            out.write_bytes(base64.b64decode(r.json()["audioContent"]))
            return out
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"목소리를 만들지 못함 ({type(e).__name__}) — 글자만으로 만듭니다")
            return None
    return None


def narrate(scenes: list, lines: list[str | None], pad: float = 0.35) -> list[tuple[Path, float, float]]:
    """장면마다 대사를 목소리로 → 장면 길이를 대사 길이에 맞춰 늘리고, (파일, 시작 초, 음량) 목록을 돌려준다."""
    cues, t0 = [], 0.0
    for s, line in zip(scenes, lines):
        a = tts(line) if line else None
        if a:
            s.dur = max(s.dur, wav_seconds(a) + pad)
            cues.append((a, t0 + 0.12, 1.0))
        t0 += s.dur
    for s in scenes[len(lines):]:
        t0 += s.dur
    return cues


# ---------------------------------------------------------------- B. 효과음

SFX = {  # ffmpeg lavfi로 만든다 (저작권 없음)
    "whoosh": "anoisesrc=d=0.32:c=pink:a=0.6,highpass=f=900,lowpass=f=6000,afade=t=in:d=0.12,afade=t=out:st=0.12:d=0.2",
    "ding": "sine=f=1568:d=0.45,afade=t=out:st=0.05:d=0.4,volume=0.8",
    "tick": "sine=f=1200:d=0.06,afade=t=out:st=0.02:d=0.04",
    "boom": "sine=f=55:d=0.6,afade=t=out:st=0.05:d=0.55,volume=2.5",
}


def sfx(exe: str, kind: str) -> Path:
    out = CACHE / "sfx" / f"{kind}.wav"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([exe, "-y", "-loglevel", "error", "-f", "lavfi", "-i", SFX[kind], "-ar", "44100", "-ac", "2", str(out)],
                       check=True)
    return out


def cue_times(scenes: list) -> list[float]:
    """장면 시작 시각들."""
    out, t = [], 0.0
    for s in scenes:
        out.append(t)
        t += s.dur
    return out


def mix(exe: str, cues: list[tuple[Path, float, float]], total: float, out: Path) -> Path:
    """(파일, 시작 초, 음량) 목록을 한 트랙으로. 비어 있으면 무음."""
    args = [exe, "-y", "-loglevel", "error", "-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
    parts, names = [], ["[0:a]"]
    for i, (f, start, vol) in enumerate(cues, 1):
        args += ["-i", str(f)]
        ms = max(0, int(start * 1000))
        parts.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,adelay={ms}|{ms},volume={vol}[a{i}]")
        names.append(f"[a{i}]")
    graph = ";".join(parts + [f"{''.join(names)}amix=inputs={len(names)}:normalize=0:dropout_transition=0,"
                                f"atrim=0:{total:.2f}[out]"])
    subprocess.run(args + ["-filter_complex", graph, "-map", "[out]", "-ar", "44100", str(out)], check=True)
    return out


# ---------------------------------------------------------------- A. 실사 배경 영상

PEOPLE = ("man", "men", "woman", "women", "boy", "girl", "child", "kid", "person", "people", "player", "batter",
          "pitcher", "catcher", "coach", "umpire", "athlete", "portrait", "face", "father", "son", "team", "golfer",
          "fan", "fans", "couple", "friends", "family", "selfie")


def bg_video(folder: Path, sport: str, seed: str) -> Path | None:
    """folder/bg.mp4 (세로 영상, 사람이 주인공인 영상은 주소 설명으로 거름) + bg.json(출처). 키가 없거나 실패하면 None."""
    out = folder / "bg.mp4"
    if out.exists():
        return out
    key = secret("PEXELS_API_KEY")
    if not key:
        return None
    kind = next((k for k in VIDEO_QUERIES if k in (sport or "")), "야구")
    qs = VIDEO_QUERIES[kind]
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    for q in qs[h % len(qs):] + qs[:h % len(qs)]:
        try:
            r = requests.get(PEXELS_VIDEO, headers={"Authorization": key},
                             params={"query": q, "orientation": "portrait", "size": "medium", "per_page": 30}, timeout=20)
            r.raise_for_status()
            vids = [v for v in r.json().get("videos", [])
                    if not any(w in v.get("url", "").lower().replace("-", " ").replace("/", " ").split() for w in PEOPLE)
                    and 6 <= v.get("duration", 0) <= 60]
            if not vids:
                continue
            v = vids[h % min(len(vids), 8)]
            files = sorted((f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4"
                            and (f.get("height") or 0) >= 1280 and (f.get("width") or 0) < (f.get("height") or 0)),
                           key=lambda f: f["height"])
            if not files:
                continue
            data = requests.get(files[0]["link"], timeout=60)
            data.raise_for_status()
            out.write_bytes(data.content)
            (folder / "bg.json").write_text(json.dumps({"id": v["id"], "by": v.get("user", {}).get("name", ""),
                                                        "page": v.get("url", ""), "query": q}, ensure_ascii=False),
                                            encoding="utf-8")
            return out
        except (requests.RequestException, KeyError, ValueError) as e:
            print(f"배경 영상을 받지 못함 ({type(e).__name__})")
            return None
    return None


def credits(folder: Path) -> list[str]:
    """설명란에 붙일 출처 줄 (배경 영상·선수 사진)."""
    out = []
    b = folder / "bg.json"
    if b.exists():
        i = json.loads(b.read_text(encoding="utf-8"))
        out.append(f"배경 영상: {i['by']} / Pexels ({i['page']})")
    for f in sorted(folder.glob("player*.json")):
        i = json.loads(f.read_text(encoding="utf-8"))
        out.append(f"선수 사진: {i['artist']} / {i['license']} / Wikimedia Commons ({i['page']})")
    return out


# ---------------------------------------------------------------- 인코딩

def encode(exe: str, frames, total: float, out: Path, bg: Path | None, audio: Path | None) -> str:
    """전경 프레임(RGBA, 투명)을 배경(실사 영상 또는 남색)에 얹고 소리를 붙인다."""
    from .clip import BG, FPS, H, W
    bg_in = (["-stream_loop", "-1", "-ss", "1.5", "-i", str(bg)] if bg else  # 1.5초 건너뜀: 스톡 영상 첫머리의 검은 화면·페이드
             ["-f", "lavfi", "-i", f"color=c=0x{BG[0]:02x}{BG[1]:02x}{BG[2]:02x}:s={W}x{H}:r={FPS}"])
    au_in = ["-i", str(audio)] if audio else ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    graph = (f"[1:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},setsar=1"
             + (",eq=brightness=-0.22:saturation=0.8,gblur=sigma=2" if bg else "") + "[b];"
             f"[b][0:v]overlay=format=auto:shortest=1[v]")
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           *bg_in, *au_in, "-filter_complex", graph, "-map", "[v]", "-map", "2:a", "-t", f"{total:.2f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for fr in frames:
            proc.stdin.write(fr.tobytes())
    except BrokenPipeError:
        pass
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="ignore")
        proc.wait()
    return err.strip()[-300:] if proc.returncode else ""


def ai_badge() -> Image.Image:
    from .clip import GRAY, label, pill
    t = label("AI 음성", "b", 30, GRAY)
    p = pill(t.width + 36, t.height + 18, (0, 0, 0, 150))
    p.alpha_composite(t, (18, 9))
    return p


def produce(exe: str, scenes: list, out: Path, bg: Path | None) -> tuple[str, dict]:
    """장면 → (대사 목소리 + 효과음 + 실사 배경) → mp4. 돌려주는 값: (오류 문장 또는 "", 쓴 것 요약)."""
    from . import clip
    if not cfg().get("sound", False):  # 영상만 (무음 트랙): 음악은 각 앱에서 인기 음원으로
        clip.VIDEO = bg is not None
        try:
            err = encode(exe, clip.render(scenes, rgba=True), sum(s.dur for s in scenes), out, bg, None)
        finally:
            clip.VIDEO = False
        out.with_suffix(".voice").unlink(missing_ok=True)
        return err, {"seconds": round(sum(s.dur for s in scenes), 1), "voice": False, "video_bg": bg is not None}
    cues = narrate(scenes, [getattr(s, "say", None) for s in scenes])
    voiced = bool(cues)
    starts = cue_times(scenes)
    for i, s in enumerate(scenes):
        if i and type(s).__name__ != "LoopBack":
            cues.append((sfx(exe, "whoosh"), starts[i], 0.35))
        for kind, off, vol in getattr(s, "sfx", []):
            if off < s.dur:
                cues.append((sfx(exe, kind), starts[i] + off, vol))
    total = sum(s.dur for s in scenes)
    audio = mix(exe, cues, total, out.with_suffix(".wav")) if cues else None
    clip.VIDEO = bg is not None
    try:
        err = encode(exe, clip.render(scenes, rgba=True, badge=ai_badge() if voiced else None), total, out, bg, audio)
    finally:
        clip.VIDEO = False
        if audio:
            audio.unlink(missing_ok=True)
    marker = out.with_suffix(".voice")  # 설명란에 'AI 음성' 고지를 붙이는 표시
    marker.write_text("1") if voiced and not err else marker.unlink(missing_ok=True)
    return err, {"seconds": round(total, 1), "voice": voiced, "video_bg": bg is not None}
