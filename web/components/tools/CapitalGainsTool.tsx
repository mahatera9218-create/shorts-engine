"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcGain } from "@/lib/tools/capital-gains";
import { won } from "@/lib/tools/tax";

function YearInput({ label, hint, value, onChange }: { label: string; hint?: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="tf">
      <label className="tf-label">{label}</label>
      {hint ? <div className="tf-hint">{hint}</div> : null}
      <div className="tf-num">
        <input inputMode="numeric" pattern="[0-9]*" value={value} placeholder="0" onChange={(e) => onChange(e.target.value.replace(/[^0-9]/g, ""))} />
        <span>년</span>
      </div>
    </div>
  );
}

export default function CapitalGainsTool() {
  const [sale, setSale] = useState("");
  const [acquire, setAcquire] = useState("");
  const [expense, setExpense] = useState("");
  const [hold, setHold] = useState("");
  const [live, setLive] = useState("");
  const [one, setOne] = useState<"yes" | "no">("yes");
  const [sur, setSur] = useState<"none" | "two" | "three">("none");

  const res = useMemo(() => {
    if (toWon(sale) <= 0 || toWon(acquire) <= 0) return null;
    return calcGain({
      sale: toWon(sale), acquire: toWon(acquire), expense: toWon(expense),
      holdYears: Number(hold || 0), liveYears: Number(live || 0),
      oneHouse: one === "yes", surcharge: sur,
    });
  }, [sale, acquire, expense, hold, live, one, sur]);

  return (
    <div>
      <ManwonInput label="양도가액(판 가격)" value={sale} onChange={setSale} />
      <ManwonInput label="취득가액(산 가격)" value={acquire} onChange={setAcquire} />
      <ManwonInput label="필요경비" hint="취득세·중개보수·자본적지출(발코니 확장 등). 영수증으로 입증되는 것만." value={expense} onChange={setExpense} />
      <YearInput label="보유기간(년)" hint="취득일~양도일. 1년 미만은 단기 70%, 1~2년은 60% 세율." value={hold} onChange={setHold} />
      <YearInput label="거주기간(년)" hint="실제 거주한 기간. 1세대 1주택 비과세·장기보유공제에 영향." value={live} onChange={setLive} />
      <Choice label="1세대 1주택인가요?" value={one} onChange={setOne} options={[{ value: "yes", label: "예" }, { value: "no", label: "아니오(다주택 등)" }]} />
      {one === "no" ? (
        <Choice label="조정지역 다주택 중과?" hint="현재 한시 배제 기간일 수 있어 기본은 '없음'. 적용 여부는 꼭 확인하세요." value={sur} onChange={setSur} options={[{ value: "none", label: "없음" }, { value: "two", label: "2주택(+20%p)" }, { value: "three", label: "3주택(+30%p)" }]} />
      ) : null}

      {res === null ? (
        <p className="cmp-sub">양도가액과 취득가액을 입력하면 결과가 나옵니다.</p>
      ) : res.kind === "loss" ? (
        <ResultBox tone="good" title="낼 양도세가 없어요">
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      ) : res.kind === "exempt" ? (
        <ResultBox tone="good" title="1세대 1주택 비과세예요">
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      ) : (
        <ResultBox tone="info" title={`예상 양도소득세 약 ${won(res.total)}`}>
          <table>
            <tbody>
              <tr><td>양도차익</td><td>{won(res.gain)}</td></tr>
              <tr><td>과세대상 차익</td><td>{won(res.taxableGain)}</td></tr>
              <tr><td>장기보유특별공제({Math.round(res.ltdPct * 100)}%)</td><td>−{won(res.ltdDeduction)}</td></tr>
              <tr><td>과세표준(기본공제 250만 반영)</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>세율</td><td>{res.rateLabel}</td></tr>
              <tr><td>양도소득세</td><td>{won(res.tax)}</td></tr>
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
