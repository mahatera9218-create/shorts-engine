"""선수 사진 (대표 결정 2026-09-30): 위키미디어 공용(Wikimedia Commons)의 자유 이용 사진만, 출처 표기와 함께.

- 통로: 위키데이터 API(선수 항목의 대표 사진 P18) → 위키미디어 공용 API(라이선스·작가·축소 이미지). 둘 다 공식 공개 API.
- 쓰는 라이선스: CC BY, CC BY-SA, CC0, 퍼블릭 도메인. 그 밖(비상업 NC, 변경 금지 ND, 불명)은 쓰지 않는다.
- 동명이인 방지: 위키데이터 설명에 종목 말(야구·축구·농구·골프 / baseball·football·soccer·basketball·golf)이 있어야 한다.
  찾은 결과는 config/player_photos.yaml에 적어 두고(사람이 확인·수정 가능), 다시 찾지 않는다. 없으면 none으로 기록 → 등판 그림.
- 사진은 선수 얼굴을 알아보게 하는 용도로만 쓴다: 얼굴 합성·변형 금지, 상품·광고(쇼핑 태그) 영상에는 쓰지 않는다(보증 오해).
사용법: python -m content.playerphoto 이정후 오타니 쇼헤이 ...   (찾기만 해서 config에 적는다)
"""
from __future__ import annotations

import io
import json
import re
import sys
from datetime import date
from pathlib import Path

import requests
import yaml
from PIL import Image

from market.common import ROOT

WIKIDATA = "https://www.wikidata.org/w/api.php"
COMMONS = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "shorts-engine/1.0 (sports salary infographics; https://github.com/mahatera9218-create)"}
BOOK = ROOT / "config" / "player_photos.yaml"
OK_LICENSE = re.compile(r"^(CC BY(-SA)? \d(\.\d)?.*|CC0.*|Public domain|PD.*)$", re.I)
SPORT_WORDS = {"kbo": ("야구", "baseball"), "mlb": ("야구", "baseball"), "nba": ("농구", "basketball"),
               "golf": ("골프", "golf"), "epl": ("축구", "football", "soccer"), "laliga": ("축구", "football", "soccer"),
               "soccer": ("축구", "football", "soccer")}


def book() -> dict:
    return (yaml.safe_load(BOOK.read_text(encoding="utf-8")) or {}) if BOOK.exists() else {}


def _get(url: str, params: dict) -> dict:
    r = requests.get(url, params={**params, "format": "json"}, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def find(name: str, sport: str, en: str = "") -> dict:
    """위키데이터에서 선수 → 대표 사진 → 라이선스 확인. 결과 dict (없으면 {'none': True})."""
    words = SPORT_WORDS.get(sport, ())
    for q, lang in ((name, "ko"), (en, "en")):
        if not q:
            continue
        hits = _get(WIKIDATA, {"action": "wbsearchentities", "search": q, "language": lang, "type": "item", "limit": 7})
        ids = [h["id"] for h in hits.get("search", [])]
        if not ids:
            continue
        ents = _get(WIKIDATA, {"action": "wbgetentities", "ids": "|".join(ids), "props": "claims|descriptions",
                               "languages": "ko|en"})["entities"]
        for qid in ids:
            e = ents.get(qid, {})
            desc = " ".join(d.get("value", "") for d in e.get("descriptions", {}).values()).lower()
            p18 = e.get("claims", {}).get("P18")
            if not p18 or not any(w in desc for w in words):
                continue
            file = p18[0]["mainsnak"]["datavalue"]["value"]
            info = _get(COMMONS, {"action": "query", "titles": f"File:{file}", "prop": "imageinfo",
                                  "iiprop": "url|extmetadata", "iiurlwidth": 1080})
            ii = next(iter(info["query"]["pages"].values()))["imageinfo"][0]
            meta = ii.get("extmetadata", {})
            lic = meta.get("LicenseShortName", {}).get("value", "")
            if not OK_LICENSE.match(lic.strip()):
                return {"none": True, "why": f"라이선스 {lic}", "qid": qid, "checked": str(date.today())}
            artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "")).strip() or "작가 미상"
            return {"qid": qid, "file": file, "license": lic, "artist": artist[:80], "thumb": ii.get("thumburl") or ii["url"],
                    "page": ii.get("descriptionurl", ""), "checked": str(date.today())}
    return {"none": True, "why": "위키데이터에 종목이 맞는 사진 없음", "checked": str(date.today())}


def lookup(player: dict) -> dict | None:
    """선수(players.yaml 항목) → 사진 정보. 장부에 있으면 그대로, 없으면 찾아서 적는다. 실패하면 None."""
    b = book()
    name = player["name"]
    if name not in b:
        try:
            b[name] = find(name, player.get("sport", ""), player.get("en_full", ""))
        except (requests.RequestException, KeyError, ValueError, StopIteration) as e:
            print(f"선수 사진을 찾지 못함 ({name}: {type(e).__name__})")
            return None
        BOOK.write_text("# 선수 사진 장부 (content/playerphoto.py가 채움, 틀린 사진은 none: true로 바꾸면 다시 안 씀)\n"
                        + yaml.safe_dump(b, allow_unicode=True, sort_keys=True), encoding="utf-8")
    e = b[name]
    return None if e.get("none") else e


def fetch(folder: Path, players: list[str], tag: str = "player") -> list[Image.Image]:
    """folder/player{n}.jpg·.json을 만들고 이미지 목록을 돌려준다 (없는 선수는 빠짐)."""
    pool = {p["name"]: p for p in yaml.safe_load((ROOT / "config" / "players.yaml").read_text(encoding="utf-8"))["players"]}
    out = []
    for i, name in enumerate(players):
        jpg = folder / f"{tag}{i}.jpg"
        if not jpg.exists():
            p = pool.get(name) or next((x for x in pool.values() if x.get("short") == name), None)
            e = lookup(p) if p else None
            if not e:
                continue
            try:
                r = requests.get(e["thumb"], headers=UA, timeout=30)
                r.raise_for_status()
            except requests.RequestException:
                continue
            jpg.write_bytes(r.content)
            (folder / f"{tag}{i}.json").write_text(json.dumps({k: e[k] for k in ("artist", "license", "page", "file")},
                                                              ensure_ascii=False), encoding="utf-8")
        out.append(Image.open(io.BytesIO(jpg.read_bytes())).convert("RGB"))
    return out


def card(photo: Image.Image, size: int) -> Image.Image:
    """정사각형 카드 (위쪽 중심으로 잘라 얼굴이 들어오게, 둥근 모서리 + 흰 테두리)."""
    from PIL import ImageDraw
    side = min(photo.size)
    x = (photo.width - side) // 2
    y = 0 if photo.height > photo.width else 0
    im = photo.crop((x, y, x + side, y + side)).resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 10, fill=255)
    out = Image.new("RGBA", (size + 16, size + 16), (0, 0, 0, 0))
    ImageDraw.Draw(out).rounded_rectangle((0, 0, size + 15, size + 15), radius=size // 10 + 8, fill=(255, 255, 255, 255))
    out.paste(im, (8, 8), mask)
    return out


def main() -> None:
    pool = {p["name"]: p for p in yaml.safe_load((ROOT / "config" / "players.yaml").read_text(encoding="utf-8"))["players"]}
    for n in sys.argv[1:] or list(pool):
        p = pool.get(n)
        print(n, lookup(p) if p else "풀에 없음")


if __name__ == "__main__":
    main()
