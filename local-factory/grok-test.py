#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""그록 API '우리 프롬프트대로' 사진 수집 재현 테스트 (집 PC 실행).

핵심: 일반 질의가 아니라 **우리가 실제로 쓰는 그록 프롬프트(규칙)를 API에 그대로 먹여서**,
      구독 웹에서 하던 것과 '동일하게' 조사+사진(실제 이미지 URL)을 수집하는지 확인한다.
      → 이게 API로 재현 안 되면 전환은 무의미(구독 유지).

쓰는 법 (집 PC):
    1) 키:  PowerShell  $env:XAI_API_KEY="xai-..."   /   bash  export XAI_API_KEY="xai-..."
    2) 실행:
        python -I local-factory/grok-test.py "<프롬프트파일>" "<입력(셀럽/키워드)>"
       예) python -I local-factory/grok-test.py prompts/project/그록-패션-조사사진.md "아이유"
       기본값: 프롬프트=그록-패션-조사사진.md, 입력="최근 공항패션 화제 여자 연예인 1명"

보는 법: 출력이 **우리 프롬프트가 기대하는 형식(조사 블록 + [사진 목록] + 직접 이미지 URL + 출처)**과
         같은지, 특히 **바로 다운로드되는 이미지 URL(.jpg/.png/.webp)**이 나오는지 본다.
         - 프롬프트대로 잘 나오면 → API 전환 가능.
         - 형식이 깨지거나 이미지 URL이 안 나오면 → 사진 수집은 구독(웹) 유지.

주의: 소액 요금 발생. 한두 번만.
"""
import os, sys, json, urllib.request, urllib.error

KEY = os.environ.get("XAI_API_KEY")
MODEL = os.environ.get("XAI_MODEL", "grok-4")  # 모델명 바뀌면 XAI_MODEL로 교체
ENDPOINT = "https://api.x.ai/v1/chat/completions"
DEFAULT_PROMPT = "prompts/project/그록-패션-조사사진.md"
DEFAULT_INPUT = "최근 공항패션으로 화제된 한국 여자 연예인 1명"

def main():
    if not KEY:
        print("XAI_API_KEY 환경변수가 없습니다(설명은 파일 상단)."); sys.exit(1)

    prompt_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PROMPT
    user_input = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_INPUT
    try:
        system_prompt = open(prompt_file, encoding="utf-8").read()
    except Exception as e:
        print(f"프롬프트 파일을 못 읽음: {prompt_file} ({e})"); sys.exit(1)

    print(f"[프롬프트] {prompt_file}  [입력] {user_input}\n{'='*60}")

    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},   # ← 우리 실제 그록 프롬프트(규칙) 그대로
            {"role": "user", "content": user_input},
        ],
        "search_parameters": {   # 라이브 검색(웹/X)으로 실제 사진 찾게
            "mode": "on",
            "return_citations": True,
            "sources": [{"type": "web"}, {"type": "x"}, {"type": "news"}],
        },
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        print(f"[HTTP {e.code}] {detail[:1500]}")
        if e.code in (400, 404, 410):
            print("\n→ search_parameters 방식이 막혔을 수 있음(API 개편). 이 응답 전문을 클로드에게 주면 "
                  "현재 docs.x.ai 방식(Responses API 등)으로 스크립트를 고쳐줌. 모델명 문제면 XAI_MODEL로 교체.")
        sys.exit(2)
    except Exception as e:
        print(f"[요청 실패] {e}"); sys.exit(2)

    print("=== 응답 본문 (우리 프롬프트 형식대로 나오나 비교) ===")
    try:
        print(data["choices"][0]["message"]["content"])
    except Exception:
        pass
    print("\n=== 인용/출처(citations — 이미지 URL 들어오나) ===")
    cites = data.get("citations") or data.get("choices",[{}])[0].get("message",{}).get("citations", [])
    print(json.dumps(cites, ensure_ascii=False, indent=2))
    print("\n=== 응답 날것 일부(이미지 URL 검색용) ===")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:4000])
    print("\n판정: ①우리 프롬프트 형식대로 조사+[사진 목록]이 나왔나 ②'.jpg/.png/.webp'로 끝나는 "
          "바로 받을 수 있는 이미지 URL이 있나 — 둘 다 OK면 API 전환 가능.")

if __name__ == "__main__":
    main()
