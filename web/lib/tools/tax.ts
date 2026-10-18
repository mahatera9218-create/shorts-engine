// 종합소득세 계산 공통 모듈(순수 함수, 테스트 가능). 세율표는 국세청 종합소득세 세율(2026년 귀속까지 같은 구간) — config/tax.yaml과 같은 값.
export const BRACKETS: ReadonlyArray<readonly [number | null, number, number]> = [
  [14_000_000, 0.06, 0],
  [50_000_000, 0.15, 1_260_000],
  [88_000_000, 0.24, 5_760_000],
  [150_000_000, 0.35, 15_440_000],
  [300_000_000, 0.38, 19_940_000],
  [500_000_000, 0.40, 25_940_000],
  [1_000_000_000, 0.42, 35_940_000],
  [null, 0.45, 65_940_000],
];

/** 과세표준(원) → 산출세액(원, 원 단위 절사). 과세표준이 0 이하이면 0. */
export function incomeTax(taxBase: number): number {
  if (taxBase <= 0) return 0;
  for (const [limit, rate, deduction] of BRACKETS) {
    if (limit === null || taxBase <= limit) return Math.floor(taxBase * rate - deduction);
  }
  return 0;
}

/** 지방소득세 = 산출세액의 10%(원 단위 절사). */
export function localIncomeTax(tax: number): number {
  return Math.floor(tax * 0.1);
}

export const won = (n: number): string => `${Math.round(n).toLocaleString("ko-KR")}원`;
