import { test } from "node:test";
import assert from "node:assert/strict";
import { calcUnemployment, benefitDays } from "./unemployment.ts";

test("소정급여일수: 50세미만 4년 → 180일, 50+ 4년 → 210일", () => {
  assert.equal(benefitDays(false, 4), 180);
  assert.equal(benefitDays(true, 4), 210);
});
test("월 400만 → 1일 상한 66,000 적용, 180일", () => {
  const r = calcUnemployment({ avgMonthlyWage: 4_000_000, age50plus: false, insuredYears: 4 });
  assert.equal(r.daily, 66_000);
  assert.equal(r.capped, "cap");
  assert.equal(r.total, 11_880_000);
});
test("낮은 임금은 하한액 적용", () => {
  const r = calcUnemployment({ avgMonthlyWage: 1_500_000, age50plus: false, insuredYears: 2 });
  assert.equal(r.capped, "floor");
});
