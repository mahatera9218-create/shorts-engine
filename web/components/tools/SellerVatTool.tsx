"use client";
import { useMemo, useState } from "react";
import { Choice, ManwonInput, ResultBox, toWon } from "./fields";
import { compareSeller, type Industry } from "@/lib/tools/seller-vat";
import { won } from "@/lib/tools/tax";

export default function SellerVatTool() {
  const [isNew, setIsNew] = useState<"new" | "old">("old");
  const [supply, setSupply] = useState("");
  const [prev, setPrev] = useState("");
  const [months, setMonths] = useState("12");
  const [purchase, setPurchase] = useState("");
  const [industry, setIndustry] = useState<Industry>("retail");

  const res = useMemo(() => {
    if (toWon(supply) <= 0) return null;
    return compareSeller({
      isNew: isNew === "new", supply: toWon(supply), prevSupply: toWon(prev),
      openMonths: Math.min(12, Math.max(1, Number(months || 12))), purchase: toWon(purchase), industry,
    });
  }, [isNew, supply, prev, months, purchase, industry]);

  return (
    <div>
      <Choice label="사업 시작 시점" value={isNew} onChange={setIsNew} options={[{ value: "old", label: "작년 이전부터" }, { value: "new", label: "올해 개업" }]} />
      <Choice label="업종" hint="스마트스토어·쿠팡 등 온라인 소매는 '소매업'입니다." value={industry} onChange={setIndustry}
        options={[{ value: "retail", label: "소매업(온라인 판매)" }, { value: "restaurant", label: "음식점업" }, { value: "service", label: "그 밖의 서비스업" }, { value: "excluded", label: "도매·제조·부동산매매" }]} />
      <ManwonInput label={isNew === "new" ? "올해 개업 이후 판매액 합계(부가세 포함)" : "올해 1년 판매액 합계(부가세 포함)"} hint="스마트스토어 '정산금액'이 아니라 수수료를 떼기 전 '판매금액'(환불 제외)입니다." value={supply} onChange={setSupply} />
      {isNew === "new" ? (
        <div className="tf">
          <label className="tf-label">개업한 달부터 12월까지 몇 개월?</label>
          <div className="tf-hint">1개월 미만 끝수는 1개월로 셉니다. 예: 7월 개업이면 6개월.</div>
          <div className="tf-num"><input inputMode="numeric" value={months} onChange={(e) => setMonths(e.target.value.replace(/[^0-9]/g, ""))} /><span>개월</span></div>
        </div>
      ) : (
        <ManwonInput label="작년 1년 판매액 합계(부가세 포함)" hint="작년 공급대가가 1억400만원 미만이면 올해 간이과세자입니다." value={prev} onChange={setPrev} />
      )}
      <ManwonInput label="매입액(세금계산서·카드 증빙 있는 것만, 부가세 포함)" hint="상품 매입·포장·광고비 등 증빙이 있는 금액. 증빙이 없으면 넣지 마세요." value={purchase} onChange={setPurchase} />

      {res === null ? (
        <p className="cmp-sub">판매액을 입력하면 결과가 나옵니다.</p>
      ) : (
        <ResultBox tone={res.exempt ? "good" : "info"} title={res.simpleTax === null ? "간이과세는 불가능한 업종이에요" : res.exempt ? "간이과세라면 부가세 납부가 면제돼요(신고는 필요)" : res.better === "simple" ? "간이과세가 부가세가 더 적어요" : res.better === "general" ? "일반과세가 부가세가 더 적어요" : "두 유형의 부가세가 비슷해요"}>
          <p>{res.reasonSimple}</p>
          <table>
            <thead><tr><th></th><th>간이과세</th><th>일반과세</th></tr></thead>
            <tbody>
              <tr><td>부가세 납부액(연)</td><td>{res.simpleTax === null ? "해당 없음" : won(res.simpleTax)}</td><td>{res.generalTax < 0 ? `환급 ${won(-res.generalTax)}` : won(res.generalTax)}</td></tr>
            </tbody>
          </table>
          <ul>
            <li>납부면제 판단 기준 금액: {won(res.annualized)} (4,800만원 미만이면 면제, 면제여도 신고는 해야 합니다)</li>
            {res.mustIssueInvoice !== null ? <li>세금계산서 발급 의무: {res.mustIssueInvoice ? "있음" : "없음(영수증 발급)"}</li> : null}
            {res.notes.map((n, i) => <li key={i}>{n}</li>)}
          </ul>
        </ResultBox>
      )}
    </div>
  );
}
