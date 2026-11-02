// 종합부동산세(주택) 대략 계산: 인별 공시가격 합계 → 기본공제 → 공정시장가액비율 → 누진세율.
// 1세대 1주택 단독명의는 고령자·장기보유 세액공제(합산 최대 80%)까지. 규칙 2026 기준(종합부동산세법).
// 재산세 중복분 공제·세부담 상한은 복잡해 반영하지 않는다(대략값, 신고 전 홈택스 확인).

export interface JongbuInput {
  publicPrice: number; // 본인이 보유한 주택 공시가격 합계(원)
  singleHome: boolean; // 1세대 1주택 단독명의 여부
  heavy: boolean; // 3주택 이상(과세표준 12억 초과 구간부터 중과세율)
  fairRatioPct: number; // 공정시장가액비율(%) — 해마다 고시, 기본 60
  ageCreditPct: number; // 고령자 세액공제율(0/20/30/40) — 단독명의 1주택만
  holdCreditPct: number; // 장기보유 세액공제율(0/20/40/50) — 단독명의 1주택만
}

// 과세표준 구간별 세율 [구간 상한(원), 세율]. 마지막은 상한 null.
const RATE_NORMAL: ReadonlyArray<readonly [number | null, number]> = [
  [300_000_000, 0.005],
  [600_000_000, 0.007],
  [1_200_000_000, 0.01],
  [2_500_000_000, 0.013],
  [5_000_000_000, 0.015],
  [9_400_000_000, 0.02],
  [null, 0.027],
];
const RATE_HEAVY: ReadonlyArray<readonly [number | null, number]> = [
  [300_000_000, 0.005],
  [600_000_000, 0.007],
  [1_200_000_000, 0.01],
  [2_500_000_000, 0.02],
  [5_000_000_000, 0.03],
  [9_400_000_000, 0.04],
  [null, 0.05],
];

/** 과세표준(원)에 구간별 세율을 '한계'로 적용해 합산(원 단위 절사). */
function bracketTax(base: number, table: ReadonlyArray<readonly [number | null, number]>): number {
  if (base <= 0) return 0;
  let tax = 0;
  let prev = 0;
  for (const [upper, rate] of table) {
    const cap = upper === null ? base : Math.min(base, upper);
    if (cap > prev) tax += (cap - prev) * rate;
    prev = cap;
    if (upper !== null && base <= upper) break;
  }
  return Math.floor(tax);
}

export interface JongbuResult {
  exempt: boolean; // 기본공제 이하라 과세 없음
  deduction: number; // 기본공제(12억/9억)
  taxBase: number; // 과세표준
  gross: number; // 세액공제 전 산출세액
  credit: number; // 1주택 세액공제액
  jongbuse: number; // 종합부동산세
  ruralTax: number; // 농어촌특별세(종부세의 20%)
  total: number; // 합계
  notes: string[];
}

export function calcJongbu(p: JongbuInput): JongbuResult {
  const notes: string[] = [];
  const deduction = p.singleHome ? 1_200_000_000 : 900_000_000;
  const ratio = Math.min(1, Math.max(0, p.fairRatioPct / 100));
  const over = p.publicPrice - deduction;
  if (over <= 0) {
    return {
      exempt: true, deduction, taxBase: 0, gross: 0, credit: 0, jongbuse: 0, ruralTax: 0, total: 0,
      notes: [
        `공시가격 합계가 기본공제(${p.singleHome ? "1세대 1주택 12억" : "9억"})원 이하라 종합부동산세 대상이 아닙니다.`,
        "재산세는 별도로 부과됩니다(이 도구는 종부세만 계산).",
      ],
    };
  }
  const taxBase = Math.floor(over * ratio);
  const gross = bracketTax(taxBase, p.heavy ? RATE_HEAVY : RATE_NORMAL);

  let credit = 0;
  if (p.singleHome) {
    const pct = Math.min(80, p.ageCreditPct + p.holdCreditPct); // 합산 한도 80%
    credit = Math.floor(gross * (pct / 100));
    if (pct > 0) notes.push(`1세대 1주택 세액공제 ${pct}%(고령자+장기보유, 최대 80%)를 적용했습니다.`);
  } else if (p.ageCreditPct > 0 || p.holdCreditPct > 0) {
    notes.push("고령자·장기보유 세액공제는 1세대 1주택 단독명의에만 적용돼, 이 경우엔 넣지 않았습니다.");
  }
  const jongbuse = Math.max(0, gross - credit);
  const ruralTax = Math.floor(jongbuse * 0.2); // 농어촌특별세 20%
  notes.push("이미 낸 재산세 중 종부세 과세분과 겹치는 금액(재산세 공제)과 세부담 상한은 반영하지 않아, 실제 고지액보다 다소 높게 나올 수 있습니다.");
  notes.push(`공정시장가액비율은 해마다 고시로 바뀝니다(입력값 ${p.fairRatioPct}% 적용). 홈택스·고지서로 확인하세요.`);
  return { exempt: false, deduction, taxBase, gross, credit, jongbuse, ruralTax, total: jongbuse + ruralTax, notes };
}
