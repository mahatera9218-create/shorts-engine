import { test } from "node:test";
import assert from "node:assert/strict";
import { calcInherit, type InheritInput } from "./inheritance-tax.ts";

const E = 100_000_000;
const base: InheritInput = { estate: 0, debts: 0, hasSpouse: false };

test("10억 상속·배우자 없음 → 공제 5억, 과표 5억, 산출 9천만", () => {
  const r = calcInherit({ ...base, estate: 10 * E });
  assert.equal(r.deduction, 500_000_000);
  assert.equal(r.taxBase, 500_000_000);
  assert.equal(r.gross, 90_000_000); // 5억×20%−1천만
  assert.equal(r.reportCredit, 2_700_000);
  assert.equal(r.payable, 87_300_000);
});

test("10억 상속·배우자 있음 → 공제 10억, 세금 0", () => {
  const r = calcInherit({ ...base, estate: 10 * E, hasSpouse: true });
  assert.equal(r.deduction, 1_000_000_000);
  assert.equal(r.payable, 0);
});

test("15억·배우자 있음 → 과표 5억, 산출 9천만", () => {
  const r = calcInherit({ ...base, estate: 15 * E, hasSpouse: true });
  assert.equal(r.taxBase, 500_000_000);
  assert.equal(r.gross, 90_000_000);
});

test("채무·장례비 차감", () => {
  const r = calcInherit({ ...base, estate: 8 * E, debts: 1 * E });
  assert.equal(r.taxBase, 200_000_000); // 7억 − 5억
});
