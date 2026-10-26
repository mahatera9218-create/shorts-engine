"""publish_fs: 오전/오후 구간 규칙과 '검증:' 발행 게이트 (네트워크 없음)."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from content import publish_fs as pf


class SlotTest(unittest.TestCase):
    def test_slot_of(self):
        self.assertEqual(pf.slot_of(9), "s1")
        self.assertEqual(pf.slot_of(10), "s2")
        self.assertEqual(pf.slot_of(13), "s3")
        self.assertEqual(pf.slot_of(15), "s4")
        self.assertEqual(pf.slot_of(17), "s5")
        self.assertEqual(pf.slot_of(19), "s6")
        self.assertEqual(pf.slot_of(21), "s7")
        self.assertEqual(pf.slot_of(23), "s8")


    def test_slot_filled_only_same_half(self):
        with tempfile.TemporaryDirectory() as d:
            posts = Path(d)
            # 10:23 발행(s2 구간)
            (posts / "a.md").write_text("---\nslug: a\ndate: 2026-10-17T10:23:00+09:00\n---\nx", encoding="utf-8")
            with mock.patch.object(pf, "POSTS_OUT", posts):
                same_slot = datetime(2026, 10, 17, 11, 7, tzinfo=pf.KST)   # s2: 이미 찬 구간
                other_slot = datetime(2026, 10, 17, 15, 9, tzinfo=pf.KST)  # s4: 빈 구간
                other_day = datetime(2026, 10, 18, 11, 7, tzinfo=pf.KST)
                self.assertTrue(pf.slot_filled(same_slot))
                self.assertFalse(pf.slot_filled(other_slot))
                self.assertFalse(pf.slot_filled(other_day))

    def test_daily_max_is_eight(self):
        self.assertEqual(pf.daily_max(), 8)

    def test_next_draft_picks_laggard_category(self):
        # 발행수: tax 2, realty 0 → 두 카테고리 초안이 모두 대기면 realty(뒤처진 쪽)를 먼저 고른다.
        with tempfile.TemporaryDirectory() as d:
            posts = Path(d) / "posts"; posts.mkdir()
            queue = Path(d) / "queue"; queue.mkdir()
            for i in (1, 2):
                (posts / f"t{i}.md").write_text(
                    f"---\nslug: t{i}\ncategory: tax\ndate: 2026-10-26T09:00:00+09:00\n---\nx",
                    encoding="utf-8")
            (queue / "01-taxdraft.md").write_text(
                "제목: t\n슬러그: taxdraft\n분류: tax\n검증: 확인됨\n\n---\n\n본문", encoding="utf-8")
            (queue / "02-realtydraft.md").write_text(
                "제목: r\n슬러그: realtydraft\n분류: realty\n검증: 확인됨\n\n---\n\n본문", encoding="utf-8")
            with mock.patch.object(pf, "POSTS_OUT", posts), mock.patch.object(pf, "QUEUE", queue):
                f, slug = pf.next_draft(set())
                self.assertEqual(slug, "realtydraft")


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


class IndexNowTest(unittest.TestCase):
    def test_slug_urls_only_posts(self):
        from content import indexnow
        out = indexnow.slug_urls(["web/content/posts/a-b.md", "web/content/pages/about.md", "reports/x.md", "web/content/posts/c.md"])
        self.assertEqual(out, ["https://astacgroup.com/a-b", "https://astacgroup.com/c"])

    def test_find_key_requires_matching_file(self):
        from content import indexnow
        with tempfile.TemporaryDirectory() as d:
            pub = Path(d)
            k = "0123456789abcdef0123456789abcdef"
            (pub / f"{k}.txt").write_text(k, encoding="utf-8")
            (pub / "robots.txt").write_text("x", encoding="utf-8")
            with mock.patch.object(indexnow, "PUBLIC", pub):
                self.assertEqual(indexnow.find_key(), k)
            (pub / f"{k}.txt").write_text("other", encoding="utf-8")
            with mock.patch.object(indexnow, "PUBLIC", pub):
                self.assertIsNone(indexnow.find_key())
