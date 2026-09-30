"""Claude API 연결 (판단·창작은 LLM, 14장).

- 키는 환경 변수 ANTHROPIC_API_KEY(GitHub Secrets)로만 받는다. 출력·저장하지 않는다.
- 응답은 JSON 스키마로 받는다(output_config.format). 숫자 계산은 여기서 하지 않는다.
- 같은 시스템 프롬프트(스킬 문서)는 캐시해서 두 번째 호출부터 싸게 쓴다.
- 안전 분류기가 거절하면 서버가 다른 모델로 한 번 더 시도한다(fallbacks: default).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 달러 / 100만 토큰. 캐시 읽기는 입력가의 10%, 캐시 쓰기는 125%.
PRICE = {
    "claude-opus-5-5": {"input": 4.0, "output": 20.0, "cache_read": 0.4, "cache_write": 5.0},
    "claude-sonnet-5-5": {"input": 2.0, "output": 10.0, "cache_read": 0.2, "cache_write": 2.5},
}


class LlmError(RuntimeError):
    pass


class Claude:
    def __init__(self):
        import anthropic  # 예시 모드에서는 패키지 없이도 돌게 여기서 불러온다

        self.client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 환경 변수
        self.usage = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "calls": 0}
        self.cost = 0.0
        self.by_stage: dict[str, float] = {}  # 단계별 비용 (숫자 뽑기·글쓰기·고쳐쓰기·편집장 …) → 비용 줄이기 판단용

    def ask_json(self, system: list[str], prompt: str, schema: dict, *, model: str = "claude-sonnet-5-5",
                 effort: str = "medium", max_tokens: int = 16000, stage: str = "기타") -> dict:
        blocks = [{"type": "text", "text": t} for t in system]
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
        with self.client.beta.messages.stream(
            model=model,
            max_tokens=max_tokens,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=blocks,
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            msg = stream.get_final_message()
        u = msg.usage
        used = {"input": u.input_tokens or 0, "output": u.output_tokens or 0,
                "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        self.usage["calls"] += 1
        for k, v in used.items():
            self.usage[k] += v
        price = PRICE.get(model, PRICE["claude-opus-5-5"])  # 모르는 모델은 비싼 쪽으로 어림
        spent = sum(v * price[k] for k, v in used.items()) / 1_000_000
        self.cost += spent
        self.by_stage[stage] = self.by_stage.get(stage, 0.0) + spent
        if msg.stop_reason == "refusal":
            raise LlmError("Claude가 이 요청을 거절했습니다 (주제·표현 확인 필요)")
        if msg.stop_reason == "max_tokens":
            raise LlmError("응답이 길이 한도에서 잘렸습니다")
        text = next((b.text for b in msg.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise LlmError(f"JSON 형식이 아닌 응답: {e}") from e

    def cost_usd(self) -> float:
        return self.cost


COST_LOG = Path(__file__).resolve().parents[1] / "reports" / "costs.csv"


def log_cost(kind: str, llm, made: int | str = "", target: int | str = "") -> None:
    """실행 한 번의 Claude 비용을 reports/costs.csv에 한 줄로 남긴다 (주간·월간 비용 점검, 비용 줄이기 판단).
    stages 칸: '단계=달러;…'. 가짜(예시) 실행은 남기지 않는다."""
    if not isinstance(llm, Claude) or not llm.usage["calls"]:
        return
    new = not COST_LOG.exists()
    COST_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COST_LOG.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["at", "kind", "usd", "calls", "stages", "made", "target"])
        w.writerow([datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M"), kind, f"{llm.cost:.3f}",
                    llm.usage["calls"], ";".join(f"{k}={v:.3f}" for k, v in sorted(llm.by_stage.items(), key=lambda x: -x[1])),
                    made, target])
