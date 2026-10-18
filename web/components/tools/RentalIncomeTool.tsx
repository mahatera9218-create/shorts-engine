"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { compareRental } from "@/lib/tools/rental-income";
import { won } from "@/lib/tools/tax";

export default function RentalIncomeTool() {
  const [rent, setRent] = useState("");
  const [registered, setRegistered] = useState<"yes" | "no">("no");
  const [other, setOther] = useState("");
  const [deductions, setDeductions] = useState("150");
  const [mode, setMode] = useState<"rate" | "actual">("rate");
  const [rate, setRate] = useState("");
  const [actual, setActual] = useState("");
  const [houses, setHouses] = useState<"1" | "2" | "3">("2");
  const [high, setHigh] = useState<"yes" | "no">("no");
  const [joint, setJoint] = useState<"yes" | "no">("no");

  const res = useMemo(() => {
    if (toWon(rent) <= 0) return null;
    return compareRental({
      rent: toWon(rent), registered: registered === "yes", otherIncome: toWon(other), deductions: toWon(deductions),
      expenseMode: mode, expenseRatePct: Number(rate || 0), actualExpense: toWon(actual),
      houseCount: Number(houses), highValueHouse: high === "yes", jointOwned: joint === "yes",
    });
  }, [rent, registered, other, deductions, mode, rate, actual, houses, high, joint]);

  return (
    <div>
      <ManwonInput label="1년 월세 수입 합계 (본인 몫)" hint="월세×개월 수. 보증금 이자(간주임대료)는 넣지 않습니다." value={rent} onChange={setRent} />
      <Choice label="소유 주택 수 (부부 합산)" value={houses} onChange={setHouses} options={[{ value: "1", label: "1주택" }, { value: "2", label: "2주택" }, { value: "3", label: "3주택 이상" }]} />
      <Choice label="기준시가 12억원 넘는 주택이 있나요?" value={high} onChange={setHigh} options={[{ value: "no", label: "없음" }, { value: "yes", label: "있음" }]} />
      <Choice label="임대사업자 등록(지자체+세무서 모두)" hint="등록 임대주택은 필요경비율 60%·기본공제 400만원, 미등록은 50%·200만원입니다." value={registered} onChange={setRegistered} options={[{ value: "no", label: "미등록/모름" }, { value: "yes", label: "등록함" }]} />
      <ManwonInput label="임대소득 외 다른 종합소득금액" hint="월급이면 '총급여−근로소득공제' 금액입니다. 없으면 0. 2,000만원을 넘으면 분리과세 기본공제가 없습니다." value={other} onChange={setOther} />
      <ManwonInput label="종합과세 때 받는 소득공제 합계" hint="본인 기본공제 150만원이 기본값입니다. 다른 공제가 있으면 합산해 수정하세요." value={deductions} onChange={setDeductions} />
      <Choice label="종합과세 때 필요경비 방식" value={mode} onChange={setMode} options={[{ value: "rate", label: "경비율(%) 직접 입력" }, { value: "actual", label: "실제 경비 입력" }]} />
      {mode === "rate" ? (
        <div className="tf">
          <label className="tf-label">종합과세 경비율 (%)</label>
          <div className="tf-hint">홈택스에서 본인 업종코드의 단순경비율을 조회해 입력하세요(해마다 달라 이 도구가 고정값을 쓰지 않습니다).</div>
          <div className="tf-num"><input inputMode="decimal" value={rate} placeholder="예: 42.6" onChange={(e) => setRate(e.target.value.replace(/[^0-9.]/g, ""))} /><span>%</span></div>
        </div>
      ) : (
        <ManwonInput label="실제 필요경비(1년)" hint="장부로 인정받을 수 있는 경비(수선비·감가상각 등)." value={actual} onChange={setActual} />
      )}
      <Choice label="공동소유(지분 나눠 소유)인가요?" value={joint} onChange={setJoint} options={[{ value: "no", label: "아니오" }, { value: "yes", label: "예" }]} />

      {res === null ? (
        <p className="cmp-sub">월세 수입을 입력하면 결과가 나옵니다.</p>
      ) : res.kind === "exempt" ? (
        <ResultBox tone="info" title="월세가 비과세일 수 있어요">
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      ) : res.kind === "comprehensive-only" ? (
        <ResultBox tone="warn" title="종합과세로 신고해야 해요">
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      ) : (
        <ResultBox tone={res.better === "similar" ? "info" : "good"} title={res.better === "similar" ? "두 방식의 세금이 비슷해요" : res.better === "separate" ? `분리과세(14%)가 약 ${won(res.diff)} 더 유리해요` : `종합과세가 약 ${won(-res.diff)} 더 유리해요`}>
          <table>
            <thead><tr><th></th><th>분리과세</th><th>종합과세</th></tr></thead>
            <tbody>
              <tr><td>소득금액</td><td>{won(res.separate.income)}</td><td>{won(res.comprehensive.income)}</td></tr>
              <tr><td>소득세</td><td>{won(res.separate.tax)}</td><td>{won(res.comprehensive.tax)}</td></tr>
              <tr><td>지방소득세(10%)</td><td>{won(res.separate.local)}</td><td>{won(res.comprehensive.local)}</td></tr>
              <tr><td><b>합계</b></td><td><b>{won(res.separate.total)}</b></td><td><b>{won(res.comprehensive.total)}</b></td></tr>
            </tbody>
          </table>
          <p className="tr-note">분리과세: 수입−필요경비({Math.round(res.separate.expenseRate * 100)}%)−기본공제({won(res.separate.basicDeduction)})에 14%. 종합과세는 다른 소득과 합산한 누진세율에서 임대 때문에 늘어나는 세금만 계산했습니다.</p>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
