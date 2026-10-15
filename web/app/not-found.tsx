import Link from "next/link";

export default function NotFound() {
  return (
    <div className="container" style={{ padding: "80px 0", textAlign: "center" }}>
      <h1 style={{ fontSize: 28 }}>페이지를 찾을 수 없습니다</h1>
      <p style={{ color: "var(--muted)" }}>
        주소가 바뀌었거나 삭제된 글일 수 있어요.
      </p>
      <p>
        <Link href="/" style={{ color: "var(--gold)", fontWeight: 700 }}>
          홈으로 돌아가기
        </Link>
      </p>
    </div>
  );
}
