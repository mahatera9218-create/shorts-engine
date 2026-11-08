// 주택 중개보수(복비) 상한 계산: 거래금액 구간별 상한요율·한도액. 규칙은 '상한'이며 협의 가능.
// 공인중개사법 시행규칙 별표(주택) 기준. 지자체 조례로 다를 수 있어 '확인'으로 안내.

export type DealType = "sale" | "lease";

export interface BrokerInput {
  amount: number; // 거래금액(원). 임대차는 보증금+월세×100(환산보증금).
  type: DealType;
}

// [구간 상한(원), 요율, 한도액(원)|null]
const SALE: ReadonlyArray<readonly [number | null, number, number | null]> = [
  [50_000_000, 0.006, 250_000],
  [200_000_000, 0.005, 800_000],
  [900_000_000, 0.004, null],
  [1_200_000_000, 0.005, null],
  [1_500_000_000, 0.006, null],
  [null, 0.007, null],
];
const LEASE: ReadonlyArray<readonly [number | null, number, number | null]> = [
  [50_000_000, 0.005, 200_000],
  [100_000_000, 0.004, 300_000],
  [600_000_000, 0.003, null],
  [1_200_000_000, 0.004, null],
  [1_500_000_000, 0.005, null],
  [null, 0.006, null],
];

export interface BrokerResult {
  ratePct: number; // 적용 상한요율(%)
  cap: number | null; // 한도액
  maxFee: number; // 상한 중개보수(부가세 별도)
  notes: string[];
}

export function calcBrokerage(p: BrokerInput): BrokerResult {
  const table = p.type === "sale" ? SALE : LEASE;
  for (const [limit, rate, cap] of table) {
    if (limit === null || p.amount < limit) {
      let fee = Math.floor(p.amount * rate);
      if (cap !== null) fee = Math.min(fee, cap);
      return {
        ratePct: rate * 100,
        cap,
        maxFee: fee,
        notes: [
          "위 금액은 법정 '상한'입니다. 실제 중개보수는 상한 안에서 중개사와 협의해 정합니다.",
          "부가가치세는 별도입니다(중개사무소가 일반과세자면 10%, 간이과세자면 더 낮게 붙을 수 있음).",
          p.type === "lease"
            ? "임대차 거래금액은 '보증금 + 월세×100'으로 환산합니다(환산액이 5천만원 미만이면 월세×70). 위에는 환산금액을 넣으세요."
            : "지자체 조례로 요율·한도가 다를 수 있으니 계약 전 확인하세요.",
        ],
      };
    }
  }
  return { ratePct: 0, cap: null, maxFee: 0, notes: [] };
}
