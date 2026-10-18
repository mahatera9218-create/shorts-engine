// 블로거·유튜버 부수입: 사업자등록 필요 여부 안내 분류. 규칙: reports/직군도구-규칙/creator-business.md.
// 주의: 계속성 점수의 임계값(3개월·3건 등)은 법 기준이 아니라 이 도구의 휴리스틱이다. 결과는 항상 '참고용'.
export type IncomeType = "adsense" | "adpost" | "sponsor" | "inkind" | "affiliate" | "selling" | "donation" | "oneoff";

export interface CreatorInput {
  types: IncomeType[];
  monthsActive: number; // 올해 수익이 발생한 개월 수
  itemsCount: number; // 올해 수익 건수(계약·정산 횟수 등)
  ongoing: boolean; // 앞으로도 계속할 계획
  hasStaffOrOffice: boolean;
  prevYearIncome: number; // 작년 총수입(원)
  withholding33: boolean; // 3.3% 원천징수를 당했음
  employed: boolean; // 직장 근로자
  alreadyRegistered: boolean;
}

export type CreatorVerdict = "advised" | "unlikely" | "check";
export interface CreatorResult {
  verdict: CreatorVerdict;
  continuity: number;
  businessType: "exempt" | "taxable" | null; // 면세(940306) / 과세(921505)
  flags: string[];
  notes: string[];
}

export function judgeCreator(p: CreatorInput): CreatorResult {
  const t = new Set(p.types);
  const flags: string[] = [];
  const notes: string[] = [];

  if (t.has("adpost") || t.has("affiliate") || (t.has("inkind") && t.size === 1)) {
    flags.push("네이버 애드포스트·제휴 수수료·현물 협찬은 원천징수·소득 구분 근거가 확인되지 않아 개별 확인이 필요합니다.");
  }

  // 계속성(도구 휴리스틱)
  let continuity = 0;
  if (p.monthsActive >= 3) continuity += 1;
  if (p.itemsCount >= 3) continuity += 1;
  if (p.ongoing) continuity += 1;
  if (t.has("adsense") || t.has("adpost")) continuity += 2;
  const onlyOneOff = t.size === 1 && t.has("oneoff");
  if (onlyOneOff && !p.ongoing) continuity = 0;

  let verdict: CreatorVerdict;
  let businessType: CreatorResult["businessType"] = null;
  if (continuity >= 3) {
    verdict = "advised";
    businessType = p.hasStaffOrOffice ? "taxable" : "exempt";
    if (t.has("selling")) notes.push("블로그·유튜브로 물건을 팔거나 중개하면 일반·간이 과세사업자 등록과 업종 확인이 필요합니다.");
  } else if (continuity >= 1) {
    verdict = "check";
  } else {
    verdict = onlyOneOff ? "unlikely" : "check";
  }
  if (flags.length > 0 && verdict !== "advised") verdict = "check";

  if (verdict === "advised") {
    notes.push("사업 개시일부터 20일 이내에 등록해야 하며, 수익이 생기기 전에도 등록할 수 있습니다. 미등록 가산세는 공급가액의 1%입니다.");
    if (businessType === "exempt") notes.push("직원·사업장 없이 1인 창작자로 활동하면 면세사업자(업종코드 940306)로 등록하는 경우가 일반적이며, 부가세 신고 의무는 없고 다음 해 2월 10일까지 사업장현황신고를 합니다. 5월 종합소득세 신고는 별도입니다.");
    if (businessType === "taxable") notes.push("직원·사업장이 있으면 과세사업자(업종코드 921505)로 등록합니다. 구글 등 해외 외화 수입은 영세율, 국내 매출은 10%입니다.");
    if (p.alreadyRegistered) notes.push("이미 등록하셨다면 위 신고 일정만 확인하세요.");
  }
  if (t.has("adsense")) notes.push("애드센스는 미국 원천징수세액이 종합소득세 신고 때 외국납부세액공제 대상이 될 수 있습니다. 수입금액은 애드센스 계정에서 확인하세요.");
  if (p.withholding33) notes.push("3.3%를 떼였어도 5월 종합소득세 신고 대상입니다(무신고 가산세 20%).");
  if (verdict === "unlikely") {
    notes.push("일시적 인적용역 대가는 기타소득일 수 있습니다. 필요경비 60%가 적용되는 항목과 소득금액 300만원 이하 분리과세 선택 여부는 세무서에서 확인하세요.");
  }
  if (p.prevYearIncome > 0 && p.prevYearIncome < 24_000_000) notes.push("작년 수입이 2,400만원 미만이면 단순경비율 대상일 수 있습니다(업종 군에 따라 다름, 경비율은 홈택스 조회).");
  if (p.prevYearIncome >= 104_000_000 && businessType === "taxable") notes.push("작년 수입이 1억400만원 이상이면 일반과세입니다(간이과세 불가).");
  if (p.employed) notes.push("직장가입자의 보수 외 소득이 연 2,000만원을 넘으면 건강보험 소득월액보험료가 붙을 수 있습니다.");
  if (t.has("sponsor") || t.has("inkind")) notes.push("협찬·체험단 글은 광고·협찬 표기가 필수입니다.");
  return { verdict, continuity, businessType, flags, notes };
}
