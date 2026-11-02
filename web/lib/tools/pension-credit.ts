// 연금저축·IRP 세액공제·환급 계산. 규칙 2026 기준(소득세법 제59조의3).
// 한도: 연금저축 납입 600만원, 연금저축+IRP 합산 900만원.
// 공제율: 총급여 5,500만원(종합소득 4,500만원) 이하 16.5%, 초과 13.2%(지방소득세 포함).

export interface PensionInput {
  pensionSaving: number; // 연금저축 납입액(원)
  irp: number; // IRP 등 추가 납입액(원)
  lowIncome: boolean; // 총급여 5,500만원(종합소득 4,500만원) 이하이면 true → 16.5%
}

export const PENSION_CAP = 6_000_000; // 연금저축 세액공제 대상 한도
export const TOTAL_CAP = 9_000_000; // 연금저축+IRP 합산 한도

export interface PensionResult {
  eligiblePension: number; // 공제 대상 연금저축
  eligibleIrp: number; // 공제 대상 IRP
  eligibleTotal: number; // 공제 대상 합계(≤900만)
  ratePct: number; // 16.5 / 13.2
  refund: number; // 돌려받는(덜 내는) 세금
  excess: number; // 한도 초과로 공제 못 받는 납입액
  notes: string[];
}

export function calcPensionCredit(p: PensionInput): PensionResult {
  const notes: string[] = [];
  const eligiblePension = Math.min(Math.max(0, p.pensionSaving), PENSION_CAP);
  const remain = TOTAL_CAP - eligiblePension;
  const eligibleIrp = Math.min(Math.max(0, p.irp), remain);
  const eligibleTotal = eligiblePension + eligibleIrp;
  const rate = p.lowIncome ? 0.165 : 0.132;
  const refund = Math.floor(eligibleTotal * rate);
  const excess = Math.max(0, p.pensionSaving + p.irp - eligibleTotal);

  if (p.pensionSaving > PENSION_CAP)
    notes.push("연금저축은 600만원까지만 세액공제됩니다. 600만원을 넘긴 납입은 IRP 한도(합산 900만원) 안에서만 추가 공제됩니다.");
  if (excess > 0)
    notes.push("합산 900만원을 넘긴 납입액은 올해 세액공제를 못 받습니다(다음 해로 이월 신청하거나 납입을 조절하세요).");
  notes.push("ISA 만기 자금을 연금계좌로 옮기면 전환액의 10%(최대 300만원) 추가 공제가 별도로 있습니다(이 도구엔 미반영).");
  notes.push("여기서 '환급'은 연말정산·종합소득세에서 그만큼 세금을 덜 낸다는 뜻입니다. 실제 환급액은 이미 낸 세금(기납부세액) 범위 안에서 정산됩니다.");
  return { eligiblePension, eligibleIrp, eligibleTotal, ratePct: rate * 100, refund, excess, notes };
}
