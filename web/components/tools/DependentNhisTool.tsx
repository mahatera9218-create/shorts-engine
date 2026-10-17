"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { judge, type AgeGroup, type Relation } from "@/lib/tools/dependent-nhis";

export default function DependentNhisTool() {
  const [relation, setRelation] = useState<Relation>("spouse");
  const [age, setAge] = useState<AgeGroup>("30to64");
  const [special, setSpecial] = useState<"yes" | "no">("no");
  const [intDiv, setIntDiv] = useState("");
  const [salary, setSalary] = useState("");
  const [business, setBusiness] = useState("");
  const [other, setOther] = useState("");
  const [reg, setReg] = useState<"yes" | "no">("no");
  const [rent, setRent] = useState<"yes" | "no">("no");
  const [uncertain, setUncertain] = useState<"yes" | "no">("no");
  const [property, setProperty] = useState("");
  const [spouse, setSpouse] = useState<"none" | "has">("none");
  const [spouseIncome, setSpouseIncome] = useState("");

  const res = useMemo(() => judge({
    relation, siblingAge: age, special: special === "yes",
    interestDividend: toWon(intDiv), salary: toWon(salary), business: toWon(business), other: toWon(other),
    hasBusinessRegistration: reg === "yes", hasHousingRent: rent === "yes", hasUncertainIncome: uncertain === "yes",
    propertyBase: toWon(property), spouseIncome: spouse === "has" ? toWon(spouseIncome) : null,
  }), [relation, age, special, intDiv, salary, business, other, reg, rent, uncertain, property, spouse, spouseIncome]);

  return (
    <div>
      <Choice label="피부양자가 되려는 사람은 직장가입자의…" value={relation} onChange={setRelation}
        options={[{ value: "spouse", label: "배우자" }, { value: "ascendant", label: "부모 등 직계존속" }, { value: "descendant", label: "자녀 등 직계비속" }, { value: "sibling", label: "형제자매" }, { value: "other", label: "기타" }]} />
      {relation === "sibling" ? (
        <Choice label="형제자매의 나이" value={age} onChange={setAge} options={[{ value: "under30", label: "30세 미만" }, { value: "30to64", label: "30~64세" }, { value: "65plus", label: "65세 이상" }]} />
      ) : null}
      <Choice label="장애인 또는 국가유공·보훈보상 상이자인가요?" value={special} onChange={setSpecial} options={[{ value: "no", label: "아니오" }, { value: "yes", label: "예" }]} />
      <ManwonInput label="이자·배당 소득금액 (연)" value={intDiv} onChange={setIntDiv} />
      <ManwonInput label="근로소득금액 (연)" hint="총급여가 아니라 근로소득공제 후 금액입니다. 모르면 총급여를 넣으세요(더 보수적)." value={salary} onChange={setSalary} />
      <ManwonInput label="사업소득금액 (연, 3.3% 프리랜서·부업 포함)" value={business} onChange={setBusiness} />
      <Choice label="사업자등록을 했나요?" value={reg} onChange={setReg} options={[{ value: "no", label: "안 함" }, { value: "yes", label: "함" }]} />
      <ManwonInput label="기타소득금액 (연, 원고료·강연료 등)" value={other} onChange={setOther} />
      <Choice label="주택 임대소득이 있나요?" value={rent} onChange={setRent} options={[{ value: "no", label: "없음" }, { value: "yes", label: "있음" }]} />
      <Choice label="연금소득·분리과세 소득·상가 등 비주택 임대소득이 있나요?" hint="있으면 소득 산정 방식이 달라 '확인 필요'로 안내합니다." value={uncertain} onChange={setUncertain} options={[{ value: "no", label: "없음" }, { value: "yes", label: "있음" }]} />
      <ManwonInput label="재산세 과세표준 합계" hint="재산세 고지서 또는 위택스에서 확인합니다(시가·공시가격이 아님)." value={property} onChange={setProperty} />
      <Choice label="피부양자가 되려는 사람이 기혼인가요?" hint="기혼이면 부부 모두 소득요건을 충족해야 합니다." value={spouse} onChange={setSpouse} options={[{ value: "none", label: "아니오" }, { value: "has", label: "예" }]} />
      {spouse === "has" ? <ManwonInput label="배우자 소득 합계 (연)" value={spouseIncome} onChange={setSpouseIncome} /> : null}

      {property === "" ? (
        <p className="cmp-sub">재산세 과세표준 합계를 입력하면(없으면 0) 결과가 나옵니다.</p>
      ) : (
      <ResultBox tone={res.verdict === "pass" ? "good" : res.verdict === "fail" ? "warn" : "info"}
        title={res.verdict === "pass" ? "소득·재산 요건은 충족으로 보여요" : res.verdict === "fail" ? "피부양자에서 탈락할 가능성이 높아요" : "이 도구만으로는 판단하기 어려워요(확인 필요)"}>
        <ul>{res.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
        {res.notes.length > 0 ? <p className="tr-note">{res.notes.join(" ")}</p> : null}
        <p className="tr-note">정확한 확인: <a href="https://www.nhis.or.kr/nhis/policy/wbhada07500m01.do" target="_blank" rel="nofollow noopener">국민건강보험공단 피부양자 자격 모의계산</a> 또는 1577-1000.</p>
      </ResultBox>
      )}
    </div>
  );
}
