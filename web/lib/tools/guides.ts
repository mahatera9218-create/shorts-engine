// 계산기 분류(허브) 안내 + 글↔계산기 내부 링크 지도.
// 수치는 전부 web/ 코드(lib/tools/*.ts)로 실제 계산한 값과 기존 글의 수치만 쓴다.
// 계산기가 모르는 것은 '확인 필요'로 적는다.

export { TOOL_GUIDES } from "./tool-guides";
export type { ToolGuide } from "./tool-guides";

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

export interface GroupGuide {
  lead: string[];
  steps: string[];
  example: { title: string; rows: Array<[string, string]>; note?: string };
  faq: Array<{ q: string; a: string }>;
  /** 이 분류와 이어지는 글 slug */
  guides: string[];
}

export const GROUP_GUIDES: Record<string, GroupGuide> = {
  property: {
    lead: [
      "부동산 세금은 '언제 사고, 언제 팔고, 얼마에 보유하느냐'에 따라 붙는 세금이 달라집니다. 살 때는 취득세, 보유하는 동안은 재산세(공시가격이 높으면 종합부동산세), 팔 때는 양도소득세, 세를 놓으면 임대소득세가 붙습니다. 거래할 때는 중개보수와 전월세 전환 계산도 함께 필요합니다.",
      "이 분류의 계산기는 그 지점들을 순서대로 확인하도록 묶었습니다. 매수 전에는 취득세와 자금 계획을, 매도 전에는 비과세 요건과 장기보유공제를, 보유 중에는 재산세·종부세를 확인하는 식입니다.",
    ],
    steps: [
      "살 때 — 취득세 계산기로 취득가·주택 수·조정지역·면적을 넣어 총액을 확인하고, 생애최초 감면 대상인지 함께 봅니다.",
      "보유할 때 — 재산세 계산기로 연간 부담을, 공시가격이 기본공제(1주택 12억·그 외 9억)를 넘으면 종합부동산세 계산기로 추가 부담을 확인합니다.",
      "팔 때 — 양도소득세 계산기로 1세대 1주택 비과세(12억)와 장기보유특별공제를 먼저 확인합니다.",
      "거래·임대 — 중개보수 계산기로 복비 상한을, 전월세 전환 계산기로 전세·월세 전환 금액을 확인합니다.",
    ],
    example: {
      title: "7억원 주택을 처음 살 때 (1주택, 비조정지역, 85㎡ 이하)",
      rows: [
        ["취득세 (1.667%)", won(11669000)],
        ["지방교육세", won(1166900)],
        ["농어촌특별세", "0원 (85㎡ 이하 비과세)"],
        ["합계", won(12835900)],
      ],
      note:
        "85㎡를 넘으면 농어촌특별세 0.2%(140만원)가 더해져 1,423만5,900원이 됩니다. 생애최초 감면 요건을 갖추면 200만원이 줄어듭니다.",
    },
    faq: [
      {
        q: "재산세와 종합부동산세를 같이 내나요?",
        a: "네, 별개 세금입니다. 재산세는 모든 주택에 매년 부과되고, 종합부동산세는 공시가격 합계가 기본공제(1세대 1주택 12억원, 그 외 9억원)를 넘을 때 추가로 부과됩니다.",
      },
      {
        q: "집을 팔 때 12억원 이하면 양도세가 없나요?",
        a: "1세대 1주택이고 2년 이상 보유(조정대상지역 취득분은 2년 거주)했다면 양도가액 12억원 이하까지 비과세입니다. 12억원을 넘으면 초과분 비율만큼만 과세되고, 장기보유특별공제가 최대 80%까지 적용됩니다.",
      },
      {
        q: "취득세와 재산세를 같은 해에 내나요?",
        a: "취득세는 집을 산 뒤 60일 안에 신고·납부하고(상속 취득은 6개월), 재산세는 6월 1일 기준 보유분에 대해 7월과 9월에 나옵니다. 그래서 해마다 취득세 한 번, 재산세 두 번의 고지 흐름이 생깁니다.",
      },
    ],
    guides: ["chwideukse-seyul-jutaek", "yangdose-1jutaek-bigwase", "jongbuse-gibon-gongje"],
  },
  gift: {
    lead: [
      "상속과 증여는 세율이 같고(10~50% 누진) 공제가 다릅니다. 상속은 일괄공제 5억원에 배우자공제가 더해져 보통 10억원까지 세금이 없지만, 살아 계실 때 미리 주는 증여는 성년 자녀 기준 10년에 5,000만원입니다. 공제 차이가 10배라 '언제, 얼마씩' 주는지가 전체 세금을 가릅니다.",
      "증여는 10년 합산이 핵심입니다. 같은 사람에게 10년 안에 나눠 받아도 공제 한도는 그대로이고, 넘는 금액에 세금이 붙습니다. 신고 기한(증여받은 달의 말일부터 3개월)을 넘기면 무신고 가산세 20%와 납부지연이자가 붙습니다.",
    ],
    steps: [
      "먼저 증여세 계산기로 이번 증여의 세액을 확인합니다. 10년 내 기존 증여가 있으면 합산해 다시 계산됩니다.",
      "부동산이라면 상속세 계산기와 번갈아 비교합니다. 물려줄 재산이 상속공제 범위 안이면 상속이 유리한 경우가 많습니다.",
      "신고할 때는 3개월 기한을 지켜 신고세액공제 3%를 받습니다. 기한을 넘기면 가산세가 붙습니다.",
    ],
    example: {
      title: "같은 1억원이라도 결과가 다릅니다",
      rows: [
        ["성년 자녀에게 1억원 증여", `증여세 ${won(4850000)} (공제 5,000만원, 신고세액공제 반영)`],
        ["상속재산 15억원 (배우자 있음)", `상속세 ${won(87300000)} (공제 10억원)`],
      ],
      note:
        "증여 공제는 10년 단위로 다시 채워지므로, 시기를 나누는 것만으로 세금이 달라집니다.",
    },
    faq: [
      {
        q: "배우자에게는 얼마까지 세금 없이 줄 수 있나요?",
        a: "배우자 증여재산공제는 10년 합산 6억원입니다. 다만 증여 후 10년 안에 이혼하거나 배우자가 사망하면 공제가 취소되어 세금이 다시 매겨질 수 있으니 주의해야 합니다.",
      },
      {
        q: "증여세는 누가 내나요?",
        a: "재산을 받은 사람(수증자)이 냅니다. 신고·납부 의무도 받는 사람에게 있고, 기한은 증여받은 날이 속하는 달의 말일부터 3개월입니다.",
      },
      {
        q: "생활비·교육비도 증여세 대상인가요?",
        a: "사회통념상 인정되는 범위의 생활비·교육비는 증여세 과세 대상이 아닙니다. 다만 목돈을 주거나 집·차 같은 재산을 사 주는 경우, 고가의 재산을 무상으로 넘기는 경우는 증여로 보아 신고 대상이 될 수 있습니다.",
      },
    ],
    guides: ["budongsan-jeungyeo-vs-sangsok", "jeungyeose-gongje-10nyeon", "jeungyeose-singo-bangbeop"],
  },
  income: {
    lead: [
      "소득에 붙는 세금은 '무엇으로 벌었는지'에 따라 신고 방식이 달라집니다. 월급 외 부수입이 있으면 5월 종합소득세 신고 대상이 될 수 있고, 사업자등록 여부·업종·매출 규모에 따라 부가세와 소득세 계산이 갈립니다.",
      "이 분류는 벌이의 형태별로 계산기를 묶었습니다. 블로그·유튜브 수익은 사업자등록 판단부터, 온라인 판매는 간이·일반과세 비교부터, 월세는 분리과세·종합과세 비교부터 시작하면 됩니다.",
    ],
    steps: [
      "부수입이 생겼다면 먼저 사업자등록 필요 여부(블로거·유튜버 계산기)를 확인합니다. 계속·반복성이 기준입니다.",
      "판매업이라면 간이과세·일반과세를 비교해 부가세 부담을 가늠합니다. 매입이 많으면 일반과세가 유리할 수 있습니다.",
      "소득이 확정되면 종합소득세 계산기로 과세표준과 한계세율을 확인하고 5월 신고를 준비합니다.",
      "월세를 받는다면 분리과세(14%)와 종합과세를 나란히 계산해 유리한 쪽을 고릅니다.",
    ],
    example: {
      title: "부수입이 있을 때 세금 흐름",
      rows: [
        ["온라인 판매 매출 1억·매입 6,000만원 (소매)", `간이과세 부가세 ${won(1200000)} (일반과세는 363만6,364원)`],
        ["월세 연 2,000만원, 다른 소득 없음", `분리 ${won(1232000)} vs 종합 ${won(660000)} → 종합과세 유리`],
        ["소득금액 5,000만원, 소득공제 1,000만원", `종합소득세 + 지방소득세 ${won(4664000)}`],
      ],
      note:
        "부가세와 소득세는 별개입니다. 부가세를 적게 내는 간이과세를 골라도 소득세는 소득금액 기준으로 따로 매겨집니다.",
    },
    faq: [
      {
        q: "3.3%를 떼고 받았는데 5월에 또 신고해야 하나요?",
        a: "네. 3.3% 원천징수는 미리 낸 세금이고, 다음 해 5월 종합소득세 신고에서 경비·공제를 반영해 정산합니다. 돌려받을 수도, 더 낼 수도 있습니다.",
      },
      {
        q: "간이과세자인데 세금계산서를 발급해야 하나요?",
        a: "직전 연도 공급대가 4,800만원 이상인 간이과세자는 세금계산서 발급 의무가 있습니다. 그 미만이면 영수증만 발급합니다.",
      },
      {
        q: "프리랜서 3.3%와 사업자등록은 무엇이 다른가요?",
        a: "3.3%는 원천징수 방식이고, 사업자등록은 사업자로서 신고·부가세 의무를 지는 별개 문제입니다. 사업자등록이 없어도 소득이 계속·반복되면 다음 해 5월 종합소득세 신고 대상이 됩니다.",
      },
    ],
    guides: ["jonghap-sodeukse-singo-5wol", "saeopja-deungnok-gijun", "seller-ganyi-ilban-gwase-chai", "imdae-sodeuk-sinmungo"],
  },
  insurance: {
    lead: [
      "건강보험과 연금은 '지금 내는 돈'과 '나중에 받는 돈'이 맞물려 있습니다. 직장인은 월급에서 4대보험료가 빠지고, 직장을 그만두면 지역가입자로 바뀌면서 보험료 구조가 달라집니다. 부모·배우자 밑에 피부양자로 올라가 있으면 소득·재산 기준을 넘는 순간 보험료가 새로 부과됩니다.",
      "노후 쪽은 세액공제가 핵심입니다. 연금저축·IRP에 넣은 돈은 연말정산에서 13.2~16.5%를 돌려받고, 퇴직금을 IRP로 받으면 퇴직소득세를 이연할 수 있습니다. 다만 한도를 넘겨 넣으면 그해 공제는 받지 못합니다.",
    ],
    steps: [
      "직장인이라면 4대보험료 계산기로 월급에서 빠지는 금액을 먼저 확인합니다(월 보수의 9% 안팎).",
      "부업·임대·연금 소득이 생겼다면 피부양자 판정으로 자격 유지 여부를 확인합니다. 탈락하면 보험료가 새로 나옵니다.",
      "연말정산 전에는 연금저축·IRP 세액공제 계산기로 한도(연금저축 600만·합산 900만원)를 채웠는지 확인합니다.",
      "퇴직을 앞뒀다면 퇴직소득세(일시금)와 실업급여를 함께 계산해 현금 흐름을 정리합니다.",
    ],
    example: {
      title: "직장인의 1년 (보험료와 환급)",
      rows: [
        ["월 보수 400만원", `4대보험 근로자 부담 월 ${won(376163)}`],
        ["연금저축 600만 + IRP 300만 납입", `세액공제 ${won(1485000)} (총급여 5,500만원 이하 기준)`],
        ["퇴직금 1억원, 근속 10년", `퇴직소득세 ${won(4262500)} (IRP 이연 시 유리)`],
      ],
      note:
        "세액공제 148만5,000원은 '덜 내는 세금'입니다. 이미 낸 세금이 그보다 적으면 실제 환급액은 줄어듭니다.",
    },
    faq: [
      {
        q: "연금저축과 IRP 중 뭘 먼저 채워야 하나요?",
        a: "연금저축 600만원을 먼저 채우고, 여유가 있으면 IRP로 300만원을 더 넣어 합산 900만원을 채우는 순서가 일반적입니다. 연금저축만으로는 600만원까지만 공제되기 때문입니다.",
      },
      {
        q: "직장을 그만두면 건강보험료가 얼마나 오르나요?",
        a: "지역가입자는 소득과 재산을 합쳐 보험료를 매기므로 직장가입자 때와 구조가 다릅니다. 이 사이트의 계산기는 지역가입자 보험료를 계산하지 않으니, 국민건강보험공단 모의계산으로 확인하세요.",
      },
      {
        q: "회사가 넣어 주는 퇴직연금도 세액공제되나요?",
        a: "회사가 납입하는 퇴직연금(DB·DC)은 세액공제 대상이 아닙니다. 본인이 IRP에 추가로 납입한 금액만 공제 대상이므로, 회사 납입분은 빼고 계산하세요.",
      },
    ],
    guides: ["yeongeum-irp-semuchul-gongje-2026", "isa-vs-yeongeum-jeochuk", "pibuyangja-jagyeok-yogeon", "jiyeok-geonbo-san-jeong"],
  },
};

