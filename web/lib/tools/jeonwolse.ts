// 전월세 전환 계산: 전세↔월세 전환. 월세 = 전환보증금 × 전환율 ÷ 12. 규칙 2026 기준(주택임대차보호법).
// 전환율 법정 상한 = 기준금리 + 2%(대략). 실제는 계약·지역에 따라 다를 수 있어 '확인'으로 안내.

export interface ConvInput {
  direction: "toMonthly" | "toDeposit"; // 전세→월세 / 월세→전세
  amount: number; // toMonthly: 월세로 돌릴 보증금(원), toDeposit: 월세(원/월)
  ratePct: number; // 전환율(%)
}

export interface ConvResult {
  direction: "toMonthly" | "toDeposit";
  value: number; // toMonthly=월세(원/월), toDeposit=전환 보증금(원)
  ratePct: number;
  notes: string[];
}

export function calcConversion(p: ConvInput): ConvResult {
  const r = Math.max(0, p.ratePct) / 100;
  const notes = [
    "전환율의 법정 상한은 '기준금리 + 2%' 수준입니다(대략). 실제 계약은 상한 안에서 협의로 정합니다.",
    "지역·계약 조건에 따라 달라질 수 있으니 계약 전 확인하세요. 이 계산은 참고용입니다.",
  ];
  if (p.direction === "toMonthly") {
    return { direction: p.direction, value: Math.round((p.amount * r) / 12), ratePct: p.ratePct, notes };
  }
  return { direction: p.direction, value: r > 0 ? Math.round((p.amount * 12) / r) : 0, ratePct: p.ratePct, notes };
}
