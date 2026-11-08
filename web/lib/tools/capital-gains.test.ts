import { test } from "node:test";
import assert from "node:assert/strict";
import { calcGain, type GainInput } from "./capital-gains.ts";

const E = 100_000_000;
const base: GainInput = {
  sale: 0, acquire: 0, expense: 0, holdYears: 5, liveYears: 0, oneHouse: false, surcharge: "none",
};

test("손실이면 세금 없음", () => {
  assert.equal(calcGain({ ...base, sale: 5 * E, acquire: 6 * E }).kind, "loss");
});

test("1주택 2년↑·12억 이하 → 비과세", () => {
  assert.equal(calcGain({ ...base, sale: 10 * E, acquire: 6 * E, holdYears: 3, oneHouse: true }).kind, "exempt");
});

test("1주택 15억(12억 초과)·10년 보유·10년 거주 → 고가주택 안분 + 장특공 80%", () => {
  const r = calcGain({ ...base, sale: 15 * E, acquire: 8 * E, expense: 2000 * 10_000, holdYears: 10, liveYears: 10, oneHouse: true });
  assert.equal(r.kind, "tax");
  if (r.kind !== "tax") return;
  // 차익 6.8억 × (3/15)=1.36억, 장특공 80% → 과표 1.36억−1.088억−250만 = 2,470만
  assert.equal(r.taxableGain, 136_000_000);
  assert.equal(r.ltdPct, 0.8);
  assert.equal(r.taxBase, 24_700_000);
  assert.equal(r.tax, 2_445_000); // 15%−126만
});

test("일반(다주택) 5년 보유 → 장특공 10%", () => {
  const r = calcGain({ ...base, sale: 8 * E, acquire: 5 * E, expense: 1000 * 10_000, holdYears: 5 });
  assert.equal(r.kind, "tax");
  if (r.kind !== "tax") return;
  assert.equal(r.ltdPct, 0.1);
});

test("1년 미만 단기 보유 → 70%", () => {
  const r = calcGain({ ...base, sale: 6 * E, acquire: 5 * E, holdYears: 0 });
  assert.equal(r.kind, "tax");
  if (r.kind !== "tax") return;
  assert.match(r.rateLabel, /70%/);
});
