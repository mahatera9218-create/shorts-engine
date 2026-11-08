"use client";
import { useMemo, useState } from "react";
import { Field, ManwonInput, ResultBox, toWon } from "./fields";
import { calcRetirement } from "@/lib/tools/retirement-tax";
import { won } from "@/lib/tools/tax";

export default function RetirementTaxTool() {
  const [payout, setPayout] = useState("");
  const [years, setYears] = useState("");

  const res = useMemo(() => {
    if (toWon(payout) <= 0 || Number(years || 0) <= 0) return null;
    return calcRetirement({ payout: toWon(payout), years: Number(years) });
  }, [payout, years]);

  return (
    <div>
      <ManwonInput label="퇴직금(퇴직소득)" hint="회사에서 받는 퇴직금 총액." value={payout} onChange={setPayout} />
      <Field label="근속연수(년)" hint="입사~퇴사. 1년 미만은 1년으로 올려 계산합니다.">
        <div className="tf-num"><input inputMode="numeric" pattern="[0-9]*" value={years} placeholder="0" onChange={(e) => setYears(e.target.value.replace(/[^0-9]/g, ""))} /><span>년</span></div>
      </Field>

      {res === null ? (
        <p className="cmp-sub">퇴직금과 근속연수를 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`예상 퇴직소득세 약 ${won(res.total)}`}>
          <table>
            <tbody>
              <tr><td>근속연수공제</td><td>−{won(res.serviceDed)}</td></tr>
              <tr><td>환산급여</td><td>{won(res.converted)}</td></tr>
              <tr><td>환산급여공제</td><td>−{won(res.convertedDed)}</td></tr>
              <tr><td>과세표준(환산)</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>퇴직소득세</td><td>{won(res.tax)}</td></tr>
              <tr><td>지방소득세(10%)</td><td>{won(res.local)}</td></tr>
              <tr><td><b>합계</b></td><td><b>{won(res.total)}</b></td></tr>
            </tbody>
          </table>
          <p className="tr-note">퇴직금 대비 실효세율 약 {res.effectivePct.toFixed(1)}%. 오래 근무할수록 세율이 크게 낮아집니다.</p>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
