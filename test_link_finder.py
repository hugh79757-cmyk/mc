"""
test_link_finder.py — LinkFinder 단위 테스트 (Phase 26, Plan 02-01)

HTML 앵커 / 마크다운 링크 / bare URL 추출, 정규화(트래킹 파라미터 제거,
fragment 제거, scheme 소문자화), 중복 제거, 입력 가드(T-26-10/T-26-11)를
커버한다.
"""

import pytest

from link_finder import DEFAULT_MAX_INPUT_CHARS, LinkFinder


@pytest.fixture
def lf() -> LinkFinder:
    return LinkFinder()


# ── bare URL ─────────────────────────────────────────────────────────

class TestBareURLs:
    def test_plain_http_url(self, lf):
        links = lf.find_links("Test http://example.com")
        assert len(links) == 1
        link = links[0]
        assert link["url"] == "http://example.com"
        assert link["raw_url"] == "http://example.com"
        assert link["kind"] == "bare"
        assert link["position"] == 5
        assert link["end"] == 23

    def test_https_url(self, lf):
        links = lf.find_links("Visit https://example.com now")
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com"
        assert links[0]["position"] == 6

    def test_uppercase_scheme_normalized(self, lf):
        links = lf.find_links("HTTP://Example.COM/Path?Q=1")
        assert len(links) == 1
        assert links[0]["url"] == "http://example.com/Path?Q=1"

    def test_multiple_links_sorted_by_position(self, lf):
        links = lf.find_links("a http://a.com b https://b.com c")
        assert len(links) == 2
        assert [l["url"] for l in links] == ["http://a.com", "https://b.com"]
        assert [l["position"] for l in links] == [2, 17]

    def test_query_params_preserved(self, lf):
        links = lf.find_links("https://example.com/search?q=test&page=2")
        assert links[0]["url"] == "https://example.com/search?q=test&page=2"

    def test_tracking_params_stripped(self, lf):
        links = lf.find_links("https://example.com/page?utm_source=news&id=1&utm_medium=email")
        assert links[0]["url"] == "https://example.com/page?id=1"

    def test_fragment_stripped(self, lf):
        links = lf.find_links("https://example.com/page#section")
        assert links[0]["url"] == "https://example.com/page"

    def test_trailing_period_trimmed(self, lf):
        links = lf.find_links("See https://example.com.")
        assert links[0]["url"] == "https://example.com"
        assert links[0]["end"] == 23

    def test_trailing_comma_trimmed(self, lf):
        links = lf.find_links("a, https://example.com, b")
        assert links[0]["url"] == "https://example.com"

    def test_snippet_context_includes_surroundings(self, lf):
        links = lf.find_links("앞부분입니다 여기 https://example.com 뒤부분이에요")
        assert "https://example.com" in links[0]["text"]
        assert "앞부분입니다" in links[0]["text"]

    def test_unicode_path_preserved(self, lf):
        links = lf.find_links("https://example.com/한국어-페이지")
        assert links[0]["url"] == "https://example.com/한국어-페이지"

    def test_punycode_domain_preserved(self, lf):
        links = lf.find_links("https://xn--hq1bm8jm9l.xn--3e0b707e/")
        assert links[0]["url"] == "https://xn--hq1bm8jm9l.xn--3e0b707e/"

    def test_unicode_domain_preserved(self, lf):
        links = lf.find_links("https://한국.kr/")
        assert links[0]["url"] == "https://한국.kr/"

    def test_no_scheme_url_not_extracted(self, lf):
        assert lf.find_links("Visit www.example.com now") == []


# ── markdown 링크 ────────────────────────────────────────────────────

class TestMarkdownLinks:
    def test_simple_markdown_link(self, lf):
        links = lf.find_links("[t](https://x.com)")
        assert len(links) == 1
        link = links[0]
        assert link["url"] == "https://x.com"
        assert link["text"] == "t"
        assert link["kind"] == "markdown"
        assert link["position"] == 4
        assert link["end"] == 17

    def test_korean_anchor_text(self, lf):
        links = lf.find_links("[공식 사이트](https://www.gov.kr)")
        assert links[0]["url"] == "https://www.gov.kr"
        assert links[0]["text"] == "공식 사이트"

    def test_uppercase_markdown_scheme(self, lf):
        links = lf.find_links("[t](HTTPS://x.com)")
        assert links[0]["url"] == "https://x.com"

    def test_relative_markdown_url_skipped(self, lf):
        assert lf.find_links("[text](/relative/path)") == []
        assert lf.find_links("[text](page.md)") == []

    def test_multiline_anchor_text_collapsed(self, lf):
        links = lf.find_links("[multi\nline](https://x.com)")
        assert links[0]["text"] == "multi line"

    def test_markdown_inside_html_anchor_skipped(self, lf):
        links = lf.find_links('<a href="https://a.com">[t](https://b.com)</a>')
        assert len(links) == 1
        assert links[0]["url"] == "https://a.com"
        assert links[0]["kind"] == "html"


# ── HTML 앵커 ────────────────────────────────────────────────────────

