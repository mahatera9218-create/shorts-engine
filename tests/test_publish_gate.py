"""publish_fs: 오전/오후 구간 규칙과 '검증:' 발행 게이트 (네트워크 없음)."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from content import publish_fs as pf


class SlotTest(unittest.TestCase):
    def test_slot_of(self):
        self.assertEqual(pf.slot_of(9), "am")
        self.assertEqual(pf.slot_of(11), "am")
        self.assertEqual(pf.slot_of(12), "pm")
        self.assertEqual(pf.slot_of(16), "pm")

    def test_slot_filled_only_same_half(self):
        with tempfile.TemporaryDirectory() as d:
            posts = Path(d)
            (posts / "a.md").write_text("---\nslug: a\ndate: 2026-10-17T09:20:00+09:00\n---\nx", encoding="utf-8")
            with mock.patch.object(pf, "POSTS_OUT", posts):
                am = datetime(2026, 10, 17, 10, 41, tzinfo=pf.KST)
                pm = datetime(2026, 10, 17, 15, 9, tzinfo=pf.KST)
                other_day = datetime(2026, 10, 18, 10, 41, tzinfo=pf.KST)
                self.assertTrue(pf.slot_filled(am))
                self.assertFalse(pf.slot_filled(pm))
                self.assertFalse(pf.slot_filled(other_day))

    def test_daily_max_is_two(self):
        self.assertEqual(pf.daily_max(), 2)


class VerifyGateTest(unittest.TestCase):
    def _draft(self, d, name, head):
        p = Path(d) / name
        p.write_text(head + "제목: t\n슬러그: s\n\n---\n\n본문", encoding="utf-8")
        return p

    def test_missing_header_is_unverified(self):
        with tempfile.TemporaryDirectory() as d:
            p = self._draft(d, "a.md", "")
            self.assertEqual(pf.draft_verification(p), "미확인")
            self.assertFalse(pf.is_publishable(p))

    def test_publishable_statuses(self):
        with tempfile.TemporaryDirectory() as d:
            for status, ok in [("확인됨", True), ("부분확인", True), ("미확인", False)]:
                p = self._draft(d, f"{status}.md", f"검증: {status}\n")
                self.assertEqual(pf.is_publishable(p), ok, status)


if __name__ == "__main__":
    unittest.main()


class RepublishTest(unittest.TestCase):
    def test_republish_keeps_date_and_sets_modified(self):
        with tempfile.TemporaryDirectory() as d:
            posts = Path(d) / "posts"
            posts.mkdir()
            (posts / "s.md").write_text("---\ntitle: t\nslug: s\ncategory: tax\ndate: 2026-10-16T18:10:53+09:00\nexcerpt: e\n---\n<p>old</p>\n", encoding="utf-8")
            draft = Path(d) / "01-s.md"
            draft.write_text("제목: 새 제목\n슬러그: s\n분류: tax\n검증: 부분확인\n\n---\n\n본문 새로\n", encoding="utf-8")
            with mock.patch.object(pf, "POSTS_OUT", posts):
                pf.publish_one(draft, "s")
            out = (posts / "s.md").read_text(encoding="utf-8")
            self.assertIn("date: 2026-10-16T18:10:53+09:00", out)
            self.assertIn("modified: ", out)
            self.assertIn("본문 새로", out)
