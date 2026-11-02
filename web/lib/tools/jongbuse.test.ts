import { test } from "node:test";
import assert from "node:assert/strict";
import { calcJongbu, type JongbuInput } from "./jongbuse.ts";

const E = 100_000_000; // 1억
const base: JongbuInput = {
  publicPrice: 0, singleHome: true, heavy: false, fairRatioPct: 60, ageCreditPct: 0, holdCreditPct: 0,
};

test("1주택 공시 10억 → 기본공제 12억 이하라 비과세", () => {
  assert.equal(calcJongbu({ ...base, publicPrice: 10 * E }).exempt, true);
});

test("1주택 공시 15억 → 과세표준 1.8억, 종부세 90만원 + 농특세 18만", () => {
  const r = calcJongbu({ ...base, publicPrice: 15 * E });
  assert.equal(r.taxBase, 180_000_000);
  assert.equal(r.gross, 900_000); // 1.8억 × 0.5%
  assert.equal(r.jongbuse, 900_000);
  assert.equal(r.ruralTax, 180_000);
  assert.equal(r.total, 1_080_000);
});

test("1주택 세액공제 80% 상한(고령40+장기50)", () => {
  const r = calcJongbu({ ...base, publicPrice: 15 * E, ageCreditPct: 40, holdCreditPct: 50 });
  assert.equal(r.credit, 720_000); // 90만 × 80%
  assert.equal(r.jongbuse, 180_000);
});

test("비(非)1주택 9억 공제, 공시 20억 → 과세표준 6.6억, 산출 420만", () => {
  const r = calcJongbu({ ...base, singleHome: false, publicPrice: 20 * E });
  assert.equal(r.deduction, 900_000_000);
  assert.equal(r.taxBase, 660_000_000);
  assert.equal(r.gross, 4_200_000);
});

test("비1주택은 고령자·장기보유 공제 적용 안 함", () => {
  const r = calcJongbu({ ...base, singleHome: false, publicPrice: 20 * E, ageCreditPct: 40, holdCreditPct: 50 });
  assert.equal(r.credit, 0);
});
