import { test } from "node:test";
import assert from "node:assert/strict";
import { incomeTax, localIncomeTax } from "./tax.ts";

test("소득세 누진세율: 구간 경계와 누진공제", () => {
  assert.equal(incomeTax(0), 0);
  assert.equal(incomeTax(-5), 0);
  assert.equal(incomeTax(14_000_000), 840_000); // 6%
  assert.equal(incomeTax(50_000_000), 6_240_000); // 15% − 126만
  assert.equal(incomeTax(60_000_000), 8_640_000); // 24% − 576만 (소득세율표 글의 864만원 예시)
  assert.equal(incomeTax(1_000_000_000), 384_060_000);
  assert.equal(incomeTax(2_000_000_000), 834_060_000); // 45% − 6,594만
});

test("지방소득세는 산출세액의 10%", () => {
  assert.equal(localIncomeTax(8_640_000), 864_000);
  assert.equal(localIncomeTax(999), 99);
});
