// 판정·비교 도구 목록. published=false 인 도구는 검색 제외(noindex) 상태로만 열어 둔다(규칙 검증·대표 확인 후 전환).
export interface ToolMeta {
  slug: string;
  title: string;
  short: string;
  audience: string;
  description: string;
  published: boolean;
  group: string; // 계층 분류 키
  related: string[]; // 관련 글 slug(존재하는 글만 표시)
  checked: string; // 규칙 확인일
}

export const TOOLS: ToolMeta[] = [
  {
    slug: "rental-income",
    group: "income",
    title: "주택 월세 소득, 분리과세 vs 종합과세 비교",
    short: "분리과세·종합과세 세금 비교",
    audience: "월세 받는 집주인",
    description: "연 월세 수입 2,000만원 이하 집주인이 분리과세(14%)와 종합과세 중 어느 쪽이 세금이 적은지 비교합니다.",
    published: true,
    related: ["imdae-sodeuk-sinmungo", "sodeukse-yulpyo-2026"],
    checked: "2026-10-18",
  },
  {
    slug: "seller-vat",
    group: "income",
    title: "온라인 셀러 간이과세 vs 일반과세 비교",
    short: "간이과세·일반과세 부가세 비교",
    audience: "스마트스토어·쿠팡 셀러",
    description: "연 매출과 매입으로 간이과세자와 일반과세자의 부가가치세를 비교하고, 납부면제 여부와 세금계산서 발급 의무를 확인합니다.",
    published: true,
    related: ["seller-ganyi-ilban-gwase-chai"],
    checked: "2026-10-18",
  },
  {
    slug: "dependent-nhis",
    group: "insurance",
    title: "건강보험 피부양자 자격 유지 판정 (부업 소득이 있다면)",
    short: "피부양자 자격 유지·탈락 판정",
    audience: "부업·부수입이 있는 직장인 가족",
    description: "소득과 재산 기준으로 건강보험 피부양자 자격이 유지될지, 탈락 가능성이 있는지 대략 판정합니다.",
    published: true,
    related: ["pibuyangja-jagyeok-yogeon", "jiyeok-geonbo-san-jeong"],
    checked: "2026-10-18",
  },
  {
    slug: "creator-business",
    group: "income",
    title: "블로거·유튜버 부수입, 사업자등록이 필요할까?",
    short: "사업자등록 필요 여부 판정",
    audience: "블로거·유튜버·인플루언서",
    description: "수익 종류와 규모, 지속성으로 사업자등록 필요 여부와 세금 처리 방향(사업소득·기타소득)을 안내합니다.",
    published: true,
    related: ["saeopja-deungnok-gijun"],
    checked: "2026-10-18",
  },
  {
    slug: "pension-credit",
    group: "insurance",
    title: "연금저축·IRP 세액공제, 얼마나 돌려받나 계산",
    short: "연금저축·IRP 세액공제 계산",
    audience: "연말정산·종합소득세 신고자",
    description: "연금저축·IRP 납입액과 소득 구간을 넣으면 올해 돌려받을(덜 낼) 세금을 계산합니다. 한도 600만/900만원, 공제율 16.5%·13.2%.",
    published: true,
    related: ["yeongeum-irp-semuchul-gongje-2026", "isa-vs-yeongeum-jeochuk"],
    checked: "2026-11-02",
  },
  {
    slug: "jongbuse",
    group: "property",
    title: "종합부동산세(주택) 얼마 나올까 계산",
    short: "종합부동산세 계산",
    audience: "공시가격 높은 주택 보유자",
    description: "보유 주택 공시가격 합계로 종합부동산세를 대략 계산합니다. 1세대 1주택 12억 공제·고령자·장기보유 세액공제 반영.",
    published: true,
    related: ["jongbuse-gibon-gongje"],
    checked: "2026-11-02",
  },
  {
    slug: "gift-tax",
    group: "gift",
    title: "증여세 얼마 나올까 계산 (관계별 공제·10년 합산)",
    short: "증여세 계산",
    audience: "재산을 주고받는 가족",
    description: "증여재산 가액과 관계를 넣으면 증여재산공제·10년 합산·신고세액공제까지 반영해 낼 증여세를 계산합니다.",
    published: true,
    related: ["jeungyeose-gongje-10nyeon", "jeungyeose-singo-bangbeop", "budongsan-jeungyeo-vs-sangsok"],
    checked: "2026-11-02",
  },
  {
    slug: "capital-gains",
    group: "property",
    title: "양도소득세 얼마 나올까 계산 (1주택 비과세·장기보유공제)",
    short: "양도소득세 계산",
    audience: "집을 파는 사람",
    description: "양도가·취득가·보유/거주기간으로 양도소득세를 대략 계산합니다. 1세대 1주택 비과세(12억)·고가주택 안분·장기보유특별공제 반영.",
    published: true,
    related: ["yangdose-1jutaek-bigwase"],
    checked: "2026-11-08",
  },
  {
    slug: "acquisition-tax",
    group: "property",
    title: "주택 취득세 얼마일까 계산 (주택수·조정지역·생애최초)",
    short: "취득세 계산",
    audience: "집을 사는 사람",
    description: "취득가와 주택 수·지역으로 취득세·지방교육세·농어촌특별세를 계산합니다. 다주택 중과·생애최초 감면 반영.",
    published: true,
    related: ["chwideukse-seyul-jutaek"],
    checked: "2026-11-08",
  },
  {
    slug: "income-tax",
    group: "income",
    title: "종합소득세 얼마일까 계산 (과세표준·누진세율)",
    short: "종합소득세 계산",
    audience: "프리랜서·사업자·N잡러",
    description: "종합소득금액과 공제로 과세표준·산출세액·지방소득세를 계산하고 한계세율을 보여 줍니다.",
    published: true,
    related: ["jonghap-sodeukse-singo-5wol", "sodeukse-yulpyo-2026"],
    checked: "2026-11-08",
  },
  {
    slug: "inheritance-tax",
    group: "gift",
    title: "상속세 얼마 나올까 계산 (일괄공제·배우자공제)",
    short: "상속세 계산",
    audience: "상속을 받는 가족",
    description: "상속재산과 배우자 유무로 상속세를 대략 계산합니다. 일괄공제 5억·배우자공제·신고세액공제 반영.",
    published: true,
    related: ["budongsan-jeungyeo-vs-sangsok", "jeungyeose-gongje-10nyeon"],
    checked: "2026-11-08",
  },
  {
    slug: "property-tax",
    group: "property",
    title: "주택 재산세 얼마일까 계산 (공시가격·1주택 특례)",
    short: "재산세 계산",
    audience: "주택 보유자",
    description: "공시가격으로 주택 재산세를 대략 계산합니다. 1세대 1주택 특례세율·도시지역분·지방교육세 반영.",
    published: true,
    related: ["jongbuse-gibon-gongje"],
    checked: "2026-11-08",
  },
  {
    slug: "brokerage",
    group: "property",
    title: "부동산 중개보수(복비) 계산 (매매·전월세 상한)",
    short: "중개보수(복비) 계산",
    audience: "집을 사고팔거나 임대차하는 사람",
    description: "거래금액으로 매매·임대차 중개보수(복비)의 법정 상한을 계산합니다. 구간별 요율·한도 반영.",
    published: true,
    related: [],
    checked: "2026-11-08",
  },
  {
    slug: "four-insurance",
    group: "insurance",
    title: "4대보험료 계산 (근로자 부담, 월급 기준)",
    short: "4대보험료 계산",
    audience: "직장인·사업주",
    description: "월급으로 국민연금·건강보험·장기요양·고용보험 근로자 부담액을 계산합니다.",
    published: true,
    related: ["jiyeok-geonbo-san-jeong", "pibuyangja-jagyeok-yogeon"],
    checked: "2026-11-08",
  },
];


/** 계산기 계층 분류(홈·허브·breadcrumb 공용). */
export const TOOL_GROUPS: { key: string; name: string; desc: string }[] = [
  { key: "property", name: "부동산 세금", desc: "집을 사고팔고 보유할 때" },
  { key: "gift", name: "상속·증여", desc: "재산을 물려주고 받을 때" },
  { key: "income", name: "소득·사업 세금", desc: "벌이에 대한 세금" },
  { key: "insurance", name: "건강보험·연금", desc: "4대보험과 노후 준비" },
];

export const groupOf = (slug: string): { key: string; name: string; desc: string } | undefined => {
  const t = TOOLS.find((x) => x.slug === slug);
  return t ? TOOL_GROUPS.find((g) => g.key === t.group) : undefined;
};

export const toolsInGroup = (key: string): ToolMeta[] => TOOLS.filter((t) => t.published && t.group === key);

/** 이 글(slug)과 짝을 이루는 도구들. */
export const toolsForPost = (slug: string): ToolMeta[] => TOOLS.filter((t) => t.published && t.related.includes(slug));

export const getTool = (slug: string): ToolMeta | undefined => TOOLS.find((t) => t.slug === slug);
