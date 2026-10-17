import { test } from "node:test";
import assert from "node:assert/strict";
import { judgeCreator, type CreatorInput } from "./creator-business.ts";

const M = 10_000;
const base: CreatorInput = {
  types: [], monthsActive: 0, itemsCount: 0, ongoing: false, hasStaffOrOffice: false,
  prevYearIncome: 0, withholding33: false, employed: false, alreadyRegistered: false,
};

test("T1 유튜버·애드센스 12개월·계속 → 등록 권고, 면세(940306)", () => {
  const r = judgeCreator({ ...base, types: ["adsense"], monthsActive: 12, itemsCount: 12, ongoing: true, prevYearIncome: 3000 * M });
  assert.equal(r.verdict, "advised");
  assert.equal(r.businessType, "exempt");
});
test("T2 기업 행사 강연 1회·3.3% → 등록 불필요 가능성(기타소득)", () => {
  const r = judgeCreator({ ...base, types: ["oneoff"], monthsActive: 1, itemsCount: 1, withholding33: true });
  assert.equal(r.verdict, "unlikely");
  assert.ok(r.notes.some((n) => n.includes("기타소득")));
});
test("T3 애드포스트만 8개월·계속 → 확인 필요 플래그(등록 권고 수준이면 권고 유지)", () => {
  const r = judgeCreator({ ...base, types: ["adpost"], monthsActive: 8, itemsCount: 8, ongoing: true });
  assert.equal(r.verdict, "advised");
  assert.ok(r.flags.length > 0);
});
test("T4 체험단 3번(현물)·계속 미정 → 확인 필요", () => {
  const r = judgeCreator({ ...base, types: ["inkind"], monthsActive: 2, itemsCount: 3 });
  assert.equal(r.verdict, "check");
});
test("T5 직원 있음·애드센스 → 과세사업자(921505), 작년 1억2천만원이면 간이 불가 안내", () => {
  const r = judgeCreator({ ...base, types: ["adsense", "sponsor"], monthsActive: 12, itemsCount: 20, ongoing: true, hasStaffOrOffice: true, prevYearIncome: 12000 * M });
  assert.equal(r.verdict, "advised");
  assert.equal(r.businessType, "taxable");
  assert.ok(r.notes.some((n) => n.includes("간이과세 불가")));
});
test("T6 직장인 퇴근 후 유튜브 3개월·계속 → 등록 권고·면세", () => {
  const r = judgeCreator({ ...base, types: ["adsense"], monthsActive: 3, itemsCount: 3, ongoing: true, employed: true });
  assert.equal(r.verdict, "advised");
  assert.equal(r.businessType, "exempt");
});
test("수익이 거의 없고 계속 계획도 없으면 확인 필요(등록 불필요라고 단정하지 않음)", () => {
  const r = judgeCreator({ ...base, types: ["donation"], monthsActive: 1, itemsCount: 1 });
  assert.equal(r.verdict, "check");
});
