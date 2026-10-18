// 건강보험 피부양자 자격(소득·재산 요건) 대략 판정. 규칙: reports/직군도구-규칙/dependent-nhis.md (원문 대조 전 → 경계는 '확인 필요'로 돌린다).
// 금액은 모두 원 단위. 한도 근처(±10%)와 규칙이 불확실한 소득 종류는 판정하지 않고 '확인 필요'.
export type Relation = "spouse" | "ascendant" | "descendant" | "sibling" | "other";
export type AgeGroup = "under30" | "30to64" | "65plus";

export interface DependentInput {
  relation: Relation;
  siblingAge: AgeGroup; // 형제자매일 때만 사용
  special: boolean; // 장애인 또는 국가유공·보훈보상 상이자
  interestDividend: number; // 이자+배당 소득금액
  salary: number; // 근로소득금액
  business: number; // 사업소득금액(3.3% 프리랜서 포함)
  other: number; // 기타소득금액(원고료·강연료 등)
  hasBusinessRegistration: boolean;
  hasHousingRent: boolean; // 주택임대소득
  hasUncertainIncome: boolean; // 연금·분리과세·비주택 임대 등 규칙이 불확실한 소득
  propertyBase: number; // 재산세 과세표준 합계
  spouseIncome: number | null; // 피부양자가 기혼일 때 배우자 소득 합계(없으면 null)
}

export type Verdict = "pass" | "fail" | "check";
export interface Judgement {
  verdict: Verdict;
  reasons: string[];
  notes: string[];
}

export const LIMITS = {
  income: 20_000_000, // R1
  incomeWhenHighProperty: 10_000_000, // R9
  business: 5_000_000, // R4
  property1: 540_000_000, // R8
  property2: 900_000_000, // R9/R10
  siblingProperty: 180_000_000, // R11
} as const;

const near = (v: number, limit: number, pct = 0.1): boolean => Math.abs(v - limit) <= limit * pct;

