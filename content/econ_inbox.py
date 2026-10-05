"""억선생의 경제판 '받은 편지함' (대표 결정 2026-10-05): 도우미 버튼 → GitHub 이슈 → 여기서 처리.

- capture <이슈번호> : [경제캡처] 이슈에 붙인 크리에이터 어드바이저·통계 캡처 사진 → Claude가 읽어
                       키워드는 오늘 키워드 목록에(대표 몫), 숫자(조회수·유입 검색어 등)는 econ/metrics/에 저장
- ref <파일>         : [경제참고] 이슈 본문(Aside가 아침마다 조사한 참고 블로거 md) → econ/ref/<날짜>.md
                       글쓰기 때 '구조·흐름만' 참고 (문장은 안 옮김)
- edit <제목> <파일> : [경제수정] <글> 이슈(도우미에서 고친 제목·문단) → 글에 반영 + edits.md (다음 글이 배움)
- learn              : 지난 7일 고친 곳 + 성과 숫자 → 글쓰기 규칙 제안 → reports/경제-학습/<날짜>.md (주간 점검이 읽음)
캡처 사진은 이슈의 본문 HTML에 든 '잠깐만 열리는 주소'로 받는다(비공개 저장소라 일반 주소는 안 열림). 키는 Secrets에서만.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

from market.common import ROOT
from . import econ_flow as F

METRICS = ROOT / "econ" / "metrics"
REF = ROOT / "econ" / "ref"
FOOTER = ("아래 초록색", "여기를 지우고")  # 도우미가 미리 채운 안내 줄

CAPTURE = {"type": "object", "additionalProperties": False, "required": ["kind", "keywords", "posts", "inflow", "note"],
           "properties": {
               "kind": {"type": "string", "description": "무슨 화면인가 (예: 크리에이터 어드바이저 트렌드, 블로그 통계 조회수, 유입 검색어)"},
               "keywords": {"type": "array", "description": "글감이 될 만한 키워드 (경제·돈 관련만)",
                            "items": {"type": "object", "additionalProperties": False, "required": ["kw", "why"],
                                      "properties": {"kw": {"type": "string"}, "why": {"type": "string"}}}},
               "posts": {"type": "array", "description": "글별 숫자가 보이면 (안 보이는 칸은 빈 문자열)",
                         "items": {"type": "object", "additionalProperties": False,
                                   "required": ["title", "date", "views", "ctr", "other"],
                                   "properties": {"title": {"type": "string"}, "date": {"type": "string"},
                                                  "views": {"type": "string"}, "ctr": {"type": "string"},
                                                  "other": {"type": "string"}}}},
               "inflow": {"type": "array", "description": "유입 검색어·유입 경로가 보이면 [검색어, 비율 또는 수]",
                          "items": {"type": "array", "items": {"type": "string"}}},
               "note": {"type": "string", "description": "화면에서 읽은 기간·기준 시각 등 한 줄"}}}


def _issue_images(num: int) -> list[bytes]:
    """이슈 본문에 붙인 사진들. full+json으로 받으면 본문 HTML에 잠깐 유효한 서명 주소가 들어 있다."""
    repo, tok = os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]
    r = requests.get(f"https://api.github.com/repos/{repo}/issues/{num}", timeout=30,
                     headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github.full+json"})
    r.raise_for_status()
    srcs = re.findall(r'<img[^>]+src="([^"]+)"', r.json().get("body_html") or "")
    out = []
    for s in srcs[:8]:
        g = requests.get(s.replace("&amp;", "&"), timeout=60)
        if g.ok and g.headers.get("content-type", "").startswith("image/"):
            out.append(g.content)
    return out


def _media(b: bytes) -> str:
    return "image/png" if b[:4] == b"\x89PNG" else "image/webp" if b[8:12] == b"WEBP" else "image/jpeg"


def capture(num: int) -> str:
    imgs = _issue_images(num)
    if not imgs:
        return "사진을 찾지 못했어요. 이슈 본문에 캡처를 붙였는지 확인해 주세요."
    import anthropic
    c = anthropic.Anthropic()
    content = [{"type": "image", "source": {"type": "base64", "media_type": _media(b), "data": base64.b64encode(b).decode()}}
               for b in imgs]
    content.append({"type": "text", "text": (
        "네이버 크리에이터 어드바이저(또는 블로그 통계) 캡처입니다. 화면에 보이는 것만 그대로 읽어 주세요. "
        "추측해서 채우지 말고, 안 보이는 칸은 빈 문자열. 키워드는 경제·돈·주식·코인·금·환율·금리 관련만.")})
    msg = c.messages.create(model="claude-sonnet-5-5", max_tokens=4000,
                            messages=[{"role": "user", "content": content}],
                            output_config={"format": {"type": "json_schema", "schema": CAPTURE}})
    u = msg.usage
    F.SPENT["claude"] += (u.input_tokens * 2.0 + u.output_tokens * 10.0) / 1_000_000
    data = json.loads("".join(b.text for b in msg.content if getattr(b, "type", "") == "text"))
    now = datetime.now(F.KST)
    f = METRICS / f"{now:%Y-%m-%d}-{num}.yaml"
    F.save(f, {"at": now.strftime("%Y-%m-%d %H:%M"), "issue": num, **data})
    if data["keywords"]:
        F.add("\n".join(k["kw"] for k in data["keywords"][:10]))
        kwf = F.FLOW / F.today() / "keywords.yaml"
        K = F.load(kwf, {"items": []})
        why = {k["kw"]: k["why"] for k in data["keywords"]}
        for it in K["items"]:
            if it["kw"] in why and not it.get("why"):
                it["why"] = "📷 캡처: " + why[it["kw"]]
        F.save(kwf, K)
    F.log_cost("capture", f"#{num}")
    return (f"캡처 {len(imgs)}장을 읽었어요 ({data['kind']}). 키워드 {len(data['keywords'])}개를 오늘 목록에 넣고, "
            f"숫자 {len(data['posts'])}줄·유입 검색어 {len(data['inflow'])}개를 성과 화면에 저장했어요.")


def ref(path: str) -> str:
    text = Path(path).read_text(encoding="utf-8").replace("\r\n", "\n")
    text = "\n".join(l for l in text.splitlines() if not any(x in l for x in FOOTER)).strip()
    if len(text) < 30:
        return "붙여 넣은 내용이 없어요."
    REF.mkdir(parents=True, exist_ok=True)
    f = REF / f"{F.today()}.md"
    f.write_text((f.read_text(encoding="utf-8") + "\n\n---\n\n" if f.exists() else "") + text + "\n", encoding="utf-8")
    return f"Aside 조사({len(text):,}자)를 저장했어요. 다음 글부터 구조·흐름 참고로 써요 (문장은 안 옮겨요)."


def edit(title: str, path: str) -> str:
    from .edits import parse, apply
    m = re.match(r"^\[경제수정\]\s*(\d{4}-\d{2}-\d{2}-[0-9A-Za-z가-힣-]+)\s*$", title.strip())
    if not m or not (F.POSTS / m.group(1) / "post.md").exists():
        return "형식이 다르거나 없는 글이에요."
    t, blocks = parse(Path(path).read_text(encoding="utf-8"))
    done = apply(F.POSTS / m.group(1), t, blocks)
    return f"반영: {', '.join(done)}. 다음 글부터 이렇게 고친 방향을 배워요." if done else "바뀐 것이 없어요."


def week_numbers(since: str) -> str:
    """코드가 센 지난 7일 숫자: 만든 글·발행한 글·정보 이득 보류·비용."""
    import csv
    import yaml
    made = [f for f in F.POSTS.iterdir() if f.is_dir() and f.name[:10] >= since] if F.POSTS.exists() else []
    used = [f for f in made if (f / "status.yaml").exists()
            and (yaml.safe_load((f / "status.yaml").read_text(encoding="utf-8")) or {}).get("status") == "used"]
    held = [f for f in made if "정보 이득 부족" in ((f / "post.md").read_text(encoding="utf-8") if (f / "post.md").exists() else "")]
    rows = [r for r in csv.DictReader(F.COSTS.open(encoding="utf-8")) if r["date"] >= since] if F.COSTS.exists() else []
    won = int(sum(float(r["total_usd"]) for r in rows) * F.KRW)
    return (f"- 만든 글 {len(made)}편 · 발행 {len(used)}편 (목표 하루 3편 = 21편) · 정보 이득 보류 {len(held)}편\n"
            f"- AI 비용 {won:,}원 (1편 평균 {won // max(1, len(made)):,}원) · 이번 달 누적 {F.month_spent_krw():,}원 / 상한 {F.MONTH_CAP_KRW:,}원")


def learn() -> Path:
    """지난 7일: 대표가 고친 곳 + 성과 숫자 → 글쓰기·제목 규칙 제안 (적용은 주간 점검에서 대표 확인 후, 설계서 15.6)."""
    since = (datetime.now(F.KST) - timedelta(days=7)).strftime("%Y-%m-%d")
    edits = [f"### {f.parent.name}\n{f.read_text(encoding='utf-8')[-3000:]}" for f in sorted(F.POSTS.glob("*/edits.md"))
             if f.parent.name[:10] >= since]
    mets = [f.read_text(encoding="utf-8")[:3000] for f in sorted(METRICS.glob("*.yaml")) if f.name[:10] >= since]
    out = ROOT / "reports" / "경제-학습" / f"{F.today()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    head = [f"# 경제판 주간 점검·학습 ({F.today()})", "", week_numbers(since), ""]
    if not edits and not mets:
        out.write_text("\n".join(head) + "\n이번 주는 고친 곳·성과 캡처가 없어 배울 거리가 없어요.\n", encoding="utf-8")
        return out
    from .llm import Claude
    c = Claude()
    res = c.ask_json(
        [F.skill("blog-voice"), F.skill("money-content-writer")],
        "대표가 이번 주 고친 곳(원래 → 고친 글)과 성과 숫자입니다. 반복되는 방향만 골라 글쓰기·제목 규칙으로 바꿔 주세요. "
        "한 번뿐인 고침은 규칙으로 만들지 않습니다. 근거(어느 글 몇 번)를 꼭 붙이세요.\n\n[고친 곳]\n"
        + ("\n\n".join(edits) or "없음") + "\n\n[성과 숫자]\n" + ("\n\n".join(mets) or "없음"),
        {"type": "object", "additionalProperties": False, "required": ["rules", "titles", "summary"],
         "properties": {"summary": {"type": "string"},
                        "rules": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                                             "required": ["rule", "evidence", "skill"],
                                                             "properties": {"rule": {"type": "string"},
                                                                            "evidence": {"type": "string"},
                                                                            "skill": {"type": "string"}}}},
                        "titles": {"type": "array", "items": {"type": "string"},
                                   "description": "성과로 본 잘 되는 제목·키워드 패턴"}}},
        stage="주간 학습", max_tokens=6000)
    F.SPENT["claude"] += c.cost_usd()
    F.log_cost("learn", since)
    lines = head + [res["summary"], "", "## 규칙 제안 (대표 확인 후 스킬에 반영)", ""]
    lines += [f"- **{r['rule']}** — 근거: {r['evidence']} → `{r['skill']}`" for r in res["rules"]] or ["- 없음"]
    lines += ["", "## 잘 되는 제목·키워드 패턴", ""] + ([f"- {t}" for t in res["titles"]] or ["- 아직 숫자가 부족해요"])
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> None:
    cmd = sys.argv[1]
    if cmd != "edit":
        F.guard()
    if cmd == "capture":
        msg = capture(int(sys.argv[2]))
    elif cmd == "ref":
        msg = ref(sys.argv[2])
    elif cmd == "edit":
        msg = edit(sys.argv[2], sys.argv[3])
    elif cmd == "learn":
        msg = f"학습 보고: {learn()}"
    else:
        raise SystemExit(f"모르는 명령: {cmd}")
    print(msg)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"msg<<EOF_X\n{msg}\nEOF_X\n")


if __name__ == "__main__":
    main()
