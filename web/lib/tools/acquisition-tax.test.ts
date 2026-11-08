import { test } from "node:test";
import assert from "node:assert/strict";
import { calcAcquisition, baseRate, type AcqInput } from "./acquisition-tax.ts";

const E = 100_000_000;
const base: AcqInput = { price: 0, homes: 1, adjusted: false, over85: false, firstHome: false };

test("기본세율: 6억 1%, 7.5억 2%, 9억 3%", () => {
  assert.equal(baseRate(6 * E), 0.01);
  assert.equal(baseRate(7.5 * E), 0.02);
  assert.equal(baseRate(9 * E), 0.03);
  assert.equal(baseRate(12 * E), 0.03);
});

test("5억 1주택 → 취득세 500만 + 지방교육세 50만 = 550만", () => {
  const r = calcAcquisition({ ...base, price: 5 * E });
  assert.equal(r.acqTax, 5_000_000);
  assert.equal(r.eduTax, 500_000);
  assert.equal(r.total, 5_500_000);
});

test("10억 1주택 85㎡초과 → 3% + 교육세 0.3% + 농특세 0.2% = 3,500만", () => {
  const r = calcAcquisition({ ...base, price: 10 * E, over85: true });
  assert.equal(r.acqTax, 30_000_000);
  assert.equal(r.eduTax, 3_000_000);
  assert.equal(r.ruralTax, 2_000_000);
  assert.equal(r.total, 35_000_000);
});

test("조정지역 2주택 6억 → 8% 중과", () => {
  const r = calcAcquisition({ ...base, price: 6 * E, homes: 2, adjusted: true });
  assert.equal(r.rate, 0.08);
  assert.equal(r.acqTax, 48_000_000);
  assert.equal(r.eduTax, 2_400_000); // 0.4%
});

test("생애최초 감면 200만원", () => {
  const r = calcAcquisition({ ...base, price: 5 * E, firstHome: true });
  assert.equal(r.firstHomeCut, 2_000_000);
  assert.equal(r.total, 3_500_000); // 500만 − 200만 + 교육세 50만
});

test("비조정 3주택 → 8%, 비조정 4주택 → 12%", () => {
  assert.equal(calcAcquisition({ ...base, price: 5 * E, homes: 3 }).rate, 0.08);
  assert.equal(calcAcquisition({ ...base, price: 5 * E, homes: 4 }).rate, 0.12);
});
