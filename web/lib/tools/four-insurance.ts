// 4대보험료(근로자 부담) 대략 계산: 월 보수 × 요율. 요율은 해마다 바뀌므로 '확인 필요'로 안내.
// 아래 요율은 참고용 기준값(최근). 실제는 공단 고시 요율로 계산된다.

export interface FourInput {
  monthlyPay: number; // 월 보수(과세소득, 원)
}

// 근로자 부담 요율(참고). 국민연금 4.5%, 건강 3.545%, 장기요양=건강×12.95%, 고용 0.9%.
export const RATES = {
  pension: 0.045,
  health: 0.03545,
  ltcOfHealth: 0.1295,
  employment: 0.009,
};

export interface FourResult {
  pension: number;
  health: number;
  ltc: number;
  employment: number;
  employeeTotal: number;
  notes: string[];
}

export function calcFourInsurance(p: FourInput): FourResult {
  const pay = Math.max(0, p.monthlyPay);
  const pension = Math.round(pay * RATES.pension);
  const health = Math.round(pay * RATES.health);
  const ltc = Math.round(health * RATES.ltcOfHealth);
  const employment = Math.round(pay * RATES.employment);
  return {
    pension,
    health,
    ltc,
    employment,
    employeeTotal: pension + health + ltc + employment,
    notes: [
      "근로자 본인 부담분입니다. 사업주도 대체로 비슷한 금액(+산재보험)을 함께 부담합니다.",
      "보험료율은 해마다 바뀝니다(국민연금 4.5%, 건강 3.545%, 장기요양 건강보험료의 12.95%, 고용 0.9% 기준). 올해 요율은 공단에서 확인하세요.",
      "국민연금은 기준소득월액 상·하한이 있어 아주 높거나 낮은 보수는 실제와 다를 수 있습니다. 비과세 수당은 보수에서 빠집니다.",
    ],
  };
}
