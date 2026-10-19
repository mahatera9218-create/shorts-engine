# -*- coding: utf-8 -*-
"""네이버 블로그 '임시저장' 자동화 (v1, 텍스트만).

하는 일:
  1) 저장된 로그인(chrome-profile)으로 크롬을 연다.
  2) 오늘(생성일=오늘, KST) 건강 초안을 읽어 '추천' 제목 + 본문을 꺼낸다.
  3) 네이버 블로그 글쓰기(스마트에디터)에 제목·본문을 넣고 **임시저장**한다.
     - **발행 버튼은 절대 누르지 않는다.** (사람이 사진 넣고 검토 후 직접 발행)
     - 이미 올린 제목(naver_done.txt)은 건너뛴다.
  4) 각 단계 스크린샷을 debug/ 에 남긴다(문제 생기면 이걸로 selector를 맞춘다).

사용:
  py draft_naver.py                 # 오늘 건강 초안 전부 임시저장
  py draft_naver.py --dry           # 임시저장 직전까지만(저장 안 누름) — 처음 테스트용
  py draft_naver.py --once <파일>   # 특정 초안 1개만

※ 스마트에디터는 버전마다 화면이 달라서, selector는 네 PC에서 1~2번
  맞춰야 할 수 있다. debug/ 스크린샷을 Claude에게 주면 고친다.
"""
import argparse
import datetime as dt
import re
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent              # tools/naver_draft -> repo root


def parse_draft(md: str) -> dict:
    """초안 .md에서 생성일·제목 후보·추천·본문만 뽑는다(자립형 파서).

    content/health_desk.py의 파싱 규칙과 동일하되, 무거운 import 없이 쓰려고
    필요한 부분만 가져왔다. 형식이 바뀌면 health_desk.py와 함께 맞춘다.
    """
    d = {"생성일": "", "후보": [], "추천": "", "본문": ""}
    m = re.search(r"^생성일\s*[:：]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", md, re.M)
    if m:
        d["생성일"] = m.group(1).strip()
    head = re.split(r"^---\s*$", md, maxsplit=1, flags=re.M)[0]
    collecting = False
    for ln in head.splitlines():
        if re.match(r"^\s*제목\s*후보\s*[:：]?\s*$", ln):
            collecting = True
            continue
        if collecting:
            mm = re.match(r"^\s*(?:\d+[.)]|[-*])\s*(.+?)\s*$", ln)
            if mm and mm.group(1).strip():
                d["후보"].append(mm.group(1).strip())
            elif ln.strip() == "":
                continue
            else:
                collecting = False
    rec = re.search(r"추천\s*[:：]?\s*(\d+)\s*번?", head)
    if rec:
        d["추천"] = rec.group(1)
    if not d["후보"]:
        m = re.search(r"^제목\(선정\):\s*(.+)$", md, re.M)
        if m:
            d["후보"] = [m.group(1).strip()]
    parts = re.split(r"^---\s*$", md, maxsplit=1, flags=re.M)
    rest = parts[1] if len(parts) > 1 else md
    body = re.split(r"^---\s*이미지 프롬프트\s*---\s*$", rest, maxsplit=1, flags=re.M)[0]
    d["본문"] = body.strip("\n")
    return d

# ---- 설정 ---------------------------------------------------------------
BLOG_ID = "mahatera"                                   # 건강 블로그 아이디
DRAFT_DIR = REPO / "reports" / "건강글-초안"
PROFILE = HERE / "chrome-profile"                      # login_capture.py가 만든 로그인
DEBUG = HERE / "debug"
DONE_FILE = HERE / "naver_done.txt"                    # 이미 올린 제목 기록(중복 방지)
WRITE_URL = f"https://blog.naver.com/{BLOG_ID}?Redirect=Write"
# ------------------------------------------------------------------------


def kst_today() -> str:
    return (dt.datetime.utcnow() + dt.timedelta(hours=9)).strftime("%Y-%m-%d")


def load_done() -> set:
    if DONE_FILE.exists():
        return set(DONE_FILE.read_text(encoding="utf-8").splitlines())
    return set()


def mark_done(title: str) -> None:
    with DONE_FILE.open("a", encoding="utf-8") as f:
        f.write(title + "\n")


def todays_drafts(once: str | None) -> list[tuple[Path, dict]]:
    if once:
        p = Path(once)
        if not p.is_absolute():
            p = DRAFT_DIR / once
        return [(p, parse_draft(p.read_text(encoding="utf-8")))]
    out = []
    today = kst_today()
    for p in sorted(DRAFT_DIR.glob("*.md")):
        d = parse_draft(p.read_text(encoding="utf-8"))
        if d.get("생성일") == today and d.get("후보"):
            out.append((p, d))
    return out


