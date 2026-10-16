import type { Metadata } from "next";
import Link from "next/link";
import { SITE_NAME } from "@/lib/wp";

// 목업(미리보기) 페이지 — 대표 디자인 확인용. 검색 노출·색인 안 함.
export const metadata: Metadata = {
  title: "세무 신고 앱 순위 (미리보기 목업)",
  robots: { index: false, follow: false },
};

// 예시 데이터 — 실제 평가 전 샘플입니다(점수·순위는 임의 예시).
const CRITERIA = ["편의성", "수수료 투명성", "환급 정확도", "고객지원", "이용자 평점"];
const APPS = [
  { name: "삼쩜삼", tag: "종합소득세 환급 특화", total: 4.4, scores: [4.6, 4.2, 4.4, 4.0, 4.5], note: "환급 조회·신고 흐름이 가장 쉬움. 수수료 구조는 미리 확인 권장.", url: "#" },
  { name: "토스 세금 서비스", tag: "앱 통합·접근성", total: 4.2, scores: [4.7, 4.3, 4.0, 4.1, 4.2], note: "기존 토스 유저에게 진입 장벽이 낮음. 복잡한 신고는 제한적.", url: "#" },
  { name: "SSEM(쏘옥)", tag: "세무사 연결형", total: 4.0, scores: [3.9, 4.1, 4.3, 4.2, 3.9], note: "세무사 검토가 필요한 케이스에 강점. 단순 환급은 과할 수 있음.", url: "#" },
  { name: "자비스 택스", tag: "사업자·프리랜서", total: 3.8, scores: [3.8, 4.0, 4.0, 3.7, 3.7], note: "경비 처리·사업소득에 유리. 단순 직장인 환급엔 기능 과함.", url: "#" },
  { name: "홈택스(국세청)", tag: "공식·무료", total: 3.6, scores: [3.2, 5.0, 4.5, 3.0, 3.3], note: "수수료 0원·가장 정확. 대신 직접 입력이라 손이 많이 감.", url: "#" },
];

export default function TaxAppsRankMockup() {
  return (
    <div className="container article">
      <div className="mock-banner">
        📋 <b>미리보기(목업)</b> — 평가 기준 확정 전 <b>예시 샘플</b>입니다. 점수·순위는 임의 예시이며, 실제 페이지에선 공개 기준·출처·제휴 표시가 붙습니다.
      </div>

      <Link href="#" className="a-cat">세금·절세</Link>
      <h1>2026 세무 신고 앱 순위 TOP 5 — 환급·편의·수수료로 비교</h1>
      <div className="byline">
        <span>{SITE_NAME}</span><span>·</span><span>2026.10.16 기준 · 매주 갱신</span>
      </div>

      <p className="rank-intro">
        종합소득세·환급 앱을 <b>편의성·수수료 투명성·환급 정확도·고객지원·이용자 평점</b> 5개 기준으로 평가해 순위를 매겼습니다.
        아래 기준과 점수는 모두 공개하며, 매주 최신 이용 동향을 반영해 갱신합니다.
        <Link href="#methodology"> 평가 방법 보기 →</Link>
      </p>

      {/* 순위 카드 */}
      <div className="rank-list">
        {APPS.map((a, i) => (
          <div key={a.name} className="rank-card">
            <div className="rank-num">{i + 1}</div>
            <div className="rank-body">
              <div className="rank-head">
                <div>
                  <div className="rank-name">{a.name}</div>
                  <div className="rank-tag">{a.tag}</div>
                </div>
                <div className="rank-score">{a.total.toFixed(1)}<span>/5</span></div>
              </div>
              <p className="rank-note">{a.note}</p>
              <a className="rank-link" href={a.url} target="_blank" rel="nofollow sponsored noopener">
                {a.name} 바로가기 ↗
              </a>
            </div>
          </div>
        ))}
      </div>

      {/* 항목별 비교표 */}
      <h2>항목별 점수 비교</h2>
      <figure className="wp-block-table">
        <table>
          <thead>
            <tr>
              <th>앱</th>
              {CRITERIA.map((c) => <th key={c}>{c}</th>)}
              <th>종합</th>
            </tr>
          </thead>
          <tbody>
            {APPS.map((a) => (
              <tr key={a.name}>
                <td><b>{a.name}</b></td>
                {a.scores.map((s, j) => <td key={j}>{s.toFixed(1)}</td>)}
                <td><b>{a.total.toFixed(1)}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      </figure>

      {/* 평가 방법 */}
      <h2 id="methodology">평가 방법 (투명 공개)</h2>
      <ul>
        <li><b>기준·가중치</b>: 편의성 25% · 수수료 투명성 25% · 환급 정확도 25% · 고객지원 15% · 이용자 평점 10%.</li>
        <li><b>자료</b>: 각 앱의 공개된 수수료·기능·약관, 앱스토어 평점, 공신력 있는 이용 후기(공개 자료)만 사용.</li>
        <li><b>갱신</b>: 매주 1회, 최신 이용 동향(검색·언급 추세)을 반영해 점수 재계산.</li>
        <li><b>독립성</b>: 순위는 위 기준으로만 매깁니다. 제휴·광고가 순위에 영향을 주지 않으며, 제휴 링크·광고는 <b>'광고'로 분리 표시</b>합니다.</li>
      </ul>

      <div className="byline-foot">
        이 글은 일반 정보 제공이며 특정 서비스 가입을 권유하지 않습니다. 수수료·혜택은 바뀔 수 있으니 이용 전 각 앱에서 확인하세요.
        일부 바로가기는 제휴 링크일 수 있으며, 그 경우 명확히 표시합니다.
      </div>
    </div>
  );
}
