from quality.html_render_checker import parse_html, check_html_duplicates
from quality._types import ContractSpec


class TestParseHtml:
    def test_extracts_title(self):
        page = parse_html("<html><head><title>Test Title</title></head><body></body></html>")
        assert page.title == "Test Title"

    def test_extracts_h1(self):
        page = parse_html("<html><body><h1>Main Heading</h1></body></html>")
        assert "Main Heading" in page.h1_texts

    def test_extracts_h2(self):
        page = parse_html("<html><body><h2>Section 1</h2><h2>Section 2</h2></body></html>")
        assert len(page.h2_texts) == 2

    def test_extracts_paragraphs(self):
        page = parse_html("<html><body><p>First paragraph.</p><p>Second paragraph.</p></body></html>")
        assert len(page.paragraphs) == 2

    def test_detects_cta_patterns(self):
        html = "<html><body><p>다음 글도 확인해보세요</p><p>관련 글이 더 있습니다</p></body></html>"
        page = parse_html(html)
        assert len(page.cta_patterns) >= 2


class TestCheckHtmlDuplicates:
    def test_duplicate_title(self):
        html = "<html><head><title>My Post</title></head><body><h1>My Post</h1></body></html>"
        result = check_html_duplicates(html)
        assert result.passed is False
        assert any("duplicate_title" in v for v in result.violations)

    def test_no_duplicate_title(self):
        html = "<html><head><title>My Post</title></head><body><h1>Different Heading</h1></body></html>"
        result = check_html_duplicates(html)
        assert not any("duplicate_title" in v for v in result.violations)

    def test_duplicate_cta(self):
        cta_html = "<p>다음 글</p>" * 4
        html = f"<html><head><title>T</title></head><body><h1>H</h1>{cta_html}</body></html>"
        result = check_html_duplicates(html)
        assert result.passed is False
        assert any("duplicate_cta" in v for v in result.violations)

    def test_single_cta(self):
        html = "<html><head><title>T</title></head><body><h1>H</h1><p>다음 글</p></body></html>"
        result = check_html_duplicates(html)
        assert not any("duplicate_cta" in v for v in result.violations)

    def test_duplicate_paragraph(self):
        para = "<p>This is a long enough paragraph that should be detected as duplicate text.</p>"
        html = f"<html><head><title>T</title></head><body><h1>H</h1>{para}{para}</body></html>"
        result = check_html_duplicates(html)
        assert result.passed is False
        assert any("duplicate_paragraph" in v for v in result.violations)

    def test_clean_html(self):
        html = """<html><head><title>Good Post</title></head><body>
<h1>Different Title</h1>
<h2>Section 1</h2>
<p>This is unique content for section one.</p>
<h2>Section 2</h2>
<p>This is unique content for section two.</p>
<p>다음 글도 보세요</p>
</body></html>"""
        result = check_html_duplicates(html)
        assert result.passed is True
        assert result.violations == []
