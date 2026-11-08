// 상속세 대략 계산: 상속재산 − 채무 → 일괄공제(5억)·배우자공제(최소 5억) → 상속·증여 공통세율 → 신고세액공제 3%.
// 규칙 2026 기준(상속세및증여세법). 배우자공제·사전증여 합산 등은 복잡해 '확인 필요'로 안내(대략값).
import { giftTaxGross } from "./gift-tax.ts";

export interface InheritInput {
  estate: number; // 상속재산가액(원)
  debts: number; // 채무·공과금·장례비(원)
  hasSpouse: boolean; // 배우자 생존
}

export const LUMP_SUM = 500_000_000; // 일괄공제 5억
export const SPOUSE_MIN = 500_000_000; // 배우자공제 최소 5억

export interface InheritResult {
  deduction: number;
  taxBase: number;
  gross: number;
  reportCredit: number;
  payable: number;
  notes: string[];
}

export function calcInherit(p: InheritInput): InheritResult {
  const net = Math.max(0, p.estate - p.debts);
  const deduction = LUMP_SUM + (p.hasSpouse ? SPOUSE_MIN : 0);
  const taxBase = Math.max(0, net - deduction);
  const gross = giftTaxGross(taxBase); // 상속·증여 공통 누진세율(10~50%)
  const reportCredit = Math.floor(gross * 0.03);
  const payable = Math.max(0, gross - reportCredit);
  const notes: string[] = [
    "일괄공제 5억원을 적용했습니다(기초공제+그 밖의 인적공제 대신 택일, 보통 일괄공제가 유리).",
  ];
  if (p.hasSpouse)
    notes.push("배우자공제는 최소 5억원으로 계산했습니다. 실제로는 배우자가 상속받은 금액·법정상속분에 따라 최대 30억원까지 커져 세금이 더 줄 수 있습니다(세무서 확인).");
  notes.push("금융재산 상속공제, 동거주택·가업상속 공제, 사전증여 합산(상속인 10년·그 외 5년)은 반영하지 않은 대략값입니다.");
  return { deduction, taxBase, gross, reportCredit, payable, notes };
}
