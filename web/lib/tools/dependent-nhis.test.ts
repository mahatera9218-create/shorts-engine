import { test } from "node:test";
import assert from "node:assert/strict";
import { judge, type DependentInput } from "./dependent-nhis.ts";

const base: DependentInput = {
  relation: "spouse", siblingAge: "30to64", special: false,
  interestDividend: 0, salary: 0, business: 0, other: 0,
  hasBusinessRegistration: false, hasHousingRent: false, hasUncertainIncome: false,
  propertyBase: 300_000_000, spouseIncome: null,
};
const M = 10_000;

test("T1 배우자·사업자등록 없음·프리랜서 400만원 → 통과", () => {
  const r = judge({ ...base, business: 400 * M, interestDividend: 50 * M });
  assert.equal(r.verdict, "pass");
});
test("T2 사업자등록 없음이어도 사업소득 600만원 → 탈락", () => {
  assert.equal(judge({ ...base, business: 600 * M }).verdict, "fail");
});
test("T3 사업자등록 있음 + 사업소득 100만원 → 탈락", () => {
  assert.equal(judge({ ...base, hasBusinessRegistration: true, business: 100 * M }).verdict, "fail");
});
test("T4 부모·이자배당 1,500만원·재산 6억 → 탈락(재산 5.4억 초과 시 소득 1,000만원 이하)", () => {
  assert.equal(judge({ ...base, relation: "ascendant", interestDividend: 1500 * M, propertyBase: 600_000_000 }).verdict, "fail");
});
test("T5 부모·이자 1,900만원·재산 4억 → 확인 필요(2,000만원 경계)", () => {
  assert.equal(judge({ ...base, relation: "ascendant", interestDividend: 1900 * M, propertyBase: 400_000_000 }).verdict, "check");
});
test("T6 형제자매 50세·장애 없음 → 탈락", () => {
  assert.equal(judge({ ...base, relation: "sibling", siblingAge: "30to64", propertyBase: 100_000_000 }).verdict, "fail");
});
test("형제자매 65세 이상·재산 1억 → 통과", () => {
  assert.equal(judge({ ...base, relation: "sibling", siblingAge: "65plus", propertyBase: 100_000_000 }).verdict, "pass");
});
test("주택임대소득이 있으면 탈락", () => {
  assert.equal(judge({ ...base, hasHousingRent: true }).verdict, "fail");
});
test("장애인은 사업자등록이 있어도 사업소득 500만원 이하면 탈락하지 않음", () => {
  assert.notEqual(judge({ ...base, special: true, hasBusinessRegistration: true, business: 300 * M }).verdict, "fail");
});
test("소득 2,300만원 → 탈락, 1,000만원·재산 4억 → 통과", () => {
  assert.equal(judge({ ...base, interestDividend: 2300 * M }).verdict, "fail");
  assert.equal(judge({ ...base, interestDividend: 1000 * M }).verdict, "pass");
});
test("재산 9억 초과(경계 밖) → 탈락, 9억 근처 → 확인 필요", () => {
  assert.equal(judge({ ...base, propertyBase: 1_000_000_000 }).verdict, "fail");
  assert.equal(judge({ ...base, propertyBase: 880_000_000 }).verdict, "check");
});
test("재산 7억·소득 500만원 → 통과(5.4억~9억은 소득 1,000만원 이하면 인정)", () => {
  assert.equal(judge({ ...base, interestDividend: 500 * M, propertyBase: 700_000_000 }).verdict, "pass");
});
test("연금·분리과세 등 불확실 소득, 기타소득은 확인 필요", () => {
  assert.equal(judge({ ...base, hasUncertainIncome: true }).verdict, "check");
  assert.equal(judge({ ...base, other: 300 * M }).verdict, "check");
});
test("배우자 소득이 2,000만원 초과면 탈락", () => {
  assert.equal(judge({ ...base, spouseIncome: 3000 * M }).verdict, "fail");
});
