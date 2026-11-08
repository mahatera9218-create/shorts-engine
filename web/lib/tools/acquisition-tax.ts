// 주택 취득세 계산: 기본세율(1~3%)·다주택 중과(8/12%) + 지방교육세 + 농어촌특별세 + 생애최초 감면.
// 규칙 2026 기준(지방세법). 조정대상지역 지정은 수시로 바뀌니 확인 필요로 안내.

export interface AcqInput {
  price: number; // 취득가액(원)
  homes: 1 | 2 | 3 | 4; // 취득 후 보유 주택 수(4 = 4주택 이상)
  adjusted: boolean; // 조정대상지역
  over85: boolean; // 전용면적 85㎡ 초과(농어촌특별세 대상)
  firstHome: boolean; // 생애최초 감면 대상(무주택·요건 충족)
}

/** 1주택 기본 취득세율: 6억 이하 1%, 6~9억 비례(1~3%), 9억 초과 3%. */
export function baseRate(price: number): number {
  if (price <= 600_000_000) return 0.01;
  if (price <= 900_000_000) {
    const r = (price * 2) / 300_000_000 / 100 - 3 / 100; // (가액×2/3억 − 3)/100
    return Math.min(0.03, Math.max(0.01, Math.round(r * 100000) / 100000));
  }
  return 0.03;
}

/** 다주택 중과 반영 취득세율. */
export function acqRate(p: AcqInput): number {
  if (p.adjusted) {
    if (p.homes >= 3) return 0.12;
    if (p.homes === 2) return 0.08;
  } else {
    if (p.homes >= 4) return 0.12;
    if (p.homes === 3) return 0.08;
  }
  return baseRate(p.price);
}

export interface AcqResult {
  rate: number; // 취득세율
  acqTax: number; // 취득세 본세
  firstHomeCut: number; // 생애최초 감면액
  eduTax: number; // 지방교육세
  ruralTax: number; // 농어촌특별세
  total: number; // 합계
  notes: string[];
}

export function calcAcquisition(p: AcqInput): AcqResult {
  const notes: string[] = [];
  const rate = acqRate(p);
  const acqTax = Math.floor(p.price * rate);
  // 지방교육세: 기본세율(1~3%) 구간은 취득세율의 1/10, 중과(8·12%)는 0.4% 고정.
  const eduRate = rate <= 0.03 ? rate * 0.1 : 0.004;
  const eduTax = Math.floor(p.price * eduRate);
  // 농어촌특별세: 85㎡ 초과만. 기본 0.2%, 중과 8%는 0.6%, 12%는 1.0%.
  const ruralRate = !p.over85 ? 0 : rate <= 0.03 ? 0.002 : rate === 0.08 ? 0.006 : 0.01;
  const ruralTax = Math.floor(p.price * ruralRate);
  // 생애최초 감면: 취득세에서 최대 200만원(요건 충족 시).
  const firstHomeCut = p.firstHome ? Math.min(2_000_000, acqTax) : 0;
  if (p.firstHome) notes.push("생애최초 감면은 세대 전원 무주택·취득가액 12억원 이하 등 요건을 모두 충족할 때만 받습니다(위택스·구청 확인). 최대 200만원을 취득세에서 뺐습니다.");
  if (rate === 0.08 || rate === 0.12) notes.push("다주택 중과세율을 적용했습니다. 조정대상지역 지정은 수시로 바뀌니 취득 전 꼭 확인하세요.");
  if (!p.over85) notes.push("전용면적 85㎡ 이하(국민주택규모)는 농어촌특별세가 비과세입니다.");
  notes.push("일시적 2주택 비과세·중과 예외, 증여·상속 취득, 오피스텔·분양권은 이 계산기 범위 밖입니다.");
  return { rate, acqTax, firstHomeCut, eduTax, ruralTax, total: acqTax - firstHomeCut + eduTax + ruralTax, notes };
}