// ---- 글 → 계산기·가이드 링크 지도 ----
// tools: 그 글에서 바로 이어서 계산해 볼 계산기.
// guides: 같은 주제의 다른 글(자동 '관련 글'과 별도로 주제 기준으로 묶은 것).
export const POST_LINKS: Record<string, { tools: string[]; guides: string[] }> = {
  "yeongeum-irp-semuchul-gongje-2026": {
    tools: ["pension-credit", "retirement-tax"],
    guides: ["isa-vs-yeongeum-jeochuk", "sodeukse-yulpyo-2026", "jonghap-sodeukse-singo-5wol"],
  },
  "isa-vs-yeongeum-jeochuk": {
    tools: ["pension-credit", "income-tax"],
    guides: ["yeongeum-irp-semuchul-gongje-2026", "jonghap-sodeukse-singo-5wol"],
  },
  "sodeukse-yulpyo-2026": {
    tools: ["income-tax", "pension-credit"],
    guides: ["jonghap-sodeukse-singo-5wol", "saeopja-deungnok-gijun"],
  },
  "jonghap-sodeukse-singo-5wol": {
    tools: ["income-tax", "rental-income"],
    guides: ["sodeukse-yulpyo-2026", "saeopja-deungnok-gijun", "pibuyangja-jagyeok-yogeon"],
  },
  "saeopja-deungnok-gijun": {
    tools: ["creator-business", "seller-vat"],
    guides: ["seller-ganyi-ilban-gwase-chai", "jonghap-sodeukse-singo-5wol"],
  },
  "seller-ganyi-ilban-gwase-chai": {
    tools: ["seller-vat", "creator-business"],
    guides: ["saeopja-deungnok-gijun", "jonghap-sodeukse-singo-5wol"],
  },
  "pibuyangja-jagyeok-yogeon": {
    tools: ["dependent-nhis", "four-insurance"],
    guides: ["jiyeok-geonbo-san-jeong", "imdae-sodeuk-sinmungo"],
  },
  "jiyeok-geonbo-san-jeong": {
    tools: ["four-insurance", "dependent-nhis", "unemployment"],
    guides: ["pibuyangja-jagyeok-yogeon", "jonghap-sodeukse-singo-5wol"],
  },
  "imdae-sodeuk-sinmungo": {
    tools: ["rental-income", "income-tax"],
    guides: ["pibuyangja-jagyeok-yogeon", "jonghap-sodeukse-singo-5wol"],
  },
  "chwideukse-seyul-jutaek": {
    tools: ["acquisition-tax", "brokerage"],
    guides: ["yangdose-1jutaek-bigwase", "jongbuse-gibon-gongje"],
  },
  "yangdose-1jutaek-bigwase": {
    tools: ["capital-gains", "brokerage"],
    guides: ["chwideukse-seyul-jutaek", "jongbuse-gibon-gongje", "budongsan-jeungyeo-vs-sangsok"],
  },
  "jongbuse-gibon-gongje": {
    tools: ["jongbuse", "property-tax"],
    guides: ["yangdose-1jutaek-bigwase", "chwideukse-seyul-jutaek"],
  },
  "budongsan-jeungyeo-vs-sangsok": {
    tools: ["gift-tax", "inheritance-tax"],
    guides: ["jeungyeose-gongje-10nyeon", "jeungyeose-singo-bangbeop"],
  },
  "jeungyeose-gongje-10nyeon": {
    tools: ["gift-tax", "inheritance-tax"],
    guides: ["jeungyeose-singo-bangbeop", "budongsan-jeungyeo-vs-sangsok"],
  },
  "jeungyeose-singo-bangbeop": {
    tools: ["gift-tax", "inheritance-tax"],
    guides: ["jeungyeose-gongje-10nyeon", "budongsan-jeungyeo-vs-sangsok"],
  },
};
