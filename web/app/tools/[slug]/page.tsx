import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { TOOLS, getTool } from "@/lib/tools/registry";
import ToolShell from "@/components/tools/ToolShell";
import RentalIncomeTool from "@/components/tools/RentalIncomeTool";
import SellerVatTool from "@/components/tools/SellerVatTool";
import DependentNhisTool from "@/components/tools/DependentNhisTool";
import CreatorBusinessTool from "@/components/tools/CreatorBusinessTool";
import PensionCreditTool from "@/components/tools/PensionCreditTool";
import JongbuseTool from "@/components/tools/JongbuseTool";
import GiftTaxTool from "@/components/tools/GiftTaxTool";

export const dynamicParams = false;

export function generateStaticParams() {
  return TOOLS.map((t) => ({ slug: t.slug }));
}

export function generateMetadata({ params }: { params: { slug: string } }): Metadata {
  const t = getTool(params.slug);
  if (!t) return { title: "도구" };
  return {
    title: t.title,
    description: t.description,
    alternates: { canonical: `/tools/${t.slug}` },
    robots: t.published ? { index: true, follow: true } : { index: false, follow: false },
  };
}

const NTS_RATE = "https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=7667&mi=2227";
const NHIS = "https://www.nhis.or.kr/nhis/policy/wbhada07400m01.do";

