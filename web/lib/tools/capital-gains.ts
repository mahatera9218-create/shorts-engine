// 주택 양도소득세 대략 계산: 양도차익 → 1세대1주택 비과세(12억) → 고가주택 안분 → 장기보유특별공제
// → 기본공제 250만 → 세율(단기 70/60%, 기본 6~45%, 다주택 중과 토글). 규칙 2026 기준(소득세법).
// 중과·거주요건·특례는 수시로 바뀌어 '확인 필요'로 강하게 안내한다(대략값).
import { incomeTax, localIncomeTax } from "./tax.ts";

export interface GainInput {
  sale: number; // 양도가액(원)
  acquire: number; // 취득가액(원)
  expense: number; // 필요경비(취득세·중개보수·자본적지출, 원)
  holdYears: number; // 보유기간(년)
  liveYears: number; // 거주기간(년)
  oneHouse: boolean; // 1세대 1주택
  surcharge: "none" | "two" | "three"; // 조정지역 다주택 중과(+20/+30%p), 한시배제라 기본 none
}

export type GainResult =
  | { kind: "loss"; gain: number; notes: string[] }
  | { kind: "exempt"; gain: number; notes: string[] }
  | {
      kind: "tax";
      gain: number;
      taxableGain: number;
      ltdPct: number;
      ltdDeduction: number;
      taxBase: number;
      rateLabel: string;
      tax: number;
      local: number;
      total: number;
      notes: string[];
    };

const HIGH = 1_200_000_000; // 1세대1주택 비과세 한도(고가주택 기준)

export function calcGain(p: GainInput): GainResult {
  const notes: string[] = [];
  const gain = p.sale - p.acquire - p.expense;
  if (gain <= 0)
    return { kind: "loss", gain, notes: ["양도차익이 없어(또는 손실) 낼 양도세가 없습니다. 같은 해 다른 양도분과 통산할 수 있습니다."] };

  let taxableGain = gain;
  const oneHouseEligible = p.oneHouse && p.holdYears >= 2;
  if (oneHouseEligible) {
    if (p.sale <= HIGH)
      return { kind: "exempt", gain, notes: ["1세대 1주택(2년 이상 보유)이고 양도가액이 12억원 이하라 비과세입니다. 조정대상지역에서 취득했다면 2년 거주요건도 확인하세요."] };
    taxableGain = Math.floor((gain * (p.sale - HIGH)) / p.sale);
    notes.push("양도가액 12억원 초과 고가주택이라, 12억을 넘는 비율만큼만 과세합니다.");
  }

  let ltdPct = 0;
  if (oneHouseEligible && p.liveYears >= 2) {
    ltdPct = Math.min(0.4, 0.04 * Math.min(p.holdYears, 10)) + Math.min(0.4, 0.04 * Math.min(p.liveYears, 10));
  } else if (p.holdYears >= 3) {
    ltdPct = Math.min(0.3, 0.02 * Math.min(p.holdYears, 15));
  }
  const ltdDeduction = Math.floor(taxableGain * ltdPct);
  const taxBase = Math.max(0, taxableGain - ltdDeduction - 2_500_000);

  let tax = 0;
  let rateLabel = "";
  if (p.holdYears < 1) {
    tax = Math.floor(taxBase * 0.7);
    rateLabel = "1년 미만 단기 70%";
  } else if (p.holdYears < 2) {
    tax = Math.floor(taxBase * 0.6);
    rateLabel = "1~2년 단기 60%";
  } else {
    tax = incomeTax(taxBase);
    rateLabel = "기본세율 6~45%";
    if (p.surcharge === "two") {
      tax += Math.floor(taxBase * 0.2);
      rateLabel += " + 중과 20%p";
    } else if (p.surcharge === "three") {
      tax += Math.floor(taxBase * 0.3);
      rateLabel += " + 중과 30%p";
    }
    if (p.surcharge !== "none")
      notes.push("조정대상지역 다주택 중과는 현재 한시적으로 배제된 기간일 수 있습니다(시기마다 달라짐). 중과를 켜면 참고용 계산이니 적용 여부를 반드시 확인하세요.");
  }
  const local = localIncomeTax(tax);
  notes.push("취득가액·필요경비 인정 범위, 2년 거주요건, 일시적 2주택·상생임대 특례는 개별 확인이 필요합니다. 장기보유특별공제는 입력한 보유·거주기간으로 계산했습니다.");
  return { kind: "tax", gain, taxableGain, ltdPct, ltdDeduction, taxBase, rateLabel, tax, local, total: tax + local, notes };
}
