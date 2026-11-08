"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcInherit } from "@/lib/tools/inheritance-tax";
import { won } from "@/lib/tools/tax";

export default function InheritanceTaxTool() {
  const [estate, setEstate] = useState("");
  const [debts, setDebts] = useState("");
  const [spouse, setSpouse] = useState<"yes" | "no">("yes");

  const res = useMemo(() => {
    if (toWon(estate) <= 0) return null;
    return calcInherit({ estate: toWon(estate), debts: toWon(debts), hasSpouse: spouse === "yes" });
  }, [estate, debts, spouse]);

  return (
    <div>
      <ManwonInput label="상속재산 가액" hint="부동산·예금·주식 등 물려받는 재산의 합계(시가 기준)." value={estate} onChange={setEstate} />
      <ManwonInput label="채무·장례비" hint="피상속인의 빚, 미납 세금, 장례비용 등. 없으면 0." value={debts} onChange={setDebts} />
      <Choice label="배우자가 있나요?" hint="배우자가 있으면 배우자공제(최소 5억)로 세금이 크게 줄어듭니다." value={spouse} onChange={setSpouse} options={[{ value: "yes", label: "예" }, { value: "no", label: "아니오" }]} />

      {res === null ? (
        <p className="cmp-sub">상속재산 가액을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone={res.payable === 0 ? "good" : "info"} title={res.payable === 0 ? "공제 범위라 낼 상속세가 없어요" : `예상 상속세 약 ${won(res.payable)}`}>
          <table>
            <tbody>
              <tr><td>상속재산(채무 차감 후)</td><td>{won(Math.max(0, toWon(estate) - toWon(debts)))}</td></tr>
              <tr><td>공제 합계</td><td>−{won(res.deduction)}</td></tr>
              <tr><td>과세표준</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>산출세액</td><td>{won(res.gross)}</td></tr>
              <tr><td>신고세액공제(3%)</td><td>−{won(res.reportCredit)}</td></tr>
              <tr><td><b>낼 상속세</b></td><td><b>{won(res.payable)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
