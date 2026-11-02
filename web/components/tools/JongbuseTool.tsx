"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcJongbu } from "@/lib/tools/jongbuse";
import { won } from "@/lib/tools/tax";

export default function JongbuseTool() {
  const [price, setPrice] = useState("");
  const [single, setSingle] = useState<"yes" | "no">("yes");
  const [heavy, setHeavy] = useState<"no" | "yes">("no");
  const [ratio, setRatio] = useState("60");
  const [age, setAge] = useState<"0" | "20" | "30" | "40">("0");
  const [hold, setHold] = useState<"0" | "20" | "40" | "50">("0");

  const res = useMemo(() => {
    if (toWon(price) <= 0) return null;
    return calcJongbu({
      publicPrice: toWon(price),
      singleHome: single === "yes",
      heavy: heavy === "yes",
      fairRatioPct: Number(ratio || 60),
      ageCreditPct: single === "yes" ? Number(age) : 0,
      holdCreditPct: single === "yes" ? Number(hold) : 0,
    });
  }, [price, single, heavy, ratio, age, hold]);

  return (
    <div>
      <ManwonInput label="내가 가진 주택 공시가격 합계" hint="부부 각자 '본인 몫'만. 공시가격은 '부동산 공시가격 알리미'에서 확인합니다. 시세가 아니라 공시가격입니다." value={price} onChange={setPrice} />
      <Choice label="1세대 1주택 단독명의인가요?" hint="단독명의 1주택은 기본공제 12억원, 그 외는 9억원입니다." value={single} onChange={setSingle} options={[{ value: "yes", label: "예(1주택 단독)" }, { value: "no", label: "아니오" }]} />
      <Choice label="주택 수" hint="3주택 이상이면 과세표준 12억 초과 구간부터 중과세율이 적용됩니다." value={heavy} onChange={setHeavy} options={[{ value: "no", label: "2주택 이하" }, { value: "yes", label: "3주택 이상" }]} />
      <div className="tf">
        <label className="tf-label">공정시장가액비율 (%)</label>
        <div className="tf-hint">해마다 고시로 바뀝니다. 최근 주택은 보통 60%였습니다. 올해 값을 모르면 60으로 두세요.</div>
        <div className="tf-num"><input inputMode="decimal" value={ratio} placeholder="60" onChange={(e) => setRatio(e.target.value.replace(/[^0-9.]/g, ""))} /><span>%</span></div>
      </div>
      {single === "yes" ? (
        <>
          <Choice label="고령자 세액공제 (만 나이)" hint="60세↑ 20% · 65세↑ 30% · 70세↑ 40%" value={age} onChange={setAge} options={[{ value: "0", label: "해당없음" }, { value: "20", label: "60대초(20%)" }, { value: "30", label: "65+(30%)" }, { value: "40", label: "70+(40%)" }]} />
          <Choice label="장기보유 세액공제 (보유기간)" hint="5년↑ 20% · 10년↑ 40% · 15년↑ 50% (고령자와 합쳐 최대 80%)" value={hold} onChange={setHold} options={[{ value: "0", label: "5년미만" }, { value: "20", label: "5년+(20%)" }, { value: "40", label: "10년+(40%)" }, { value: "50", label: "15년+(50%)" }]} />
        </>
      ) : null}

      {res === null ? (
        <p className="cmp-sub">공시가격 합계를 입력하면 결과가 나옵니다.</p>
      ) : res.exempt ? (
        <ResultBox tone="good" title="종합부동산세 대상이 아니에요">
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      ) : (
        <ResultBox tone="info" title={`예상 종합부동산세 약 ${won(res.total)}`}>
          <table>
            <tbody>
              <tr><td>공시가격 합계</td><td>{won(toWon(price))}</td></tr>
              <tr><td>기본공제</td><td>−{won(res.deduction)}</td></tr>
              <tr><td>과세표준(공정시장가액비율 적용)</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>산출세액</td><td>{won(res.gross)}</td></tr>
              {res.credit > 0 ? <tr><td>1주택 세액공제</td><td>−{won(res.credit)}</td></tr> : null}
              <tr><td>종합부동산세</td><td>{won(res.jongbuse)}</td></tr>
              <tr><td>농어촌특별세(20%)</td><td>{won(res.ruralTax)}</td></tr>
              <tr><td><b>합계</b></td><td><b>{won(res.total)}</b></td></tr>
            </tbody>
          </table>
          <p className="tr-note">재산세 중복분 공제·세부담 상한을 빼지 않은 대략값이라, 실제 고지액은 이보다 낮을 수 있습니다.</p>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
