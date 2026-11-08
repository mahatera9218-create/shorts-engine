import { test } from "node:test";
import assert from "node:assert/strict";
import { calcRetirement, serviceDeduction } from "./retirement-tax.ts";

test("근속연수공제: 10년 → 1,500만", () => {
  assert.equal(serviceDeduction(10), 15_000_000);
});
test("퇴직금 5천만·10년 → 과표 1,360만, 세금 약 74.8만", () => {
  const r = calcRetirement({ payout: 50_000_000, years: 10 });
  assert.equal(r.serviceDed, 15_000_000);
  assert.equal(r.converted, 42_000_000);
  assert.equal(r.convertedDed, 28_400_000);
  assert.equal(r.taxBase, 13_600_000);
  assert.equal(r.tax, 680_000);
  assert.equal(r.total, 748_000);
});
