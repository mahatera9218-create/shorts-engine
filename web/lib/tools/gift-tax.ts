// 증여세 계산: 증여재산공제 + 10년 합산(기납부세액 공제) + 신고세액공제 3%.
// 규칙 2026 기준(상속세및증여세법). 경계·특례는 '확인 필요'로 안내한다.

export type GiftRelation =
  | "spouse"
  | "lineal-adult"
  | "lineal-minor"
  | "descendant-to-ascendant"
  | "other-relative"
  | "non-relative";

export interface GiftInput {
  amount: number; // 이번 증여재산가액(원)
  relation: GiftRelation;
  priorGifts: number; // 같은 증여자에게 10년 내 이미 증여받은 과세가액 합계(원)
  reportOnTime: boolean; // 기한 내 신고(신고세액공제 3%)
}

// 증여재산공제(10년 누적 한도, 원)
export const GIFT_DEDUCTION: Record<GiftRelation, number> = {
  spouse: 600_000_000, // 배우자
  "lineal-adult": 50_000_000, // 직계존속 → 성년 직계비속
  "lineal-minor": 20_000_000, // 직계존속 → 미성년 직계비속
  "descendant-to-ascendant": 50_000_000, // 직계비속 → 직계존속
  "other-relative": 10_000_000, // 기타 친족(6촌 이내 혈족·4촌 이내 인척)
  "non-relative": 0, // 친족 아님
};

// 상속·증여세율(공통): [과세표준 상한(원), 세율, 누진공제(원)]
const G_BRACKETS: ReadonlyArray<readonly [number | null, number, number]> = [
  [100_000_000, 0.1, 0],
  [500_000_000, 0.2, 10_000_000],
  [1_000_000_000, 0.3, 60_000_000],
  [3_000_000_000, 0.4, 160_000_000],
  [null, 0.5, 460_000_000],
];

/** 과세표준(원) → 증여세 산출세액(원 단위 절사). */
export function giftTaxGross(base: number): number {
  if (base <= 0) return 0;
  for (const [limit, rate, ded] of G_BRACKETS) {
    if (limit === null || base <= limit) return Math.floor(base * rate - ded);
  }
  return 0;
}

export interface GiftResult {
  deduction: number; // 공제 한도
  taxBase: number; // 이번 증여 과세표준(합산 반영)
  grossThis: number; // 이번 증여 산출세액(합산 − 기존)
  reportCredit: number; // 신고세액공제(3%)
  payable: number; // 낼 세금
  effectiveRatePct: number; // 실효세율(이번 증여가액 대비)
  notes: string[];
}

export function calcGift(p: GiftInput): GiftResult {
  const L = GIFT_DEDUCTION[p.relation];
  const notes: string[] = [];
  // 10년 합산: (이번+기존) 과세가액에서 공제 L 적용 → 합산 산출세액. 기존분 산출세액을 빼 이번분만 남긴다.
  const cumBase = Math.max(0, p.amount + p.priorGifts - L);
  const priorBase = Math.max(0, p.priorGifts - L);
  const grossThis = Math.max(0, giftTaxGross(cumBase) - giftTaxGross(priorBase));
  const reportCredit = p.reportOnTime ? Math.floor(grossThis * 0.03) : 0;
  const payable = Math.max(0, grossThis - reportCredit);
  const effectiveRatePct = p.amount > 0 ? (payable / p.amount) * 100 : 0;

  if (p.relation === "lineal-minor")
    notes.push("미성년(만 19세 미만) 직계비속은 공제 한도가 2,000만원입니다.");
  if (p.priorGifts > 0)
    notes.push("같은 사람에게 10년 안에 받은 증여를 합산해 계산하고, 기존 증여에 매겨진 세액은 빼 이번 증여분만 보여줍니다(개략).");
  notes.push("증여재산은 시가(매매사례가·감정가·공시가격 순)로 평가하는 것이 원칙입니다. 부동산 저가양수·부담부증여·창업/가업 승계 특례는 반영하지 않았습니다.");
  notes.push("취득세(부동산 증여 시 별도)와 세대 생략 할증(직계비속을 건너뛴 증여 30~40% 가산)은 계산에 넣지 않았습니다.");
  return { deduction: L, taxBase: cumBase, grossThis, reportCredit, payable, effectiveRatePct, notes };
}
