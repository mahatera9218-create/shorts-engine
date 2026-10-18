"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { judgeCreator, type IncomeType } from "@/lib/tools/creator-business";

const TYPES: { value: IncomeType; label: string }[] = [
  { value: "adsense", label: "구글 애드센스" }, { value: "adpost", label: "네이버 애드포스트" }, { value: "sponsor", label: "협찬(현금)" },
  { value: "inkind", label: "체험단·제품 협찬(현물)" }, { value: "affiliate", label: "제휴 마케팅 수수료" }, { value: "selling", label: "직접 판매·공동구매" },
  { value: "donation", label: "후원·슈퍼챗" }, { value: "oneoff", label: "강연·원고 등 1회성" },
];

export default function CreatorBusinessTool() {
  const [types, setTypes] = useState<IncomeType[]>([]);
  const [months, setMonths] = useState("");
  const [items, setItems] = useState("");
  const [ongoing, setOngoing] = useState<"yes" | "no">("yes");
  const [staff, setStaff] = useState<"yes" | "no">("no");
  const [prev, setPrev] = useState("");
  const [w33, setW33] = useState<"yes" | "no">("no");
  const [employed, setEmployed] = useState<"yes" | "no">("no");
  const [registered, setRegistered] = useState<"yes" | "no">("no");

  const toggle = (v: IncomeType) => setTypes((t) => (t.includes(v) ? t.filter((x) => x !== v) : [...t, v]));
  const res = useMemo(() => judgeCreator({
    types, monthsActive: Number(months || 0), itemsCount: Number(items || 0), ongoing: ongoing === "yes",
    hasStaffOrOffice: staff === "yes", prevYearIncome: toWon(prev), withholding33: w33 === "yes", employed: employed === "yes", alreadyRegistered: registered === "yes",
  }), [types, months, items, ongoing, staff, prev, w33, employed, registered]);

  return (
    <div>
      <div className="tf">
        <label className="tf-label">어떤 수입이 있나요? (여러 개 선택)</label>
        <div className="tf-choice">
          {TYPES.map((t) => (
            <button key={t.value} type="button" aria-pressed={types.includes(t.value)} className={types.includes(t.value) ? "on" : ""} onClick={() => toggle(t.value)}>{t.label}</button>
          ))}
        </div>
      </div>
      <div className="tf">
        <label className="tf-label">올해 수익이 난 달은 몇 개월인가요?</label>
        <div className="tf-num"><input inputMode="numeric" value={months} placeholder="0" onChange={(e) => setMonths(e.target.value.replace(/[^0-9]/g, ""))} /><span>개월</span></div>
      </div>
      <div className="tf">
        <label className="tf-label">올해 수익 건수 (정산·계약 횟수)</label>
        <div className="tf-num"><input inputMode="numeric" value={items} placeholder="0" onChange={(e) => setItems(e.target.value.replace(/[^0-9]/g, ""))} /><span>건</span></div>
      </div>
      <Choice label="앞으로도 계속 수익 활동을 할 계획인가요?" value={ongoing} onChange={setOngoing} options={[{ value: "yes", label: "예" }, { value: "no", label: "아니오" }]} />
      <Choice label="직원을 두거나 별도 사무실이 있나요?" value={staff} onChange={setStaff} options={[{ value: "no", label: "없음(혼자)" }, { value: "yes", label: "있음" }]} />
      <ManwonInput label="작년 총수입(대략)" value={prev} onChange={setPrev} />
      <Choice label="3.3% 원천징수를 당한 적이 있나요?" value={w33} onChange={setW33} options={[{ value: "no", label: "아니오/모름" }, { value: "yes", label: "예" }]} />
      <Choice label="직장에 다니고 있나요?" value={employed} onChange={setEmployed} options={[{ value: "no", label: "아니오" }, { value: "yes", label: "예" }]} />
      <Choice label="이미 사업자등록을 했나요?" value={registered} onChange={setRegistered} options={[{ value: "no", label: "아니오" }, { value: "yes", label: "예" }]} />

      {types.length === 0 ? (
        <p className="cmp-sub">수입 종류를 하나 이상 선택하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone={res.verdict === "advised" ? "warn" : res.verdict === "unlikely" ? "good" : "info"}
          title={res.verdict === "advised" ? "사업자등록을 권해요" : res.verdict === "unlikely" ? "사업자등록이 필요 없을 가능성이 있어요" : "개별 확인이 필요해요"}>
          {res.flags.length > 0 ? <ul>{res.flags.map((f, i) => <li key={i}>{f}</li>)}</ul> : null}
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
          <p className="tr-note">‘계속적·반복적 활동’의 판단은 개별 사정에 따라 달라지며, 이 도구의 점수 기준(3개월·3건 등)은 법정 기준이 아닌 참고용입니다. 국세청 126 또는 관할 세무서에서 확인하세요.</p>
        </ResultBox>
      )}
    </div>
  );
}
