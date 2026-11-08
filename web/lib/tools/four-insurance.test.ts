import { test } from "node:test";
import assert from "node:assert/strict";
import { calcFourInsurance } from "./four-insurance.ts";

test("월 300만원 근로자 부담", () => {
  const r = calcFourInsurance({ monthlyPay: 3_000_000 });
  assert.equal(r.pension, 135_000); // 4.5%
  assert.equal(r.health, 106_350); // 3.545%
  assert.equal(r.ltc, 13_772); // 건강 × 12.95%
  assert.equal(r.employment, 27_000); // 0.9%
  assert.equal(r.employeeTotal, 282_122);
});
