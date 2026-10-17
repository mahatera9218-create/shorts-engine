// 판정·비교 도구 목록. published=false 인 도구는 검색 제외(noindex) 상태로만 열어 둔다(규칙 검증·대표 확인 후 전환).
export interface ToolMeta {
  slug: string;
  title: string;
  short: string;
  audience: string;
  description: string;
  published: boolean;
  related: string[]; // 관련 글 slug(존재하는 글만 표시)
  checked: string; // 규칙 확인일
}

export const TOOLS: ToolMeta[] = [
  {
    slug: "rental-income",
    title: "주택 월세 소득, 분리과세 vs 종합과세 비교",
    short: "분리과세·종합과세 세금 비교",
    audience: "월세 받는 집주인",
    description: "연 월세 수입 2,000만원 이하 집주인이 분리과세(14%)와 종합과세 중 어느 쪽이 세금이 적은지 비교합니다.",
    published: false,
    related: ["imdae-sodeuk-sinmungo", "sodeukse-yulpyo-2026"],
    checked: "2026-10-18",
  },
  {
    slug: "seller-vat",
    title: "온라인 셀러 간이과세 vs 일반과세 비교",
    short: "간이과세·일반과세 부가세 비교",
    audience: "스마트스토어·쿠팡 셀러",
    description: "연 매출과 매입으로 간이과세자와 일반과세자의 부가가치세를 비교하고, 납부면제 여부와 세금계산서 발급 의무를 확인합니다.",
    published: false,
    related: [],
    checked: "2026-10-18",
  },
  {
    slug: "dependent-nhis",
    title: "건강보험 피부양자 자격 유지 판정 (부업 소득이 있다면)",
    short: "피부양자 자격 유지·탈락 판정",
    audience: "부업·부수입이 있는 직장인 가족",
    description: "소득과 재산 기준으로 건강보험 피부양자 자격이 유지될지, 탈락 가능성이 있는지 대략 판정합니다.",
    published: false,
    related: [],
    checked: "2026-10-18",
  },
  {
    slug: "creator-business",
    title: "블로거·유튜버 부수입, 사업자등록이 필요할까?",
    short: "사업자등록 필요 여부 판정",
    audience: "블로거·유튜버·인플루언서",
    description: "수익 종류와 규모, 지속성으로 사업자등록 필요 여부와 세금 처리 방향(사업소득·기타소득)을 안내합니다.",
    published: false,
    related: [],
    checked: "2026-10-18",
  },
];

export const getTool = (slug: string): ToolMeta | undefined => TOOLS.find((t) => t.slug === slug);
