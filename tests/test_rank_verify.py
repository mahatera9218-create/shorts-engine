from content.rank_verify import verify

EV = {"type": "auto", "source": "s", "label": "l", "checked": "2026-10-17"}
CRIT = [{"key": "a", "name": "A", "weight": 60}, {"key": "b", "name": "B", "weight": 40}]


def _d(**kw):
    d = {"beta": True, "criteria": CRIT, "apps": [{"slug": "x", "url": "https://x.kr", "scores": {"a": 4, "b": 3}, "evidence": {"a": EV, "b": EV}}]}
    d.update(kw)
    return d


def test_beta_structure_ok():
    assert verify(_d()) == []


def test_weight_sum_must_be_100():
    assert verify(_d(criteria=[{"key": "a", "name": "A", "weight": 50}]))


def test_score_range_and_missing():
    bad = _d(apps=[{"slug": "x", "url": "#", "scores": {"a": 9}, "evidence": {"a": EV}}])
    errs = verify(bad)
    assert any("0~5" in e for e in errs)


def test_public_requires_verified_and_sources():
    errs = verify(_d(beta=False))
    assert any("verified" in e for e in errs) and any("sources" in e for e in errs)
    ok = _d(beta=False, status="verified")
    ok["apps"][0]["sources"] = ["https://example.kr/a"]
    assert verify(ok) == []


def test_pending_cannot_be_public():
    d = _d(beta=False, status="verified", apps=[{"slug": "p", "url": "#", "pending": True}])
    assert any("평가 대기" in e for e in verify(d))


def test_valid_new_topics_filters():
    from content.wp_write import valid_new_topics
    raw = [
        {"slug": "good-one", "cat": "tax", "topic": "충분히 긴 한글 주제 설명입니다"},
        {"slug": "good-one", "cat": "tax", "topic": "중복 slug는 제외되어야 한다고요"},
        {"slug": "Bad_Slug", "cat": "tax", "topic": "형식이 틀린 slug 주제입니다 정말"},
        {"slug": "known-x", "cat": "tax", "topic": "기존에 있는 slug 주제입니다 정말"},
        {"slug": "bad-cat", "cat": "stock", "topic": "허용되지 않은 분류 주제입니다 정말"},
        {"slug": "short", "cat": "tax", "topic": "짧음"},
    ]
    out = valid_new_topics(raw, {"known-x"})
    assert [t["slug"] for t in out] == ["good-one"]


def test_link_regex_matches_markdown_and_html():
    from content.link_check import LINK
    assert LINK.findall("[a](/foo-bar) and <a href=\"/baz-1\">x</a> [c](/p/about) [d](https://x.kr/no)") == ["foo-bar", "baz-1", "about"]


def test_every_score_needs_evidence_and_manual_needs_link():
    d = _d(apps=[{"slug": "x", "url": "#", "scores": {"a": 4, "b": 3}, "evidence": {"a": EV}}])
    assert any("근거" in e for e in verify(d))
    man = dict(EV, type="manual")
    d2 = _d(apps=[{"slug": "x", "url": "#", "scores": {"a": 4}, "evidence": {"a": man}}])
    assert any("https" in e for e in verify(d2))
    d3 = _d(apps=[{"slug": "x", "url": "#", "scores": {"a": 4}, "evidence": {"a": dict(man, url="https://a.kr/p")}}])
    assert verify(d3) == []


def test_rank_metrics_scoring_and_apple_pick():
    from content.rank_metrics import volume_to_score, interest_to_score, rating_to_score, pick_apple_result
    assert volume_to_score(50) == 0 and volume_to_score(10_000) == 2.5 and volume_to_score(1_000_000) == 5.0
    assert interest_to_score([100, 100, 100]) is None and interest_to_score([50, 50, 50, 50]) == 2.5
    assert rating_to_score(4.6, 999) is None and rating_to_score(4.64, 5000) == 4.6 and rating_to_score(None, 5000) is None
    res = [{"trackName": "다른 앱", "sellerName": "x"}, {"trackName": "삼쩜삼 - 세금 환급", "sellerName": "(주)자비스앤빌런즈"}]
    assert pick_apple_result(res, "삼쩜삼", "자비스")["sellerName"] == "(주)자비스앤빌런즈"
    assert pick_apple_result(res, "삼쩜삼", "토스") is None
