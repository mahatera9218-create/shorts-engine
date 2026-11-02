"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcGift, type GiftRelation } from "@/lib/tools/gift-tax";
import { won } from "@/lib/tools/tax";

export default function GiftTaxTool() {
  const [amount, setAmount] = useState("");
  const [relation, setRelation] = useState<GiftRelation>("lineal-adult");
  const [prior, setPrior] = useState("");
  const [onTime, setOnTime] = useState<"yes" | "no">("yes");

  const res = useMemo(() => {
    if (toWon(amount) <= 0) return null;
    return calcGift({
      amount: toWon(amount),
      relation,
      priorGifts: toWon(prior),
      reportOnTime: onTime === "yes",
    });
  }, [amount, relation, prior, onTime]);

  return (
    <div>
      <ManwonInput label="증여받는 재산 가액" hint="현금은 금액 그대로, 부동산은 시가(없으면 공시가격)로 적습니다." value={amount} onChange={setAmount} />
      <Choice
        label="증여하는 사람과의 관계"
        value={relation}
        onChange={setRelation}
        options={[
          { value: "lineal-adult", label: "부모→성년자녀" },
          { value: "lineal-minor", label: "부모→미성년" },
          { value: "spouse", label: "배우자" },
          { value: "descendant-to-ascendant", label: "자녀→부모" },
          { value: "other-relative", label: "기타친족" },
          { value: "non-relative", label: "타인" },
        ]}
      />
      <ManwonInput label="같은 사람에게 최근 10년간 받은 증여 합계" hint="이번 건 제외. 없으면 0. 10년 내 증여는 합산해 세금을 다시 계산합니다." value={prior} onChange={setPrior} />
      <Choice label="증여받은 달의 말일부터 3개월 안에 신고하나요?" hint="기한 내 신고하면 신고세액공제 3%를 받습니다." value={onTime} onChange={setOnTime} options={[{ value: "yes", label: "예(기한 내)" }, { value: "no", label: "아니오" }]} />

      {res === null ? (
        <p className="cmp-sub">증여재산 가액을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone={res.payable === 0 ? "good" : "info"} title={res.payable === 0 ? "공제 범위라 낼 증여세가 없어요" : `예상 증여세 약 ${won(res.payable)}`}>
          <table>
            <tbody>
              <tr><td>증여재산 가액</td><td>{won(toWon(amount))}</td></tr>
              <tr><td>증여재산공제</td><td>−{won(res.deduction)}</td></tr>
              <tr><td>과세표준</td><td>{won(res.taxBase)}</td></tr>
              <tr><td>산출세액</td><td>{won(res.grossThis)}</td></tr>
              <tr><td>신고세액공제(3%)</td><td>−{won(res.reportCredit)}</td></tr>
              <tr><td><b>낼 증여세</b></td><td><b>{won(res.payable)}</b></td></tr>
            </tbody>
          </table>
          {res.payable > 0 ? <p className="tr-note">이번 증여가액 대비 실효세율 약 {res.effectiveRatePct.toFixed(1)}%. 부동산 증여라면 취득세가 별도로 붙습니다.</p> : null}
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
