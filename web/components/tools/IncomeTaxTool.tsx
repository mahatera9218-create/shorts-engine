"use client";
import { useMemo, useState } from "react";
import { ManwonInput, ResultBox, toWon } from "./fields";
import { calcIncomeTax } from "@/lib/tools/income-tax-calc";
import { won } from "@/lib/tools/tax";

export default function IncomeTaxTool() {
  const [income, setIncome] = useState("");
  const [ded, setDed] = useState("");
  const [credit, setCredit] = useState("");

  const res = useMemo(() => {
    if (toWon(income) <= 0) return null;
    return calcIncomeTax({ incomeAmount: toWon(income), deductions: toWon(ded), taxCredits: toWon(credit) });
  }, [income, ded, credit]);

  return (
    <div>
      <ManwonInput label="종합소득금액" hint="수입이 아니라 '수입 − 필요경비'입니다. 근로소득만 있으면 '총급여 − 근로소득공제' 금액을 넣으세요." value={income} onChange={setIncome} />
      <ManwonInput label="소득공제 합계" hint="본인·부양가족 인적공제(1인 150만), 국민연금보험료 등. 모르면 비워 두세요." value={ded} onChange={setDed} />
      <ManwonInput label="세액공제 합계" hint="근로·자녀·연금계좌 세액공제 등 산출세액에서 바로 빼는 금액. 모르면 비워 두세요." value={credit} onChange={setCredit} />

      {res === null ? (
        <p className="cmp-sub">종합소득금액을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`예상 세금 약 ${won(res.total)} (한계세율 ${res.marginalPct}%)`}>
          <table>
            <tbody>
              <tr><td>과세표준</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>산출세액</td><td>{won(res.gross)}</td></tr>
              <tr><td>세액공제</td><td>−{won(res.gross - res.determined)}</td></tr>
              <tr><td>결정세액(소득세)</td><td>{won(res.determined)}</td></tr>
              <tr><td>지방소득세(10%)</td><td>{won(res.local)}</td></tr>
              <tr><td><b>합계</b></td><td><b>{won(res.total)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
