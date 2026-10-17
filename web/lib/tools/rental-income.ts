// 주택 월세 소득: 분리과세(14%) vs 종합과세 비교. 규칙: reports/직군도구-규칙/rental-income.md (원문 대조 전 → 경계는 '확인 필요'로 표시).
import { incomeTax, localIncomeTax } from "./tax.ts";

export interface RentalInput {
  rent: number; // 연 주택임대 월세 수입(본인 몫, 원)
  registered: boolean; // 임대사업자 등록 요건 충족(지자체+세무서)
  otherIncome: number; // 임대소득을 뺀 다른 종합소득금액
  deductions: number; // 종합과세 시 소득공제 합계
  expenseMode: "rate" | "actual";
  expenseRatePct: number; // 종합과세 경비율(%) — 홈택스 조회값을 직접 입력
  actualExpense: number; // 실제 경비(원)
  houseCount: number; // 소유 주택 수(부부 합산)
  highValueHouse: boolean; // 기준시가 12억 초과 주택 보유
  jointOwned: boolean;
}

export type RentalResult =
  | { kind: "exempt"; notes: string[] }
  | { kind: "comprehensive-only"; notes: string[] }
  | {
      kind: "compare";
      separate: { income: number; tax: number; local: number; total: number; expenseRate: number; basicDeduction: number };
      comprehensive: { income: number; tax: number; local: number; total: number };
      better: "separate" | "comprehensive" | "similar";
      diff: number; // 종합 − 분리 (양수면 분리가 유리)
      notes: string[];
    };

export const SEPARATE_LIMIT = 20_000_000;
const near = (v: number, limit: number, pct = 0.1): boolean => Math.abs(v - limit) <= limit * pct;

export function compareRental(p: RentalInput): RentalResult {
  const notes: string[] = [];
  if (p.jointOwned) notes.push("공동소유는 지분에 따라 수입을 나눠 각자 계산합니다. 이 도구는 본인 몫만 입력받습니다(주택 수는 부부 합산).");
  if (p.houseCount <= 1 && !p.highValueHouse) {
    return { kind: "exempt", notes: ["1주택자의 월세 수입은 원칙적으로 비과세입니다(기준시가 12억원 초과 고가주택·국외주택은 과세).", ...notes] };
  }
  if (p.rent > SEPARATE_LIMIT) {
    return { kind: "comprehensive-only", notes: ["연 주택임대 수입이 2,000만원을 넘으면 분리과세를 선택할 수 없고 종합과세로 신고합니다.", ...notes] };
  }
  if (near(p.rent, SEPARATE_LIMIT)) notes.push("수입이 2,000만원 경계 근처입니다. 2,000만원 판단에 포함되는 수입 범위(간주임대료 등)는 세무서에서 확인하세요.");
  if (near(p.otherIncome, SEPARATE_LIMIT)) notes.push("다른 종합소득금액이 2,000만원 경계 근처입니다. 기본공제(200만/400만원) 적용 여부가 달라질 수 있습니다.");

  const expenseRate = p.registered ? 0.6 : 0.5;
  const basicDeduction = p.otherIncome > SEPARATE_LIMIT ? 0 : p.registered ? 4_000_000 : 2_000_000;
  const sepIncome = Math.max(0, p.rent - p.rent * expenseRate - basicDeduction);
  const sepTax = Math.floor(sepIncome * 0.14);
  const sepLocal = localIncomeTax(sepTax);

  const compExpense = p.expenseMode === "actual" ? p.actualExpense : p.rent * (p.expenseRatePct / 100);
  const compIncome = Math.max(0, p.rent - compExpense);
  const withTax = incomeTax(p.otherIncome + compIncome - p.deductions);
  const withoutTax = incomeTax(p.otherIncome - p.deductions);
  const compTax = withTax - withoutTax;
  const compLocal = localIncomeTax(compTax);

  const sepTotal = sepTax + sepLocal;
  const compTotal = compTax + compLocal;
  const diff = compTotal - sepTotal;
  const better = Math.abs(diff) < 10_000 ? "similar" : diff > 0 ? "separate" : "comprehensive";
  notes.push("표준세액공제·건강보험료 영향·가산세·세액감면(소형주택 임대사업자 등)은 계산에 넣지 않았습니다.");
  return {
    kind: "compare",
    separate: { income: sepIncome, tax: sepTax, local: sepLocal, total: sepTotal, expenseRate, basicDeduction },
    comprehensive: { income: compIncome, tax: compTax, local: compLocal, total: compTotal },
    better,
    diff,
    notes,
  };
}
