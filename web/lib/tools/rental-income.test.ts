import { test } from "node:test";
import assert from "node:assert/strict";
import { compareRental, type RentalInput } from "./rental-income.ts";

const M = 10_000;
const base: RentalInput = {
  rent: 1000 * M, registered: false, otherIncome: 0, deductions: 150 * M,
  expenseMode: "rate", expenseRatePct: 42.6, actualExpense: 0,
  houseCount: 2, highValueHouse: false, jointOwned: false,
};

test("T1 미등록 1,000만원·타소득 0 → 분리 46.2만원, 종합 27.984만원, 종합과세 유리", () => {
  const r = compareRental(base);
  assert.equal(r.kind, "compare");
  if (r.kind !== "compare") return;
  assert.equal(r.separate.total, 462_000);
  assert.equal(r.comprehensive.total, 279_840);
  assert.equal(r.better, "comprehensive");
});
test("T2 등록 1,500만원 → 분리 30.8만원, 종합 46.926만원, 분리과세 유리", () => {
  const r = compareRental({ ...base, rent: 1500 * M, registered: true });
  assert.equal(r.kind, "compare");
  if (r.kind !== "compare") return;
  assert.equal(r.separate.total, 308_000);
  assert.equal(r.comprehensive.total, 469_260);
  assert.equal(r.better, "separate");
});
test("T3 다른 소득 3,000만원이면 기본공제 없음, 분리 77만원 vs 종합 94.71만원", () => {
  const r = compareRental({ ...base, otherIncome: 3000 * M });
  assert.equal(r.kind, "compare");
  if (r.kind !== "compare") return;
  assert.equal(r.separate.basicDeduction, 0);
  assert.equal(r.separate.total, 770_000);
  assert.equal(r.comprehensive.total, 947_100);
  assert.equal(r.better, "separate");
});
test("T4 수입 2,000만원 초과 → 종합과세 의무", () => {
  assert.equal(compareRental({ ...base, rent: 2500 * M }).kind, "comprehensive-only");
});
test("T5 1주택(고가주택 아님) → 비과세", () => {
  assert.equal(compareRental({ ...base, houseCount: 1 }).kind, "exempt");
  assert.notEqual(compareRental({ ...base, houseCount: 1, highValueHouse: true }).kind, "exempt");
});
test("실제경비 입력 방식", () => {
  const r = compareRental({ ...base, expenseMode: "actual", actualExpense: 600 * M });
  assert.equal(r.kind, "compare");
});
