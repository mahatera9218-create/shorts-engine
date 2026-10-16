from content.rank_verify import verify

CRIT = [{"key": "a", "name": "A", "weight": 60}, {"key": "b", "name": "B", "weight": 40}]


def _d(**kw):
    d = {"beta": True, "criteria": CRIT, "apps": [{"slug": "x", "url": "https://x.kr", "scores": {"a": 4, "b": 3}}]}
    d.update(kw)
    return d


def test_beta_structure_ok():
    assert verify(_d()) == []


def test_weight_sum_must_be_100():
    assert verify(_d(criteria=[{"key": "a", "name": "A", "weight": 50}]))


def test_score_range_and_missing():
    bad = _d(apps=[{"slug": "x", "url": "#", "scores": {"a": 9}}])
    errs = verify(bad)
    assert any("0~5" in e for e in errs) and any("빠짐" in e for e in errs)


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