class TestHTMLLinks:
    def test_simple_anchor(self, lf):
        links = lf.find_links('<a href="https://example.com">click here</a>')
        assert len(links) == 1
        link = links[0]
        assert link["url"] == "https://example.com"
        assert link["text"] == "click here"
        assert link["kind"] == "html"
        assert link["position"] == 9
        assert link["end"] == 28

    def test_single_quoted_href(self, lf):
        links = lf.find_links("<a href='https://example.com'>x</a>")
        assert links[0]["url"] == "https://example.com"

    def test_unquoted_href(self, lf):
        links = lf.find_links("<a href=https://example.com>x</a>")
        assert links[0]["url"] == "https://example.com"

    def test_anchor_with_attributes(self, lf):
        links = lf.find_links(
            '<a href="https://example.com" target="_blank" rel="noopener">링크</a>'
        )
        assert links[0]["url"] == "https://example.com"
        assert links[0]["text"] == "링크"

    def test_nested_tags_in_anchor_text(self, lf):
        links = lf.find_links('<a href="https://x.com"><b>bold</b> link</a>')
        assert links[0]["text"] == "bold link"

    def test_entity_escaped_href_unescaped(self, lf):
        links = lf.find_links('<a href="https://x.com/?a=1&amp;b=2">x</a>')
        assert links[0]["url"] == "https://x.com/?a=1&b=2"

    def test_protocol_relative_href_resolved_to_https(self, lf):
        links = lf.find_links('<a href="//example.com/x">rel</a>')
        assert links[0]["url"] == "https://example.com/x"

    def test_relative_html_href_skipped(self, lf):
        assert lf.find_links('<a href="/relative/path">x</a>') == []
        assert lf.find_links('<a href="#anchor">x</a>') == []

    def test_data_href_not_matched(self, lf):
        assert lf.find_links('<a data-href="https://x.com">x</a>') == []

    def test_img_src_not_extracted(self, lf):
        assert lf.find_links('<img src="https://x.com/img.jpg">') == []

    def test_anchor_inside_code_fence_skipped(self, lf):
        text = '```html\n<a href="https://x.com">a</a>\n```'
        assert lf.find_links(text) == []


# ── 중복 제거 ────────────────────────────────────────────────────────

class TestDedup:
    def test_dedupe_by_default(self, lf):
        links = lf.find_links("https://x.com first https://x.com second")
        assert len(links) == 1
        assert links[0]["url"] == "https://x.com"

    def test_dedupe_disabled_keeps_duplicates(self):
        lf = LinkFinder(dedupe=False)
        links = lf.find_links("https://x.com first https://x.com second")
        assert len(links) == 2

    def test_anchor_and_bare_same_url_not_duplicated(self, lf):
        links = lf.find_links('<a href="https://x.com">https://x.com</a>')
        assert len(links) == 1
        assert links[0]["kind"] == "html"

    def test_markdown_and_bare_same_url_not_duplicated(self, lf):
        links = lf.find_links("[https://x.com](https://x.com)")
        assert len(links) == 1
        assert links[0]["kind"] == "markdown"


# ── 경계/예외 ────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_text(self, lf):
        assert lf.find_links("") == []

    def test_no_links(self, lf):
        assert lf.find_links("링크가 없는 평범한 본문입니다.") == []

    def test_malformed_bare_url(self, lf):
        assert lf.find_links("http://") == []
        assert lf.find_links("https://") == []
        assert lf.find_links("http:// spaced") == []

    def test_mixed_kinds_ordered_by_position(self, lf):
        links = lf.find_links(
            "[md](https://a.com) and <a href=\"https://b.com\">b</a> and https://c.com"
        )
        assert len(links) == 3
        assert [l["kind"] for l in links] == ["markdown", "html", "bare"]
        assert [l["url"] for l in links] == ["https://a.com", "https://b.com", "https://c.com"]

    def test_code_fence_bare_url_skipped(self, lf):
        text = "```\nhttps://x.com\n```"
        assert lf.find_links(text) == []

    def test_tilde_fence_url_skipped(self, lf):
        text = "~~~\nhttps://x.com\n~~~"
        assert lf.find_links(text) == []

    def test_url_after_fence_extracted(self, lf):
        text = "```\nhttps://x.com\n```\n\nhttps://y.com"
        links = lf.find_links(text)
        assert len(links) == 1
        assert links[0]["url"] == "https://y.com"

    def test_result_dict_keys(self, lf):
        link = lf.find_links("https://x.com")[0]
        assert set(link.keys()) == {"url", "raw_url", "text", "position", "end", "kind"}

    def test_non_string_input_raises_type_error(self, lf):
        with pytest.raises(TypeError):
            lf.find_links(None)  # type: ignore[arg-type]
        with pytest.raises(TypeError):
            lf.find_links(123)  # type: ignore[arg-type]

    def test_input_cap_exceeded_raises_value_error(self):
        lf = LinkFinder(max_input_chars=100)
        with pytest.raises(ValueError):
            lf.find_links("x" * 101)

    def test_input_within_cap_ok(self):
        lf = LinkFinder(max_input_chars=100)
        assert lf.find_links("x" * 99) == []

    def test_default_cap_is_one_megabyte(self):
        assert DEFAULT_MAX_INPUT_CHARS == 1_048_576
