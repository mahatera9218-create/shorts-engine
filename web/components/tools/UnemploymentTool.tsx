"use client";
import { useMemo, useState } from "react";
import { Choice, Field, ManwonInput, ResultBox, toWon } from "./fields";
import { calcUnemployment } from "@/lib/tools/unemployment";
import { won } from "@/lib/tools/tax";

export default function UnemploymentTool() {
  const [wage, setWage] = useState("");
  const [age, setAge] = useState<"under" | "over">("under");
  const [years, setYears] = useState("");

  const res = useMemo(() => {
    if (toWon(wage) <= 0 || Number(years || 0) <= 0) return null;
    return calcUnemployment({ avgMonthlyWage: toWon(wage), age50plus: age === "over", insuredYears: Number(years) });
  }, [wage, age, years]);

  return (
    <div>
      <ManwonInput label="월 평균임금(세전)" hint="퇴직 전 3개월 평균 월급. 상여·수당 포함." value={wage} onChange={setWage} />
      <Choice label="나이" hint="50세 이상·장애인은 소정급여일수가 더 깁니다." value={age} onChange={setAge} options={[{ value: "under", label: "50세 미만" }, { value: "over", label: "50세 이상·장애인" }]} />
      <Field label="고용보험 가입기간(년)" hint="실직 전까지 고용보험에 든 기간.">
        <div className="tf-num"><input inputMode="numeric" pattern="[0-9]*" value={years} placeholder="0" onChange={(e) => setYears(e.target.value.replace(/[^0-9]/g, ""))} /><span>년</span></div>
      </Field>

      {res === null ? (
        <p className="cmp-sub">월 평균임금과 가입기간을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`예상 실업급여 총 약 ${won(res.total)}`}>
          <table>
            <tbody>
              <tr><td>1일 구직급여</td><td>{won(res.daily)}{res.capped === "cap" ? " (상한)" : res.capped === "floor" ? " (하한)" : ""}</td></tr>
              <tr><td>소정급여일수</td><td>{res.days}일</td></tr>
              <tr><td><b>예상 총액</b></td><td><b>{won(res.total)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
