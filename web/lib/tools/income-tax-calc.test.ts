import { test } from "node:test";
import assert from "node:assert/strict";
import { calcIncomeTax } from "./income-tax-calc.ts";

const M = 10_000;

test("과세표준 3,000만원 → 15%−126만 = 324만, 지방세 32.4만", () => {
  const r = calcIncomeTax({ incomeAmount: 3000 * M, deductions: 0, taxCredits: 0 });
  assert.equal(r.taxBase, 30_000_000);
  assert.equal(r.gross, 3_240_000); // 3,000만×15% − 126만
  assert.equal(r.local, 324_000);
  assert.equal(r.total, 3_564_000);
  assert.equal(r.marginalPct, 15);
});

test("소득공제 반영: 소득금액 5,000만 − 공제 1,500만 → 과표 3,500만", () => {
  const r = calcIncomeTax({ incomeAmount: 5000 * M, deductions: 1500 * M, taxCredits: 0 });
  assert.equal(r.taxBase, 35_000_000);
  assert.equal(r.gross, 3_990_000); // 3,500만×15%−126만
});

test("세액공제가 산출세액보다 크면 결정세액 0", () => {
  const r = calcIncomeTax({ incomeAmount: 1500 * M, deductions: 0, taxCredits: 200 * M });
  assert.equal(r.determined, 0);
  assert.equal(r.total, 0);
});

test("과세표준 1,400만 이하 → 6%", () => {
  const r = calcIncomeTax({ incomeAmount: 1000 * M, deductions: 0, taxCredits: 0 });
  assert.equal(r.gross, 600_000);
  assert.equal(r.marginalPct, 6);
});
