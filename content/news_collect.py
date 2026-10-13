"""신문사 제목 훅 단어 수집 (대표 요청 2026-10-13): 공개 RSS 제목만, AI 없음, 0원.

경제·연예(패션) 신문사의 공식 RSS 제목을 모아 econ/ref/titles/뉴스/<날짜>.md 에 저장하고, 블로거 단어박스와 같은 사전으로
훅 단어 비율을 센다. 문장은 복사·재사용하지 않고 단어 빈도만 본다. 피드 주소는 후보라 되는 곳/안 되는 곳을 결과에 적는다.
"""
from __future__ import annotations

import collections
import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import requests

from market.common import ROOT
from . import econ_flow as F

OUT = ROOT / "econ" / "ref" / "titles" / "뉴스"
UA = {"User-Agent": "Mozilla/5.0 (eok-econ news-headline reader; RSS)"}
FEEDS = {   # 이름: (묶음, 주소)  — 후보. 결과에 성공/실패가 적힌다
    "연합뉴스 경제": ("경제", "https://www.yna.co.kr/rss/economy.xml"),
    "연합뉴스 연예": ("연예", "https://www.yna.co.kr/rss/entertainment.xml"),
    "매일경제 경제": ("경제", "https://www.mk.co.kr/rss/30100041/"),
    "매일경제 증권": ("경제", "https://www.mk.co.kr/rss/50200011/"),
    "한국경제 경제": ("경제", "https://www.hankyung.com/feed/economy"),
    "한국경제 증권": ("경제", "https://www.hankyung.com/feed/finance"),
    "한국경제 연예": ("연예", "https://www.hankyung.com/feed/entertainment"),
    "조선비즈": ("경제", "https://biz.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    "머니투데이": ("경제", "https://rss.mt.co.kr/mt_news.xml"),
    "서울경제": ("경제", "https://www.sedaily.com/RSSFeed.xml"),
    "이데일리 경제": ("경제", "https://rss.edaily.co.kr/edaily_news.xml"),
}
# 블로거 훅 단어와 같은 사전 (경제+패션 합친 것)
CATS = {
    "감정·충격": r"소름|기막힌|충격|난리|발칵|통곡|멘붕|벌벌|덜덜|와르르|뚝뚝|폭락|폭등|폭발|쇼크|환장|피눈물|무섭|위험|지옥|최악|참담|악재|붕괴|급락|급등|터졌|터진|떴다|뜻밖|반전|깜짝|경악|후회|박살|미쳤|대박|논란",
    "정보격차·정체": r"모르|비밀|속사정|정체|진짜|숨은|힌트|알고 보니|놓치|전문가|월가|소문|내부|단독|속보|공식",
    "가림": r"이렇게|이것|이곳|이 신호|이 가격|이 때|이 날|이 \d|이 종목",
    "긴박·시점": r"오늘|내일|다음주|월요일|당장|곧|조만간|연휴|직후",
    "경고·전망": r"경고|전망|우려|주의|위기|비상|공포|전운",
}


def feed(url: str) -> list[dict]:
    r = requests.get(url, headers=UA, timeout=20)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    out = []
    for it in list(root.iter("item")) + list(root.iter("{http://www.w3.org/2005/Atom}entry")):
        t = (it.findtext("title") or it.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
        if t:
            out.append(t)
    return out[:60]


def stats(titles: list[str]) -> dict:
    n = len(titles) or 1
    return {c: sum(1 for t in titles if re.search(p, t)) * 100 // n for c, p in CATS.items()}


def words(titles: list[str]) -> collections.Counter:
    c = collections.Counter()
    for t in titles:
        for w in set(re.findall(r"[가-힣A-Za-z0-9%]{2,}", t)):
            c[w] += 1
    return c


def run() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    got: dict[str, tuple[str, list[str]]] = {}
    bad = []
    for name, (grp, url) in FEEDS.items():
        try:
            ts = feed(url)
            got[name] = (grp, ts)
            print(f"{name}: {len(ts)}개")
        except Exception as ex:
            print(f"{name} 실패: {type(ex).__name__} {str(ex)[:60]}")
            bad.append(f"{name} ({url}) — {type(ex).__name__}")
    md = [f"# 신문사 제목 수집 ({F.today()}, 공개 RSS · AI 없음)", "",
          "## 훅 단어 비율 (제목 중 해당 단어가 든 비율 %)", "",
          "| 매체 | 개수 | " + " | ".join(CATS) + " |", "|---|---|" + "---|" * len(CATS)]
    for name, (grp, ts) in got.items():
        s = stats(ts)
        md.append(f"| {name} | {len(ts)} | " + " | ".join(f"{s[c]}%" for c in CATS) + " |")
    for grp in ("경제", "연예"):
        allt = [t for g, ts in got.values() if g == grp for t in ts]
        if allt:
            top = [(w, c) for w, c in words(allt).most_common(120) if c >= 3][:60]
            md += ["", f"## {grp} 자주 나온 단어 (매체 합산 {len(allt)}개 제목)", "", " · ".join(f"{w}({c})" for w, c in top)]
    if bad:
        md += ["", "## 못 읽은 피드", ""] + [f"- {b}" for b in bad]
    for name, (grp, ts) in got.items():
        md += ["", f"## {name} 제목", ""] + [f"- {t}" for t in ts]
    (OUT / f"{F.today()}.md").write_text("\n".join(md), encoding="utf-8")
    print(f"저장: {OUT / (F.today() + '.md')} (성공 {len(got)}, 실패 {len(bad)})")
    if not got:
        raise SystemExit("읽은 피드가 하나도 없어요.")


if __name__ == "__main__":
    run()
