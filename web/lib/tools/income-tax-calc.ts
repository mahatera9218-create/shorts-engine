// 종합소득세 간이 계산: 종합소득금액 − 소득공제 → 과세표준 → 누진세율 → 세액공제 → 지방소득세.
// 세율표는 공통 모듈(tax.ts)을 쓴다. 규칙 2026 기준(소득세법).
import { incomeTax, localIncomeTax, BRACKETS } from "./tax.ts";

export interface IncomeTaxInput {
  incomeAmount: number; // 종합소득금액(수입 − 필요경비, 원)
  deductions: number; // 소득공제 합계(인적공제·연금보험료 등, 원)
  taxCredits: number; // 세액공제 합계(근로·자녀·연금계좌 등, 원)
}

export interface IncomeTaxResult {
  taxBase: number; // 과세표준
  gross: number; // 산출세액
  determined: number; // 결정세액(세액공제 후)
  local: number; // 지방소득세(10%)
  total: number; // 합계
  marginalPct: number; // 한계세율(%)
  notes: string[];
}

function marginalRate(taxBase: number): number {
  if (taxBase <= 0) return 0;
  for (const [limit, rate] of BRACKETS) {
    if (limit === null || taxBase <= limit) return rate * 100;
  }
  return 0;
}

export function calcIncomeTax(p: IncomeTaxInput): IncomeTaxResult {
  const taxBase = Math.max(0, p.incomeAmount - p.deductions);
  const gross = incomeTax(taxBase);
  const determined = Math.max(0, gross - p.taxCredits);
  const local = localIncomeTax(determined);
  return {
    taxBase,
    gross,
    determined,
    local,
    total: determined + local,
    marginalPct: marginalRate(taxBase),
    notes: [
      "종합소득금액은 '수입 − 필요경비'입니다(근로소득은 총급여 − 근로소득공제). 수입 자체가 아닙니다.",
      "소득공제(인적공제·국민연금보험료 등)와 세액공제(근로·자녀·연금계좌 세액공제 등)는 본인 상황에 맞게 합산해 입력하세요.",
      "건강보험료·가산세·중간예납·기납부세액(원천징수 3.3% 등)은 반영하지 않은 대략값입니다. 실제 납부·환급액은 홈택스 신고에서 정산됩니다.",
    ],
  };
}
