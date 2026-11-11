#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
배포담당 — 단일 원본(저장소) → 창별 배포 꾸러미 조립 + '바뀐 창만' 감지.

하는 일:
  1) deploy/배포맵.json을 읽는다.
  2) 각 타깃(창)의 원본 파일들을 모아 deploy/dist/<사업부>/<창>/ 에 복사(맨 위 1줄 배포 스탬프).
  3) 창별 내용 해시를 지난 배포상태(deploy/.배포상태.json)와 비교 → '바뀐 창' 목록.
  4) deploy/dist/배포-변경내역.md 작성(바뀐 창 + 전체 목록 + 붙여넣기 위치).
  5) deploy/dist/공장-배포.zip 생성.
  6) 화면에 한국어 요약(바뀐 창만 다시 붙여넣으라고).

의존성 없음(파이썬 표준 라이브러리만). 윈도우/맥/리눅스 공통.
사용: python deploy/배포.py            (배포 꾸러미 만들기)
      python deploy/배포.py --commit-state  (상태 저장 후 '이번 배포를 기준으로' 갱신 — 보통 배포 커맨드가 처리)
"""
import json, os, sys, hashlib, shutil, zipfile, subprocess, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = os.path.join(ROOT, "deploy", "배포맵.json")
DIST = os.path.join(ROOT, "deploy", "dist")
STATE = os.path.join(ROOT, "deploy", ".배포상태.json")
ZIP = os.path.join(DIST, "공장-배포.zip")
CHANGELOG = os.path.join(DIST, "배포-변경내역.md")


def git_hash():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
    except Exception:
        return "nogit"


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    commit_state = "--commit-state" in sys.argv
    today = datetime.date.today().isoformat()
    gh = git_hash()

    with open(MAP, "r", encoding="utf-8") as f:
        m = json.load(f)

    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST, exist_ok=True)

    prev = {}
    if os.path.exists(STATE):
        try:
            prev = json.load(open(STATE, "r", encoding="utf-8")).get("창", {})
        except Exception:
            prev = {}

    now_state = {}
    changed, unchanged, missing = [], [], []
    targets = []  # (사업부, 타깃)

    for bu in m["사업부"]:
        for t in bu["타깃"]:
            targets.append((bu["이름"], t))

    for bu_name, t in targets:
        key = bu_name + "/" + t["창"]
        out_dir = os.path.join(DIST, bu_name, t["창"])
        os.makedirs(out_dir, exist_ok=True)
        h = hashlib.sha256()
        files_done = []
        for rel in t["원본"]:
            src = os.path.join(ROOT, rel)
            base = os.path.basename(rel)
            if not os.path.exists(src):
                missing.append(rel + "  (→ " + key + ")")
                continue
            body = read(src)
            h.update((rel + "\n" + body).encode("utf-8"))
            stamp = "<!-- 배포원본: %s · %s · %s -->\n" % (rel, gh, today)
            with open(os.path.join(out_dir, base), "w", encoding="utf-8") as f:
                f.write(stamp + body)
            files_done.append(base)
        digest = h.hexdigest()[:16]
        now_state[key] = digest
        rec = {"key": key, "type": t["type"], "창": t["창"], "위치": t["붙여넣기위치"], "files": files_done}
        if key not in prev:
            rec["status"] = "신규"
            changed.append(rec)
        elif prev[key] != digest:
            rec["status"] = "변경"
            changed.append(rec)
        else:
            rec["status"] = "동일"
            unchanged.append(rec)

    # 붙여넣기 필요한 것(그록/어사이드)과 자동(claude_auto) 구분
    def needs_paste(r):
        return r["type"] in ("grok", "aside")

    changed_paste = [r for r in changed if needs_paste(r)]
    changed_auto = [r for r in changed if not needs_paste(r)]

    # 변경내역.md
    lines = []
    lines.append("# 배포 변경내역 — %s (%s)\n" % (today, gh))
    lines.append("원본 저장소 1곳 → 창별 꾸러미. **붙여넣기 필요한 건 그록·어사이드뿐**(참고=Claude Code 자동).\n")
    lines.append("## ✅ 다시 붙여넣을 창 (여기만!)\n")
    if changed_paste:
        for r in changed_paste:
            lines.append("- **[%s] %s** → %s  _(%s)_" % (r["status"], r["창"], r["위치"], ", ".join(r["files"])))
    else:
        lines.append("- (없음) 붙여넣을 외부 창은 바뀐 게 없어요.")
    lines.append("\n## 🔄 Claude Code 자동 반영(붙여넣기 X — git pull이면 끝)\n")
    if changed_auto:
        for r in changed_auto:
            lines.append("- [%s] %s  _(%s)_" % (r["status"], r["창"], ", ".join(r["files"])))
    else:
        lines.append("- (없음)")
    lines.append("\n## 전체 창 목록\n")
    for r in changed + unchanged:
        tag = {"grok": "그록", "aside": "어사이드", "claude_auto": "참고(자동)"}.get(r["type"], r["type"])
        lines.append("- [%s] (%s) %s → %s" % (r["status"], tag, r["창"], r["위치"]))
    if missing:
        lines.append("\n## ⚠️ 원본 없음(맵 확인 필요)\n")
        for x in missing:
            lines.append("- " + x)
    with open(CHANGELOG, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # zip
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(DIST):
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if os.path.abspath(full) == os.path.abspath(ZIP):
                    continue
                z.write(full, os.path.relpath(full, DIST))

    if commit_state:
        json.dump({"갱신일": today, "git": gh, "창": now_state},
                  open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # 화면 요약
    print("=" * 48)
    print("배포 꾸러미 완성: deploy/dist/공장-배포.zip")
    print("변경내역: deploy/dist/배포-변경내역.md")
    print("-" * 48)
    if changed_paste:
        print("✅ 다시 붙여넣을 창 (여기만):")
        for r in changed_paste:
            print("   - [%s] %s → %s" % (r["status"], r["창"], r["위치"]))
    else:
        print("✅ 붙여넣을 외부 창: 바뀐 것 없음")
    if changed_auto:
        print("🔄 Claude Code 자동(붙여넣기 X): %d개" % len(changed_auto))
    if missing:
        print("⚠️ 원본 없음 %d건 — 배포맵.json 확인" % len(missing))
    if not commit_state:
        print("-" * 48)
        print("(상태 미저장: 다음에도 같은 '바뀐 창'이 뜨려면 --commit-state 로 기준 갱신)")
    print("=" * 48)
    return 0


if __name__ == "__main__":
    sys.exit(main())