const CONTENT: Record<string, { basis: { rule: string; value: string; source: string; url?: string }[]; limits: string[]; Tool: () => JSX.Element }> = {
  "rental-income": {
    Tool: RentalIncomeTool,
    basis: [
      { rule: "분리과세 선택 요건", value: "주택임대 연 수입 2,000만원 이하(초과 시 종합과세)", source: "소득세법 제64조의2·시행령 제122조의2" },
      { rule: "분리과세 세율", value: "14% (필요경비율 등록 60%/미등록 50%, 기본공제 등록 400만/미등록 200만원 — 임대 외 종합소득금액 2,000만원 이하일 때)", source: "국세청 주택임대소득 안내" },
      { rule: "지방소득세", value: "소득세의 10%", source: "지방세법" },
      { rule: "종합과세 세율", value: "6~45% 누진 (과세표준 구간별 누진공제)", source: "국세청 종합소득세 세율", url: NTS_RATE },
      { rule: "1주택 월세", value: "비과세(기준시가 12억원 초과·국외주택은 과세)", source: "소득세법 제12조" },
    ],
    limits: [
      "종합과세 경비율은 해마다 고시가 달라 직접 입력받습니다(홈택스 조회).",
      "보증금 간주임대료, 소형주택 임대사업자 세액감면, 건강보험료 영향, 표준세액공제, 가산세는 계산하지 않습니다.",
      "2,000만원 판단에 포함되는 수입 범위, 공동소유·부부 합산의 세부 규칙은 세무서 확인이 필요합니다.",
    ],
  },
  "seller-vat": {
    Tool: SellerVatTool,
    basis: [
      { rule: "간이과세 기준", value: "직전 연도 공급대가 1억400만원 미만 (부동산임대업 등은 4,800만원)", source: "부가가치세법 시행령 제109조" },
      { rule: "납부면제", value: "해당 과세기간 공급대가 4,800만원 미만(신고는 필요)", source: "부가가치세법 제69조" },
      { rule: "업종별 부가가치율", value: "소매업·음식점업 15%, 그 밖의 서비스업 30%", source: "부가가치세법 시행령 제111조" },
      { rule: "간이과세 납부세액", value: "공급대가×부가가치율×10% − 매입 공급대가×0.5% (환급 없음)", source: "부가가치세법 제63조" },
      { rule: "일반과세 납부세액", value: "매출세액 − 매입세액 (환급 가능)", source: "부가가치세법 제37조" },
      { rule: "신규 사업자", value: "개업일~연말 공급대가를 12개월로 환산", source: "국세청 안내" },
    ],
    limits: [
      "간이과세 배제 지역·규모·전문직 고시와 2개 이상 사업장 합산 기준은 확인하지 못해 계산하지 않습니다.",
      "신용카드 매출 발행세액공제(2026년 말까지), 신고·납부 일정, 가산세, 종합소득세는 다루지 않습니다.",
      "해외 판매·영세율 매출, 업종 전환·휴폐업은 범위 밖입니다.",
    ],
  },
  "dependent-nhis": {
    Tool: DependentNhisTool,
    basis: [
      { rule: "소득 요건", value: "연 소득 합계 2,000만원 이하(기혼이면 부부 모두)", source: "건강보험법 시행규칙 별표 1의2(공단 안내)", url: NHIS },
      { rule: "사업소득", value: "원칙적으로 없어야 함. 사업자등록이 없고 연 500만원 이하이면 없는 것으로 봄", source: "건강보험법 시행규칙(공단 안내)", url: NHIS },
      { rule: "주택임대소득", value: "있으면 제외", source: "건강보험법 시행규칙(공단 안내)", url: NHIS },
      { rule: "재산 요건", value: "재산세 과세표준 합계 5.4억 이하 / 5.4억~9억은 소득 1,000만원 이하일 때 / 9억 초과 탈락", source: "공단 안내(9억 초과는 구판 비고 기준)", url: NHIS },
      { rule: "형제자매", value: "30세 미만·65세 이상·장애인·상이자 중 하나, 재산 과세표준 1.8억 이하", source: "공단 피부양자 취득안내", url: "https://www.nhis.or.kr/nhis/policy/wbhada07300m01.do" },
    ],
    limits: [
      "부모·자녀 등의 동거·혼인 같은 부양요건 세부, 연금소득 산입 비율, 분리과세 소득의 합산 여부는 확인되지 않아 '확인 필요'로 안내합니다.",
      "소득 자료 기준 연도(1~10월/11~12월)와 11월 정기 심사 시점에 따라 같은 값도 결과가 달라질 수 있습니다. 한도 ±10% 근처는 판정하지 않습니다.",
      "탈락 후 지역가입자 보험료는 계산하지 않습니다(공단 모의계산 이용).",
    ],
  },
  "creator-business": {
    Tool: CreatorBusinessTool,
    basis: [
      { rule: "사업자등록 대상", value: "영리 목적으로 계속적·반복적으로 하는 활동(수입금액 하한 기준은 확인되지 않음)", source: "소득세법 제19조·부가가치세법(국세청 안내)" },
      { rule: "1인 창작자 업종", value: "인적·물적 시설 없으면 면세(940306), 직원·사업장 있으면 과세(921505)", source: "국세청 1인 미디어 창작자 안내" },
      { rule: "등록 시기·가산세", value: "개시일부터 20일 이내(개시 전 가능), 미등록 가산세 공급가액의 1%", source: "부가가치세법" },
      { rule: "기타소득", value: "일시적 인적용역 대가 — 필요경비 60%(항목별), 소득금액 300만원 이하·원천징수 시 분리과세 선택", source: "소득세법 제21조·시행령 제87조" },
      { rule: "3.3% 원천징수", value: "떼였어도 5월 종합소득세 신고 대상", source: "국세청 안내" },
    ],
    limits: [
      "계속성 점수(3개월·3건 등)는 법정 기준이 아니라 이 도구의 참고용 기준입니다.",
      "네이버 애드포스트·제휴 수수료·현물 협찬의 원천징수와 소득 구분은 확인되지 않아 '확인 필요'로 안내합니다.",
      "경비율 수치, 건강보험료 계산, 2026년 귀속 변경 사항은 다루지 않습니다.",
    ],
  },
  "pension-credit": {
    Tool: PensionCreditTool,
    basis: [
      { rule: "연금저축 공제 한도", value: "연 600만원", source: "소득세법 제59조의3" },
      { rule: "연금저축+IRP 합산 한도", value: "연 900만원", source: "소득세법 제59조의3" },
      { rule: "공제율", value: "총급여 5,500만원(종합소득 4,500만원) 이하 16.5%, 초과 13.2% (지방소득세 포함)", source: "국세청 연말정산 안내", url: NTS_RATE },
      { rule: "ISA 전환 추가공제", value: "전환액의 10%, 최대 300만원(별도)", source: "조세특례제한법(이 도구 미반영)" },
    ],
    limits: [
      "연금 수령 때 내는 연금소득세(3.3~5.5%)와 사적연금 연 1,500만원 초과 시 과세 방식은 다루지 않습니다.",
      "실제 환급은 이미 낸 세금(기납부세액) 범위 안에서 정산됩니다. 결정세액이 0이면 공제액을 다 돌려받지 못할 수 있습니다.",
      "ISA 만기 전환 추가공제, 퇴직연금(DB/DC) 회사 납입분은 계산하지 않습니다.",
    ],
  },
  "jongbuse": {
    Tool: JongbuseTool,
    basis: [
      { rule: "기본공제", value: "1세대 1주택 단독명의 12억원 / 그 외 9억원 (인별 공시가격 합계 기준)", source: "종합부동산세법 제8조" },
      { rule: "세율(2주택 이하)", value: "0.5%~2.7% 누진 (과세표준 구간별)", source: "종합부동산세법 제9조" },
      { rule: "세율(3주택 이상)", value: "0.5%~5.0% 누진 (12억 초과 구간부터 중과)", source: "종합부동산세법 제9조" },
      { rule: "1주택 세액공제", value: "고령자 20~40% + 장기보유 20~50%, 합산 최대 80%", source: "종합부동산세법 제9조의2" },
      { rule: "농어촌특별세", value: "종합부동산세의 20%", source: "농어촌특별세법" },
    ],
    limits: [
      "공정시장가액비율은 해마다 고시로 바뀌어 직접 입력받습니다(최근 주택 60% 안팎).",
      "이미 낸 재산세 중 종부세와 겹치는 금액(재산세 공제)과 세부담 상한을 빼지 않아, 실제 고지액보다 높게 나올 수 있습니다.",
      "합산배제(임대·사원용 주택 등), 부부 공동명의 1주택 특례, 법인 과세는 다루지 않습니다.",
    ],
  },
  "gift-tax": {
    Tool: GiftTaxTool,
    basis: [
      { rule: "증여재산공제(10년)", value: "배우자 6억 / 성년 직계비속 5천만(미성년 2천만) / 직계존속 5천만 / 기타친족 1천만원", source: "상속세및증여세법 제53조" },
      { rule: "세율", value: "10%~50% 누진 (1억↓10%, 5억↓20%, 10억↓30%, 30억↓40%, 30억 초과 50%)", source: "상속세및증여세법 제26조" },
      { rule: "신고세액공제", value: "기한 내 신고 시 산출세액의 3%", source: "상속세및증여세법 제69조" },
      { rule: "10년 합산", value: "같은 사람에게 10년 내 받은 증여는 합산 과세(기납부세액 공제)", source: "상속세및증여세법 제47조·제58조" },
    ],
    limits: [
      "증여재산 가액 평가(시가·보충적 평가), 부담부증여, 저가·고가 양수, 창업·가업 승계 특례는 반영하지 않습니다.",
      "부동산 증여 시 취득세(별도)와 세대 생략 증여 할증(30~40%)은 계산에 넣지 않습니다.",
      "10년 합산·기납부세액 공제는 개략 계산이라, 실제 신고 세액과 다를 수 있습니다(홈택스·세무서 확인).",
    ],
  },
};

export default function ToolPage({ params }: { params: { slug: string } }) {
  const tool = getTool(params.slug);
  const c = tool ? CONTENT[tool.slug] : undefined;
  if (!tool || !c) notFound();
  const { Tool, basis, limits } = c;
  return (
    <ToolShell tool={tool} basis={basis} limits={limits}>
      <Tool />
    </ToolShell>
  );
}
