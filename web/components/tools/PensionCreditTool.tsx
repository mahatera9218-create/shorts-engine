"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcPensionCredit } from "@/lib/tools/pension-credit";
import { won } from "@/lib/tools/tax";

export default function PensionCreditTool() {
  const [pension, setPension] = useState("");
  const [irp, setIrp] = useState("");
  const [low, setLow] = useState<"yes" | "no">("yes");

  const res = useMemo(() => {
    if (toWon(pension) + toWon(irp) <= 0) return null;
    return calcPensionCredit({
      pensionSaving: toWon(pension),
      irp: toWon(irp),
      lowIncome: low === "yes",
    });
  }, [pension, irp, low]);

  return (
    <div>
      <ManwonInput label="올해 연금저축 납입액" hint="증권사·은행의 '연금저축' 계좌에 넣은 금액. 세액공제 한도는 600만원입니다." value={pension} onChange={setPension} />
      <ManwonInput label="올해 IRP 등 추가 납입액" hint="IRP(개인형 퇴직연금)에 넣은 금액. 연금저축과 합쳐 900만원까지 공제됩니다." value={irp} onChange={setIrp} />
      <Choice label="소득 구간" hint="총급여 5,500만원(사업 등 종합소득 4,500만원) 이하면 16.5%, 넘으면 13.2% 공제." value={low} onChange={setLow} options={[{ value: "yes", label: "5,500만원 이하(16.5%)" }, { value: "no", label: "초과(13.2%)" }]} />

      {res === null ? (
        <p className="cmp-sub">납입액을 입력하면 돌려받을 세금이 나옵니다.</p>
      ) : (
        <ResultBox tone="good" title={`올해 약 ${won(res.refund)} 덜 내요(세액공제)`}>
          <table>
            <tbody>
              <tr><td>공제 대상 연금저축</td><td>{won(res.eligiblePension)}</td></tr>
              <tr><td>공제 대상 IRP</td><td>{won(res.eligibleIrp)}</td></tr>
              <tr><td>공제 대상 합계</td><td>{won(res.eligibleTotal)}</td></tr>
              <tr><td>공제율</td><td>{res.ratePct}%</td></tr>
              <tr><td><b>세액공제(환급)</b></td><td><b>{won(res.refund)}</b></td></tr>
              {res.excess > 0 ? <tr><td>한도 초과 납입</td><td>{won(res.excess)}</td></tr> : null}
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
