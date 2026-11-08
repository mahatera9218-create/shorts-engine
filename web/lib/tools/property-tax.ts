// 주택 재산세 대략 계산: 공시가격 × 공정시장가액비율 → 누진세율 + 도시지역분 + 지방교육세.
// 규칙 2026 기준(지방세법). 세부담 상한은 복잡해 반영하지 않는다(대략값, 고지서 확인).

export interface PropTaxInput {
  publicPrice: number; // 주택 공시가격(원)
  singleHome: boolean; // 1세대 1주택(공시 9억 이하 특례세율)
  fairRatioPct: number; // 공정시장가액비율(%) — 주택 보통 60, 1주택 특례는 43~45
  urbanArea: boolean; // 도시지역분(재산세 도시지역분 0.14%) 부과 지역
}

// 표준세율 [과세표준 상한, 세율, 누진공제(원)]
const STD: ReadonlyArray<readonly [number | null, number, number]> = [
  [60_000_000, 0.001, 0],
  [150_000_000, 0.0015, 30_000],
  [300_000_000, 0.0025, 180_000],
  [null, 0.004, 630_000],
];
// 1세대 1주택 특례세율(공시 9억 이하)
const SPECIAL: ReadonlyArray<readonly [number | null, number, number]> = [
  [60_000_000, 0.0005, 0],
  [150_000_000, 0.001, 30_000],
  [300_000_000, 0.002, 180_000],
  [null, 0.0035, 630_000],
];

function bracket(base: number, table: typeof STD): number {
  if (base <= 0) return 0;
  for (const [limit, rate, ded] of table) {
    if (limit === null || base <= limit) return Math.floor(base * rate - ded);
  }
  return 0;
}

export interface PropTaxResult {
  taxBase: number;
  propertyTax: number; // 재산세 본세
  urbanTax: number; // 도시지역분
  eduTax: number; // 지방교육세(본세의 20%)
  total: number;
  special: boolean; // 1주택 특례세율 적용 여부
  notes: string[];
}

export function calcPropertyTax(p: PropTaxInput): PropTaxResult {
  const ratio = Math.min(1, Math.max(0, p.fairRatioPct / 100));
  const taxBase = Math.floor(p.publicPrice * ratio);
  const special = p.singleHome && p.publicPrice <= 900_000_000;
  const propertyTax = bracket(taxBase, special ? SPECIAL : STD);
  const urbanTax = p.urbanArea ? Math.floor(taxBase * 0.0014) : 0; // 도시지역분 0.14%
  const eduTax = Math.floor(propertyTax * 0.2); // 지방교육세 = 재산세 본세의 20%
  const notes: string[] = [];
  if (special) notes.push("1세대 1주택(공시 9억 이하) 특례세율을 적용했습니다. 공시가격 9억 초과이거나 다주택이면 표준세율입니다.");
  else if (p.singleHome) notes.push("1세대 1주택이지만 공시가격 9억원을 초과해 표준세율을 적용했습니다.");
  notes.push("재산세는 7월·9월에 절반씩 나눠 부과됩니다(위 금액은 연간 합계). 공정시장가액비율은 해마다 고시로 바뀝니다.");
  notes.push("세부담 상한(전년 대비 인상 한도)과 지역자원시설세는 반영하지 않아 실제 고지액과 다를 수 있습니다.");
  return { taxBase, propertyTax, urbanTax, eduTax, total: propertyTax + urbanTax + eduTax, special, notes };
}
