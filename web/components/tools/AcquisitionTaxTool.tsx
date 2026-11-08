"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { calcAcquisition } from "@/lib/tools/acquisition-tax";
import { won } from "@/lib/tools/tax";

export default function AcquisitionTaxTool() {
  const [price, setPrice] = useState("");
  const [homes, setHomes] = useState<"1" | "2" | "3" | "4">("1");
  const [adjusted, setAdjusted] = useState<"no" | "yes">("no");
  const [over85, setOver85] = useState<"no" | "yes">("no");
  const [first, setFirst] = useState<"no" | "yes">("no");

  const res = useMemo(() => {
    if (toWon(price) <= 0) return null;
    return calcAcquisition({
      price: toWon(price),
      homes: Number(homes) as 1 | 2 | 3 | 4,
      adjusted: adjusted === "yes",
      over85: over85 === "yes",
      firstHome: first === "yes" && homes === "1",
    });
  }, [price, homes, adjusted, over85, first]);

  return (
    <div>
      <ManwonInput label="취득가액(매매가)" hint="실제 거래가격. 분양권·오피스텔은 이 계산기 범위 밖입니다." value={price} onChange={setPrice} />
      <Choice label="취득 후 보유 주택 수" value={homes} onChange={setHomes} options={[{ value: "1", label: "1주택" }, { value: "2", label: "2주택" }, { value: "3", label: "3주택" }, { value: "4", label: "4주택+" }]} />
      <Choice label="조정대상지역인가요?" hint="조정지역은 2주택부터, 비조정은 3주택부터 중과됩니다. 지정은 수시로 바뀌니 확인하세요." value={adjusted} onChange={setAdjusted} options={[{ value: "no", label: "비조정" }, { value: "yes", label: "조정지역" }]} />
      <Choice label="전용면적 85㎡ 초과?" hint="85㎡ 이하는 농어촌특별세가 비과세입니다." value={over85} onChange={setOver85} options={[{ value: "no", label: "85㎡ 이하" }, { value: "yes", label: "85㎡ 초과" }]} />
      {homes === "1" ? (
        <Choice label="생애최초 구입 감면 대상?" hint="세대 전원 무주택·취득가 12억 이하 등 요건 충족 시 최대 200만원 감면." value={first} onChange={setFirst} options={[{ value: "no", label: "아니오/모름" }, { value: "yes", label: "예" }]} />
      ) : null}

      {res === null ? (
        <p className="cmp-sub">취득가액을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone="info" title={`예상 취득세 합계 약 ${won(res.total)}`}>
          <table>
            <tbody>
              <tr><td>취득세율</td><td>{(res.rate * 100).toFixed(res.rate <= 0.03 ? 2 : 0)}%</td></tr>
              <tr><td>취득세</td><td>{won(res.acqTax)}</td></tr>
              {res.firstHomeCut > 0 ? <tr><td>생애최초 감면</td><td>−{won(res.firstHomeCut)}</td></tr> : null}
              <tr><td>지방교육세</td><td>{won(res.eduTax)}</td></tr>
              <tr><td>농어촌특별세</td><td>{won(res.ruralTax)}</td></tr>
              <tr><td><b>합계</b></td><td><b>{won(res.total)}</b></td></tr>
            </tbody>
          </table>
          <ul>{res.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </ResultBox>
      )}
    </div>
  );
}
