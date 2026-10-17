import { test } from "node:test";
import assert from "node:assert/strict";
import { compareSeller, type SellerInput } from "./seller-vat.ts";

const M = 10_000;
const base: SellerInput = { isNew: false, supply: 8000 * M, prevSupply: 7000 * M, openMonths: 12, purchase: 4000 * M, industry: "retail" };

test("소매업 8,000만원·매입 4,000만원: 간이 100만원 vs 일반 3,636,364원 → 간이 유리", () => {
  const r = compareSeller(base);
  assert.equal(r.eligibleSimple, true);
  assert.equal(r.simpleTax, 1_000_000); // 8000만×15%×10%=120만 − 4000만×0.5%=20만
  assert.equal(r.generalTax, 7_272_727 - 3_636_363);
  assert.equal(r.better, "simple");
  assert.equal(r.mustIssueInvoice, true); // 직전 7,000만 ≥ 4,800만
});
test("연 공급대가 4,500만원이면 납부면제(신고는 필요)", () => {
  const r = compareSeller({ ...base, supply: 4500 * M, prevSupply: 4000 * M, purchase: 0 });
  assert.equal(r.exempt, true);
  assert.equal(r.simpleTax, 0);
  assert.equal(r.mustIssueInvoice, false);
});
test("정확히 4,800만원은 면제 아님", () => {
  assert.equal(compareSeller({ ...base, supply: 4800 * M, purchase: 0 }).exempt, false);
});
test("직전 연도 1억400만원 이상이면 일반과세자, 정확히 1억400만원도 일반", () => {
  assert.equal(compareSeller({ ...base, prevSupply: 10400 * M }).eligibleSimple, false);
  assert.equal(compareSeller({ ...base, prevSupply: 10399 * M }).eligibleSimple, true);
});
test("신규 개업 7월(6개월) 공급대가 2,000만원 → 12개월 환산 4,000만원이라 면제", () => {
  const r = compareSeller({ ...base, isNew: true, supply: 2000 * M, openMonths: 6, purchase: 0 });
  assert.equal(r.annualized, 4000 * M);
  assert.equal(r.exempt, true);
  assert.equal(r.eligibleSimple, "choose");
});
test("도매업 등 배제 업종은 간이 불가", () => {
  const r = compareSeller({ ...base, industry: "excluded" });
  assert.equal(r.eligibleSimple, false);
  assert.equal(r.simpleTax, null);
});
test("매입이 매우 많으면 일반과세 환급이 나올 수 있고 일반이 유리", () => {
  const r = compareSeller({ ...base, supply: 6000 * M, purchase: 7000 * M });
  assert.ok(r.generalTax < 0);
  assert.equal(r.better, "general");
});
