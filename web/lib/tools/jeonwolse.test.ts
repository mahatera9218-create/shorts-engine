import { test } from "node:test";
import assert from "node:assert/strict";
import { calcConversion } from "./jeonwolse.ts";

test("전세→월세: 보증금 1억, 전환율 5.5% → 월 약 45.8만원", () => {
  const r = calcConversion({ direction: "toMonthly", amount: 100_000_000, ratePct: 5.5 });
  assert.equal(r.value, 458_333);
});
test("월세→전세: 월 50만원, 5.5% → 보증금 약 1.09억", () => {
  const r = calcConversion({ direction: "toDeposit", amount: 500_000, ratePct: 5.5 });
  assert.equal(r.value, 109_090_909);
});
