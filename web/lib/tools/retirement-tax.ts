// 퇴직소득세 대략 계산: 근속연수공제 → 환산급여 → 환산급여공제 → 기본세율 → 연분연승(÷12×근속).
// 규칙 2026 기준(소득세법 제48조·제55조). 임원 한도·중간정산 등은 반영하지 않는다(대략값).
import { incomeTax, localIncomeTax } from "./tax.ts";

export interface RetireInput {
  payout: number; // 퇴직금(퇴직소득, 원)
  years: number; // 근속연수(년, 1년 미만 올림)
}

/** 근속연수공제(원). */
export function serviceDeduction(years: number): number {
  const y = Math.max(1, years);
  if (y <= 5) return 1_000_000 * y;
  if (y <= 10) return 5_000_000 + 2_000_000 * (y - 5);
  if (y <= 20) return 15_000_000 + 2_500_000 * (y - 10);
  return 40_000_000 + 3_000_000 * (y - 20);
}

/** 환산급여공제(원). */
export function convertedDeduction(converted: number): number {
  const c = converted;
  if (c <= 8_000_000) return c;
  if (c <= 70_000_000) return 8_000_000 + (c - 8_000_000) * 0.6;
  if (c <= 100_000_000) return 45_200_000 + (c - 70_000_000) * 0.55;
  if (c <= 300_000_000) return 61_700_000 + (c - 100_000_000) * 0.45;
  return 151_700_000 + (c - 300_000_000) * 0.35;
}

export interface RetireResult {
  serviceDed: number;
  converted: number; // 환산급여
  convertedDed: number;
  taxBase: number; // 과세표준(환산)
  tax: number; // 퇴직소득세
  local: number; // 지방소득세
  total: number;
  effectivePct: number;
  notes: string[];
}

export function calcRetirement(p: RetireInput): RetireResult {
  const years = Math.max(1, Math.ceil(p.years));
  const serviceDed = serviceDeduction(years);
  const afterService = Math.max(0, p.payout - serviceDed);
  const converted = Math.floor((afterService / years) * 12); // 환산급여
  const convertedDed = Math.floor(convertedDeduction(converted));
  const taxBase = Math.max(0, converted - convertedDed);
  const convertedTax = incomeTax(taxBase); // 환산산출세액(기본세율)
  const tax = Math.floor((convertedTax / 12) * years); // 연분연승
  const local = localIncomeTax(tax);
  return {
    serviceDed,
    converted,
    convertedDed,
    taxBase,
    tax,
    local,
    total: tax + local,
    effectivePct: p.payout > 0 ? ((tax + local) / p.payout) * 100 : 0,
    notes: [
      "퇴직소득세는 오래 근무할수록(근속연수공제·연분연승) 세율이 크게 낮아집니다.",
      "근속연수는 1년 미만을 1년으로 올려 계산합니다. 임원 퇴직금 한도, 2012년 이전 근속분, 중간정산은 반영하지 않았습니다.",
      "퇴직소득은 다른 소득과 합산하지 않고 따로 과세(분류과세)합니다. 실제 세액은 원천징수영수증·홈택스로 확인하세요.",
    ],
  };
}
