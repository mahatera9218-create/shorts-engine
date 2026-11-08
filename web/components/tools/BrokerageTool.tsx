"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcBrokerage, type DealType } from "@/lib/tools/brokerage";
import { won } from "@/lib/tools/tax";

export default function BrokerageTool() {
  const [amount, setAmount] = useState("");
  const [type, setType] = useState<DealType>("sale");

  const res = useMemo(() => {
    if (toWon(amount) <= 0) return null;
    return calcBrokerage({ amount: toWon(amount), type });
  }, [amount, type]);

  return (
    <div>
      <Choice label="거래 종류" value={type} onChange={setType} options={[{ value: "sale", label: "매매·교환" }, { value: "lease", label: "전·월세(임대차)" }]} />
      <ManwonInput label={type === "sale" ? "매매 거래금액" : "임대차 거래금액(환산보증금)"} hint={type === "sale" ? "매매가." : "보증금 + 월세×100. (환산액이 5천만원 미만이면 월세×70)"} value={amount} onChange={setAmount} />

      {res === null ? (
        <p className="cmp-sub">거래금액을 입력하면 중개보수 상한이 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`중개보수 상한 약 ${won(res.maxFee)} (부가세 별도)`}>
          <table>
            <tbody>
              <tr><td>적용 상한요율</td><td>{res.ratePct}%</td></tr>
              {res.cap !== null ? <tr><td>한도액</td><td>{won(res.cap)}</td></tr> : null}
              <tr><td><b>상한 중개보수</b></td><td><b>{won(res.maxFee)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
