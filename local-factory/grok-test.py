#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""그록 API '우리 프롬프트대로' 사진 수집 재현 테스트 (Agent Tools API 버전).

Live search(search_parameters)는 폐지됨(HTTP 410). 지금은 /v1/responses +
서버사이드 도구(web_search, x_search)로 검색한다. x_search = X(트위터) 사진에 강함.

핵심: 일반 질의가 아니라 **우리 실제 그록 프롬프트(규칙)를 그대로 먹여** 조사+사진(이미지 URL)이
      나오는지 본다. 안 되면 사진 수집은 구독(어사이드 웹) 유지.

env:  XAI_API_KEY (필수),  XAI_MODEL (기본 grok-4, 막히면 grok-4.7 등으로 교체)
실행: python -I local-factory/grok-test.py "<프롬프트파일>" "<입력>"
"""
import os, sys, json, urllib.request, urllib.error

KEY = os.environ.get("XAI_API_KEY")
MODEL = os.environ.get("XAI_MODEL", "grok-4")
ENDPOINT = "https://api.x.ai/v1/responses"
DEFAULT_PROMPT = "prompts/project/그록-패션-조사사진.md"
DEFAULT_INPUT = "최근 공항패션으로 화제된 한국 여자 연예인 1명"

def main():
    if not KEY:
        print("XAI_API_KEY 없음."); sys.exit(1)
    prompt_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT
    user_input = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_INPUT
    try:
        system_prompt = open(prompt_file, encoding="utf-8").read()
    except Exception as e:
        print(f"프롬프트 파일 못 읽음: {prompt_file} ({e})"); sys.exit(1)

    print(f"[프롬프트] {prompt_file}  [입력] {user_input}  [모델] {MODEL}\n{'='*60}")

    body = {
        "model": MODEL,
        "input": [
            {"role": "system", "content": system_prompt},   # 우리 실제 그록 프롬프트(규칙)
            {"role": "user", "content": user_input},
        ],
        "tools": [
            {"type": "web_search", "enable_image_understanding": True},
            {"type": "x_search"},   # X(트위터) 사진에 강함
        ],
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=240) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"[HTTP {e.code}] {detail[:2000]}")
        print("\n→ 이 응답 전문을 클로드에게 주면 형식/모델명 맞춰 고쳐줌.")
        sys.exit(2)
    except Exception as e:
        print(f"[요청 실패] {e}"); sys.exit(2)

    # Responses API: 결과 텍스트 추출 시도(형식 다를 수 있어 날것도 함께 출력)
    print("=== 응답 텍스트(우리 프롬프트 형식대로 나오나) ===")
    txt = data.get("output_text")
    if not txt:
        chunks = []
        for item in data.get("output", []) or []:
            for c in (item.get("content") or []):
                if isinstance(c, dict) and c.get("text"):
                    chunks.append(c["text"])
        txt = "\n".join(chunks)
    print(txt or "(텍스트 필드 못 찾음 — 아래 날것 참고)")

    print("\n=== 날것 전체(이미지 URL '.jpg/.png/.webp' 있나 찾기) ===")
    raw = json.dumps(data, ensure_ascii=False, indent=2)
    print(raw[:7000])

    low = raw.lower()
    hits = [ext for ext in (".jpg", ".jpeg", ".png", ".webp") if ext in low]
    print(f"\n[자동 체크] 이미지 확장자 발견: {hits if hits else '없음'}")
    print("판정: ①우리 프롬프트 형식대로 조사+[사진 목록]이 나왔나 ②바로 받는 이미지 URL이 있나 — 둘 다 OK면 API 전환 가능.")

if __name__ == "__main__":
    main()
