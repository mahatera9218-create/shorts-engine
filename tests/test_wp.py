"""content.wp: 초안 파싱과 마크다운→HTML 변환 검사 (네트워크 없음)."""
import tempfile
import unittest
from pathlib import Path

from content import wp


class WpTest(unittest.TestCase):
    def test_parse_draft(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "draft.md"
            p.write_text("제목: 테스트 제목\n\n---\n\n첫 문단입니다.\n\n## 소제목\n본문.\n",
                         encoding="utf-8")
            title, body = wp.parse_draft(p)
            assert title == "테스트 제목"
            assert body.startswith("첫 문단입니다.")
            assert "## 소제목" in body
            assert not body.startswith("---")

    def test_md_to_html_headings_and_paragraph(self):
        out = wp.md_to_html("첫 문단.\n\n## 소제목\n둘째 문단.")
        assert "<p>첫 문단.</p>" in out
        assert "<h2>소제목</h2>" in out
        assert "<p>둘째 문단.</p>" in out

    def test_md_to_html_table(self):
        md = "| 과세표준 | 세율 |\n|---|---|\n| 1,400만원 이하 | 6% |\n| 10억원 초과 | 45% |"
        out = wp.md_to_html(md)
        assert "<table>" in out
        assert "<th>과세표준</th>" in out
        assert "<td>1,400만원 이하</td>" in out
        assert "<td>45%</td>" in out
        assert "<td>---</td>" not in out  # 구분선 줄은 데이터 행으로 새지 않는다

    def test_md_to_html_list_and_bold(self):
        md = "1. 첫째\n2. 둘째\n\n- 하나\n- 둘\n\n**굵게** 강조."
        out = wp.md_to_html(md)
        assert "<ol><li>첫째</li><li>둘째</li></ol>" in out
        assert "<ul><li>하나</li><li>둘</li></ul>" in out
        assert "<strong>굵게</strong>" in out

    def test_inline_escapes_html(self):
        out = wp.md_to_html("태그 <b>는</b> 그대로 안 나와야 한다 & 처리.")
        assert "&lt;b&gt;" in out
        assert "&amp;" in out

    def test_parse_real_draft(self):
        draft = wp.ROOT / "reports" / "구글글-초안" / "01-소득세율표.md"
        if not draft.exists():
            self.skipTest("초안 없음")
        title, body = wp.parse_draft(draft)
        assert "소득세율표" in title
        out = wp.md_to_html(body)
        assert "<table>" in out
        assert "<h2>" in out


if __name__ == "__main__":
    unittest.main()
