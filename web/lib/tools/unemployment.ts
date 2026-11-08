// 실업급여(구직급여) 대략 계산: 1일 구직급여 = 평균임금의 60%(상·하한 적용) × 소정급여일수.
// 상·하한액·최저임금은 해마다 바뀌어 '확인 필요'로 안내(대략값). 고용보험법 기준.

export interface UnempInput {
  avgMonthlyWage: number; // 월 평균임금(원)
  age50plus: boolean; // 50세 이상 또는 장애인
  insuredYears: number; // 고용보험 가입기간(년)
}

export const DAILY_CAP = 66_000; // 1일 상한액(참고)
export const DAILY_FLOOR = 63_104; // 1일 하한액(최저임금 80%×8h, 참고·변동)

/** 소정급여일수(연령·가입기간별). */
export function benefitDays(age50plus: boolean, years: number): number {
  const table: [number, number][] = age50plus
    ? [[1, 120], [3, 180], [5, 210], [10, 240], [Infinity, 270]]
    : [[1, 120], [3, 150], [5, 180], [10, 210], [Infinity, 240]];
  for (const [lt, d] of table) if (years < lt) return d;
  return table[table.length - 1][1];
}

export interface UnempResult {
  dailyWage: number; // 1일 평균임금(근사)
  daily: number; // 1일 구직급여(상·하한 적용)
  days: number; // 소정급여일수
  total: number; // 예상 총액
  capped: "cap" | "floor" | "none";
  notes: string[];
}

export function calcUnemployment(p: UnempInput): UnempResult {
  const dailyWage = Math.round(p.avgMonthlyWage / 30); // 1일 평균임금(근사)
  const raw = Math.round(dailyWage * 0.6);
  let daily = raw;
  let capped: "cap" | "floor" | "none" = "none";
  if (raw > DAILY_CAP) { daily = DAILY_CAP; capped = "cap"; }
  else if (raw < DAILY_FLOOR) { daily = DAILY_FLOOR; capped = "floor"; }
  const days = benefitDays(p.age50plus, p.insuredYears);
  return {
    dailyWage,
    daily,
    days,
    total: daily * days,
    capped,
    notes: [
      "1일 구직급여는 평균임금의 60%이며, 1일 상한액(약 66,000원)과 하한액(최저임금 80%, 약 63,104원) 사이로 조정됩니다. 상·하한액은 해마다 바뀌니 확인하세요.",
      "1일 평균임금은 월 평균임금을 30으로 나눈 근삿값입니다(실제는 퇴직 전 3개월 임금÷일수).",
      "실업급여는 비자발적 이직 등 수급요건을 갖춰야 받습니다. 소정급여일수는 연령·가입기간 기준이며, 실제 지급은 고용센터 판단에 따릅니다.",
    ],
  };
}
