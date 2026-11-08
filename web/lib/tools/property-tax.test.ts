import { test } from "node:test";
import assert from "node:assert/strict";
import { calcPropertyTax, type PropTaxInput } from "./property-tax.ts";

const E = 100_000_000;
const base: PropTaxInput = { publicPrice: 0, singleHome: false, fairRatioPct: 60, urbanArea: true };

test("공시 3억 표준·도시지역 → 과표 1.8억, 재산세 27만 + 도시지역분 + 교육세", () => {
  const r = calcPropertyTax({ ...base, publicPrice: 3 * E });
  assert.equal(r.taxBase, 180_000_000);
  assert.equal(r.propertyTax, 270_000); // 0.25%−18만
  assert.equal(r.urbanTax, 252_000); // 0.14%
  assert.equal(r.eduTax, 54_000); // 본세의 20%
  assert.equal(r.total, 576_000);
});

test("1주택 특례(공시 9억 이하)는 더 낮은 세율", () => {
  const std = calcPropertyTax({ ...base, publicPrice: 5 * E, urbanArea: false });
  const sp = calcPropertyTax({ ...base, publicPrice: 5 * E, singleHome: true, urbanArea: false });
  assert.equal(sp.special, true);
  assert.ok(sp.propertyTax < std.propertyTax);
});

test("1주택이라도 공시 9억 초과면 표준세율", () => {
  const r = calcPropertyTax({ ...base, publicPrice: 12 * E, singleHome: true });
  assert.equal(r.special, false);
});

test("도시지역분 미부과 지역", () => {
  const r = calcPropertyTax({ ...base, publicPrice: 3 * E, urbanArea: false });
  assert.equal(r.urbanTax, 0);
});
