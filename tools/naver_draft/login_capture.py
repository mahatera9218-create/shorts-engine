# -*- coding: utf-8 -*-
"""네이버 로그인 1회 저장.

이 스크립트를 한 번 실행해 네이버에 로그인해 두면, 그 로그인 상태가
같은 폴더의 chrome-profile/ 에 저장된다. 이후 임시저장 스크립트
(draft_naver.py)는 이 프로필을 그대로 재사용하므로 비밀번호를
다시 입력할 필요가 없다. (비밀번호는 코드가 입력하지 않는다 — 사람이 직접.)

사용: py login_capture.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

PROFILE = Path(__file__).parent / "chrome-profile"


def main() -> None:
    PROFILE.mkdir(exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE),
            channel="chrome",        # PC에 설치된 크롬을 그대로 사용
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        print("=" * 50)
        print("열린 크롬 창에서 네이버에 로그인하세요.")
        print("(아이디·비밀번호는 직접 입력, 2단계 인증도 직접)")
        print("로그인이 끝나면 이 검은 창을 클릭하고 Enter 를 누르세요.")
        print("=" * 50)
        input()
        ctx.close()
        print("저장 완료:", PROFILE)
        print("이제 임시저장 프로그램을 돌릴 수 있어요.")


if __name__ == "__main__":
    main()