export function judge(p: DependentInput): Judgement {
  const reasons: string[] = [];
  const notes: string[] = [];
  const check: string[] = [];
  let fail = false;

  // 0. 부양 관계
  if (p.relation === "sibling") {
    const ok = p.siblingAge === "under30" || p.siblingAge === "65plus" || p.special;
    if (!ok) {
      fail = true;
      reasons.push("형제자매는 30세 미만·65세 이상·장애인·국가유공/보훈보상 상이자 중 하나여야 합니다.");
    }
  } else if (p.relation !== "spouse") {
    notes.push("부모·자녀 등은 동거 여부·혼인 상태 같은 부양요건이 따로 있습니다. 이 도구는 소득·재산 요건만 봅니다.");
  }

  // 1. 주택임대소득 / 사업소득
  if (p.hasHousingRent) {
    fail = true;
    reasons.push("주택임대소득이 있으면 사업자등록과 상관없이 피부양자에서 제외됩니다.");
  }
  let business = 0;
  if (p.business > 0) {
    if (p.hasBusinessRegistration && !p.special) {
      fail = true;
      reasons.push("사업자등록이 있으면서 사업소득이 있으면 원칙적으로 피부양자에서 제외됩니다.");
    } else if (p.business > LIMITS.business) {
      if (near(p.business, LIMITS.business)) {
        check.push("사업소득이 연 500만원 경계 근처입니다(수입금액 기준인지 소득금액 기준인지에 따라 달라질 수 있음).");
      } else {
        fail = true;
        reasons.push("사업자등록이 없어도 사업소득이 연 500만원을 넘으면 사업소득이 있는 것으로 봅니다.");
      }
      business = p.business;
    } else {
      if (near(p.business, LIMITS.business)) {
        check.push("사업소득이 연 500만원 경계 근처입니다(수입금액 기준인지 소득금액 기준인지에 따라 달라질 수 있음).");
      } else {
        notes.push("사업자등록이 없고 사업소득이 연 500만원 이하라 사업소득이 없는 것으로 봅니다(소득 합계에서 제외).");
      }
      business = 0;
    }
  }

  // 2. 소득 합계
  const sum = p.interestDividend + p.salary + p.other + (p.business > LIMITS.business ? business : 0);
  if (sum > LIMITS.income) {
    if (near(sum, LIMITS.income)) {
      check.push("소득 합계가 연 2,000만원 경계 근처입니다(소득 자료 연도·필요경비 차이로 달라질 수 있음).");
    } else {
      fail = true;
      reasons.push("소득 합계가 연 2,000만원을 넘습니다.");
    }
  } else if (near(sum, LIMITS.income)) {
    check.push("소득 합계가 연 2,000만원 경계 근처입니다(소득 자료 연도·필요경비 차이로 달라질 수 있음).");
  }
  if (p.spouseIncome !== null && p.spouseIncome > LIMITS.income) {
    if (near(p.spouseIncome, LIMITS.income)) check.push("배우자 소득이 연 2,000만원 경계 근처입니다.");
    else {
      fail = true;
      reasons.push("피부양자가 기혼이면 부부 모두 소득요건(연 2,000만원 이하)을 충족해야 합니다.");
    }
  }
  if (p.other > 0) check.push("원고료·강연료 같은 기타소득은 건강보험에서 필요경비 반영 방식이 확인되지 않았습니다.");
  if (p.hasUncertainIncome) check.push("연금·분리과세·비주택 임대소득은 소득 산정 방식이 달라 이 도구로 판정하기 어렵습니다.");

  // 3. 재산
  if (p.relation === "sibling") {
    if (p.propertyBase > LIMITS.siblingProperty) {
      if (near(p.propertyBase, LIMITS.siblingProperty, 0.05)) check.push("재산세 과세표준이 형제자매 기준(1.8억원) 경계 근처입니다.");
      else {
        fail = true;
        reasons.push("형제자매는 재산세 과세표준 합계가 1.8억원 이하여야 합니다.");
      }
    } else if (near(p.propertyBase, LIMITS.siblingProperty, 0.05)) {
      check.push("재산세 과세표준이 형제자매 기준(1.8억원) 경계 근처입니다.");
    }
  } else {
    if (p.propertyBase > LIMITS.property2) {
      if (near(p.propertyBase, LIMITS.property2, 0.05)) check.push("재산세 과세표준이 9억원 경계 근처입니다.");
      else {
        fail = true;
        reasons.push("재산세 과세표준 합계가 9억원을 넘으면 피부양자 인정이 어렵습니다.");
      }
    } else if (p.propertyBase > LIMITS.property1) {
      if (sum > LIMITS.incomeWhenHighProperty) {
        if (near(sum, LIMITS.incomeWhenHighProperty)) check.push("재산이 5.4억~9억원인 구간의 소득 기준(연 1,000만원) 경계 근처입니다.");
        else {
          fail = true;
          reasons.push("재산세 과세표준이 5.4억원을 넘으면(9억원 이하) 소득 합계가 연 1,000만원 이하여야 합니다.");
        }
      } else if (near(sum, LIMITS.incomeWhenHighProperty)) {
        check.push("재산이 5.4억~9억원인 구간의 소득 기준(연 1,000만원) 경계 근처입니다.");
      }
    }
    if (near(p.propertyBase, LIMITS.property1, 0.05)) check.push("재산세 과세표준이 5.4억원 경계 근처입니다.");
    if (near(p.propertyBase, LIMITS.property2, 0.05) && p.propertyBase <= LIMITS.property2) check.push("재산세 과세표준이 9억원 경계 근처입니다.");
  }

  if (fail) return { verdict: "fail", reasons, notes: [...notes, ...check] };
  if (check.length > 0) return { verdict: "check", reasons: check, notes };
  return {
    verdict: "pass",
    reasons: ["입력하신 값으로는 소득·재산 요건을 충족하는 것으로 보입니다."],
    notes: [...notes, "최종 결정은 국민건강보험공단이 소득·재산 자료로 확정합니다."],
  };
}
