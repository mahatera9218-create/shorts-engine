import { test } from "node:test";
import assert from "node:assert/strict";
import { calcGift, giftTaxGross, type GiftInput } from "./gift-tax.ts";

const E = 100_000_000; // 1억
const base: GiftInput = { amount: 0, relation: "lineal-adult", priorGifts: 0, reportOnTime: true };

test("성년 자녀에게 5천만원 → 공제로 세금 0", () => {
  const r = calcGift({ ...base, amount: 50_000_000 });
  assert.equal(r.payable, 0);
});

test("성년 자녀에게 3억 → 과세표준 2.5억, 산출 4천만, 신고공제 3%", () => {
  const r = calcGift({ ...base, amount: 3 * E });
  assert.equal(r.taxBase, 250_000_000);
  // 2.5억 → 20% − 1천만 누진공제 = 4천만
  assert.equal(r.grossThis, 40_000_000);
  assert.equal(r.reportCredit, 1_200_000);
  assert.equal(r.payable, 38_800_000);
});

test("배우자 6억은 전액 공제 → 0", () => {
  assert.equal(calcGift({ ...base, relation: "spouse", amount: 6 * E }).payable, 0);
});

test("미성년 자녀 공제 2천만원", () => {
  const r = calcGift({ ...base, relation: "lineal-minor", amount: 20_000_000 });
  assert.equal(r.payable, 0);
  assert.equal(r.deduction, 20_000_000);
});

test("10년 내 기존 증여 합산: 기존 1억 + 이번 2억(성년)", () => {
  // 합산 3억 − 5천만 = 2.5억 → 4천만. 기존 1억 − 5천만 = 5천만 → 10% = 5백만. 이번분 = 3,500만
  const r = calcGift({ ...base, amount: 2 * E, priorGifts: 1 * E });
  assert.equal(r.grossThis, 35_000_000);
});

test("세율표: 10억 → 30%−6천만 = 2.4억", () => {
  assert.equal(giftTaxGross(1_000_000_000), 240_000_000);
});

test("신고 안 하면 신고세액공제 없음", () => {
  const r = calcGift({ ...base, amount: 3 * E, reportOnTime: false });
  assert.equal(r.reportCredit, 0);
  assert.equal(r.payable, 40_000_000);
});
