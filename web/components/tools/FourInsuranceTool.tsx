"use client";
import { useMemo, useState } from "react";
import { ManwonInput, ResultBox, toWon } from "./fields";
import { calcFourInsurance } from "@/lib/tools/four-insurance";
import { won } from "@/lib/tools/tax";

export default function FourInsuranceTool() {
  const [pay, setPay] = useState("");

  const res = useMemo(() => {
    if (toWon(pay) <= 0) return null;
    return calcFourInsurance({ monthlyPay: toWon(pay) });
  }, [pay]);

  return (
    <div>
      <ManwonInput label="월 보수(세전)" hint="비과세 수당(식대 등)을 뺀 과세 대상 월급입니다." value={pay} onChange={setPay} />

      {res === null ? (
        <p className="cmp-sub">월 보수를 입력하면 근로자 부담 보험료가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`근로자 부담 합계 약 월 ${won(res.employeeTotal)}`}>
          <table>
            <tbody>
              <tr><td>국민연금(4.5%)</td><td>{won(res.pension)}</td></tr>
              <tr><td>건강보험(3.545%)</td><td>{won(res.health)}</td></tr>
              <tr><td>장기요양(건강×12.95%)</td><td>{won(res.ltc)}</td></tr>
              <tr><td>고용보험(0.9%)</td><td>{won(res.employment)}</td></tr>
              <tr><td><b>합계(월)</b></td><td><b>{won(res.employeeTotal)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
