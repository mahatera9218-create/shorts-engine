"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcPropertyTax } from "@/lib/tools/property-tax";
import { won } from "@/lib/tools/tax";

export default function PropertyTaxTool() {
  const [price, setPrice] = useState("");
  const [single, setSingle] = useState<"yes" | "no">("yes");
  const [ratio, setRatio] = useState("");
  const [urban, setUrban] = useState<"yes" | "no">("yes");

  const defaultRatio = single === "yes" ? 45 : 60;
  const res = useMemo(() => {
    if (toWon(price) <= 0) return null;
    return calcPropertyTax({
      publicPrice: toWon(price),
      singleHome: single === "yes",
      fairRatioPct: Number(ratio || defaultRatio),
      urbanArea: urban === "yes",
    });
  }, [price, single, ratio, urban, defaultRatio]);

  return (
    <div>
      <ManwonInput label="주택 공시가격" hint="시세가 아니라 공시가격입니다('부동산 공시가격 알리미'에서 확인)." value={price} onChange={setPrice} />
      <Choice label="1세대 1주택인가요?" hint="공시 9억 이하 1주택은 특례(낮은) 세율이 적용됩니다." value={single} onChange={setSingle} options={[{ value: "yes", label: "예" }, { value: "no", label: "아니오" }]} />
      <div className="tf">
        <label className="tf-label">공정시장가액비율 (%)</label>
        <div className="tf-hint">해마다 고시로 바뀝니다. 1주택은 보통 43~45%, 그 외는 60%. 모르면 비워 두면 {defaultRatio}%로 계산합니다.</div>
        <div className="tf-num"><input inputMode="decimal" value={ratio} placeholder={String(defaultRatio)} onChange={(e) => setRatio(e.target.value.replace(/[^0-9.]/g, ""))} /><span>%</span></div>
      </div>
      <Choice label="도시지역인가요?" hint="도시지역이면 재산세 도시지역분(0.14%)이 더해집니다." value={urban} onChange={setUrban} options={[{ value: "yes", label: "도시지역" }, { value: "no", label: "아니오/모름" }]} />

      {res === null ? (
        <p className="cmp-sub">공시가격을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`예상 재산세 합계 약 ${won(res.total)} (연간)`}>
          <table>
            <tbody>
              <tr><td>과세표준</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>재산세 본세{res.special ? " (1주택 특례)" : ""}</td><td>{won(res.propertyTax)}</td></tr>
              {res.urbanTax > 0 ? <tr><td>도시지역분</td><td>{won(res.urbanTax)}</td></tr> : null}
              <tr><td>지방교육세</td><td>{won(res.eduTax)}</td></tr>
              <tr><td><b>합계(연간)</b></td><td><b>{won(res.total)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
