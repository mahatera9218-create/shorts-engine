// 온라인 셀러 간이과세 vs 일반과세 부가세 비교. 규칙: reports/직군도구-규칙/seller-vat.md (원문 대조 전).
export type Industry = "retail" | "restaurant" | "service" | "excluded";

export interface SellerInput {
  isNew: boolean; // 올해 개업
  supply: number; // 올해 연 공급대가(부가세 포함 판매액)
  prevSupply: number; // 직전 연도 공급대가(기존 사업자)
  openMonths: number; // 신규: 개업월~12월 개월 수(1~12)
  purchase: number; // 세금계산서·카드 증빙이 있는 매입 공급대가(부가세 포함)
  industry: Industry;
}

export const SIMPLE_LIMIT = 104_000_000;
export const EXEMPT_LIMIT = 48_000_000;
export const VALUE_ADDED_RATE: Record<Exclude<Industry, "excluded">, number> = { retail: 0.15, restaurant: 0.15, service: 0.3 };

export interface SellerResult {
  eligibleSimple: boolean | "choose"; // choose = 신규 개업 시 선택
  reasonSimple: string;
  annualized: number; // 면제 판단용(신규는 12개월 환산)
  simpleTax: number | null; // 간이 납부세액(null=간이 불가)
  exempt: boolean; // 간이 납부면제
  generalTax: number; // 일반(음수=환급)
  better: "simple" | "general" | "similar" | null;
  mustIssueInvoice: boolean | null;
  notes: string[];
}

export function compareSeller(p: SellerInput): SellerResult {
  const notes: string[] = [];
  const annualized = p.isNew ? Math.round((p.supply / Math.max(1, p.openMonths)) * 12) : p.supply;
  const generalTax = Math.floor(p.supply / 1.1 * 0.1) - Math.floor(p.purchase / 1.1 * 0.1);

  let eligibleSimple: boolean | "choose";
  let reasonSimple: string;
  if (p.industry === "excluded") {
    eligibleSimple = false;
    reasonSimple = "도매업·제조업·상품중개업·부동산매매업 등은 간이과세가 배제됩니다(일부 예외 업종 있음).";
  } else if (p.isNew) {
    eligibleSimple = "choose";
    reasonSimple = "신규 사업자는 개업 때 간이과세·일반과세를 선택합니다(예상 연매출이 1억400만원 미만이면 간이 가능).";
  } else if (p.prevSupply < SIMPLE_LIMIT) {
    eligibleSimple = true;
    reasonSimple = "직전 연도 공급대가가 1억400만원 미만이라 간이과세자입니다.";
  } else {
    eligibleSimple = false;
    reasonSimple = "직전 연도 공급대가가 1억400만원 이상이라 일반과세자입니다.";
  }

  let simpleTax: number | null = null;
  let exempt = false;
  if (p.industry !== "excluded") {
    const base = Math.floor(p.supply * VALUE_ADDED_RATE[p.industry] * 0.1);
    const credit = Math.floor(p.purchase * 0.005);
    simpleTax = Math.max(0, base - credit);
    exempt = annualized < EXEMPT_LIMIT;
    if (exempt) simpleTax = 0;
  }

  let better: SellerResult["better"] = null;
  if (simpleTax !== null) {
    const gen = Math.max(generalTax, 0 - Infinity); // 환급 포함 그대로 비교
    const d = gen - simpleTax;
    better = Math.abs(d) < 10_000 ? "similar" : d > 0 ? "simple" : "general";
  }

  const mustIssueInvoice = p.isNew ? null : eligibleSimple === true ? p.prevSupply >= EXEMPT_LIMIT : true;
  if (!p.isNew && eligibleSimple === true && p.supply >= SIMPLE_LIMIT) notes.push("올해 공급대가가 1억400만원 이상이면 다음 해 7월 1일부터 일반과세자로 전환됩니다.");
  if (generalTax < 0) notes.push("일반과세자는 매입이 많아 환급이 나올 수 있습니다(간이과세자는 환급 없음).");
  if (p.isNew) notes.push("신규 사업자는 개업일부터 연말까지의 공급대가를 12개월로 환산해 납부면제 여부를 판단합니다(1개월 미만 끝수는 1개월).");
  notes.push("신용카드 매출 발행세액공제, 부가세 신고 방식·가산세, 종합소득세는 계산에 넣지 않았습니다.");
  return { eligibleSimple, reasonSimple, annualized, simpleTax, exempt, generalTax, better, mustIssueInvoice, notes };
}
