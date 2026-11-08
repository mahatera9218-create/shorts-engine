import { test } from "node:test";
import assert from "node:assert/strict";
import { calcBrokerage } from "./brokerage.ts";

const E = 100_000_000;
test("매매 3억 → 0.4%, 120만원", () => {
  const r = calcBrokerage({ amount: 3 * E, type: "sale" });
  assert.equal(r.ratePct, 0.4);
  assert.equal(r.maxFee, 1_200_000);
});
test("매매 4,900만 → 0.6%지만 한도 25만", () => {
  const r = calcBrokerage({ amount: 49_000_000, type: "sale" });
  assert.equal(r.maxFee, 250_000);
});
test("매매 10억 → 0.5%, 500만원", () => {
  assert.equal(calcBrokerage({ amount: 10 * E, type: "sale" }).maxFee, 5_000_000);
});
test("임대차 9천만 → 0.4%지만 한도 30만", () => {
  assert.equal(calcBrokerage({ amount: 90_000_000, type: "lease" }).maxFee, 300_000);
});
