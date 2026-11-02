import { test } from "node:test";
import assert from "node:assert/strict";
import { calcPensionCredit, type PensionInput } from "./pension-credit.ts";

const M = 10_000;
const base: PensionInput = { pensionSaving: 0, irp: 0, lowIncome: true };

test("연금저축 600만 (저소득 16.5%) → 99만원", () => {
  const r = calcPensionCredit({ ...base, pensionSaving: 600 * M });
  assert.equal(r.eligiblePension, 6_000_000);
  assert.equal(r.refund, 990_000);
});

test("연금저축 600만 (고소득 13.2%) → 79.2만원", () => {
  const r = calcPensionCredit({ ...base, pensionSaving: 600 * M, lowIncome: false });
  assert.equal(r.refund, 792_000);
});

test("연금저축 600만 + IRP 300만 = 900만 → 148.5만원", () => {
  const r = calcPensionCredit({ ...base, pensionSaving: 600 * M, irp: 300 * M });
  assert.equal(r.eligibleTotal, 9_000_000);
  assert.equal(r.refund, 1_485_000);
});

test("연금저축 1,000만 → 600만만 대상, 나머지는 IRP칸 없으면 초과", () => {
  const r = calcPensionCredit({ ...base, pensionSaving: 1000 * M });
  assert.equal(r.eligiblePension, 6_000_000);
  assert.equal(r.excess, 4_000_000);
  assert.equal(r.refund, 990_000);
});

test("IRP만 900만 → 합산 900만 대상", () => {
  const r = calcPensionCredit({ ...base, irp: 900 * M });
  assert.equal(r.eligibleIrp, 9_000_000);
  assert.equal(r.refund, 1_485_000);
});

test("연금저축 400 + IRP 600 = 1000만 → 900만 대상, 100만 초과", () => {
  const r = calcPensionCredit({ ...base, pensionSaving: 400 * M, irp: 600 * M });
  assert.equal(r.eligibleTotal, 9_000_000);
  assert.equal(r.excess, 1_000_000);
});
