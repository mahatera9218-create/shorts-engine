"use client";
import { useMemo, useState } from "react";
import { Choice, Field, ManwonInput, ResultBox, toWon } from "./fields";
import { calcConversion } from "@/lib/tools/jeonwolse";
import { won } from "@/lib/tools/tax";

export default function JeonwolseTool() {
  const [dir, setDir] = useState<"toMonthly" | "toDeposit">("toMonthly");
  const [amount, setAmount] = useState("");
  const [rate, setRate] = useState("5.5");

  const res = useMemo(() => {
    if (toWon(amount) <= 0 || Number(rate || 0) <= 0) return null;
    return calcConversion({ direction: dir, amount: toWon(amount), ratePct: Number(rate) });
  }, [dir, amount, rate]);

  return (
    <div>
      <Choice label="무엇으로 바꾸나요?" value={dir} onChange={setDir} options={[{ value: "toMonthly", label: "전세→월세" }, { value: "toDeposit", label: "월세→전세" }]} />
      <ManwonInput label={dir === "toMonthly" ? "월세로 돌릴 보증금" : "월세(월 납부액)"} hint={dir === "toMonthly" ? "전세 보증금 중 월세로 전환할 금액." : "매달 내는 월세."} value={amount} onChange={setAmount} />
      <Field label="전환율 (%)" hint="법정 상한은 '기준금리 + 2%' 수준(대략 5.5%). 모르면 5.5로 두세요.">
        <div className="tf-num"><input inputMode="decimal" value={rate} placeholder="5.5" onChange={(e) => setRate(e.target.value.replace(/[^0-9.]/g, ""))} /><span>%</span></div>
      </Field>

      {res === null ? (
        <p className="cmp-sub">금액과 전환율을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={dir === "toMonthly" ? `환산 월세 약 ${won(res.value)} / 월` : `환산 보증금 약 ${won(res.value)}`}>
          <p className="tr-note">{dir === "toMonthly" ? `보증금 ${won(toWon(amount))}을(를) 전환율 ${rate}%로 월세로 돌리면 월 ${won(res.value)}입니다.` : `월세 ${won(toWon(amount))}을(를) 전환율 ${rate}%로 보증금으로 돌리면 약 ${won(res.value)}입니다.`}</p>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