def pick_title(d: dict) -> str:
    cands = d.get("후보") or []
    rec = d.get("추천")
    if rec and rec.isdigit() and 1 <= int(rec) <= len(cands):
        return cands[int(rec) - 1]
    return cands[0] if cands else ""


def shot(page, name: str) -> None:
    DEBUG.mkdir(exist_ok=True)
    try:
        page.screenshot(path=str(DEBUG / f"{name}.png"), full_page=False)
    except Exception:
        pass


def fill_one(page, title: str, body: str, dry: bool) -> None:
    """스마트에디터에 제목·본문을 넣고 임시저장. (selector는 여러 후보로 시도)"""
    page.goto(WRITE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(4000)

    # 에디터는 보통 iframe(mainFrame) 안에 있다. 있으면 그 안에서, 없으면 페이지에서.
    frame = page
    try:
        page.wait_for_selector("iframe#mainFrame", timeout=5000)
        frame = page.frame(name="mainFrame") or page.frame_locator("#mainFrame")
    except PwTimeout:
        pass
    shot(page, "1_editor_open")

    # '작성 중인 글이 있습니다' 팝업이 뜨면 '취소'(새 글로 시작)
    for sel in ["button:has-text('취소')", ".se-popup-button-cancel",
                "button:has-text('아니오')"]:
        try:
            el = frame.locator(sel)
            if el.count() and el.first.is_visible():
                el.first.click(timeout=2000)
                break
        except Exception:
            pass
    page.wait_for_timeout(1000)

    # 제목 입력 (여러 후보 selector 중 먼저 되는 것)
    for sel in [".se-documentTitle .se-text-paragraph",
                ".se-section-documentTitle .se-text-paragraph",
                "[contenteditable='true'][data-a11y-title]",
                "span.se-placeholder:has-text('제목')"]:
        try:
            el = frame.locator(sel).first
            if el.count():
                el.click(timeout=3000)
                page.keyboard.type(title, delay=10)
                break
        except Exception:
            continue
    shot(page, "2_title")

    # 본문 입력
    for sel in [".se-section-text .se-text-paragraph",
                ".se-component.se-text .se-text-paragraph",
                "span.se-placeholder:has-text('내용')"]:
        try:
            el = frame.locator(sel).first
            if el.count():
                el.click(timeout=3000)
                page.keyboard.type(body, delay=2)
                break
        except Exception:
            continue
    shot(page, "3_body")

    if dry:
        print("   [dry] 임시저장 직전에서 멈춤(저장 안 누름). debug/ 확인.")
        return

    # 임시저장 ('저장' 버튼). '발행'은 절대 누르지 않는다.
    saved = False
    for sel in ["button:has-text('저장')", ".save_btn__bzc5B",
                "button.se-save-button"]:
        try:
            el = frame.locator(sel).first
            if el.count() and el.first.is_visible():
                txt = (el.inner_text() or "").strip()
                if "발행" in txt:          # 안전장치: 발행 글자 있으면 거른다
                    continue
                el.click(timeout=3000)
                saved = True
                break
        except Exception:
            continue
    page.wait_for_timeout(2500)
    shot(page, "4_saved")
    print("   임시저장:", "완료" if saved else "버튼 못 찾음(debug/ 스샷 확인)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="임시저장 직전까지만")
    ap.add_argument("--once", help="특정 초안 파일 하나만")
    args = ap.parse_args()

    drafts = todays_drafts(args.once)
    if not drafts:
        print("오늘(", kst_today(), ") 올릴 건강 초안이 없어요.")
        return
    done = load_done()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), channel="chrome",
            headless=False, no_viewport=True, args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 로그인 확인
        page.goto("https://blog.naver.com/" + BLOG_ID, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        if "nidlogin" in page.url or "로그인" in (page.title() or ""):
            print("[!] 네이버 로그인이 안 돼 있어요. 먼저: py login_capture.py")
            ctx.close()
            return

        for path, d in drafts:
            title = pick_title(d)
            body = d.get("본문", "")
            if not title or not body:
                print("건너뜀(제목/본문 비어 있음):", path.name)
                continue
            if title in done:
                print("건너뜀(이미 올림):", title)
                continue
            print("임시저장 시도:", title)
            try:
                fill_one(page, title, body, args.dry)
                if not args.dry:
                    mark_done(title)
            except Exception as e:
                print("   실패:", e, "(debug/ 스샷 확인)")

        ctx.close()
    print("끝. (발행은 네이버에서 대표가 사진 넣고 직접)")


if __name__ == "__main__":
    main()
