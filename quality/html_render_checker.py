"""HTML render checker for post-build validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser

from quality._types import ContractSpec


@dataclass
class ParsedPage:
    """Parsed HTML page structure."""
    title: str = ""
    h1: str = ""
    h2_list: list[str] = field(default_factory=list)
    cta_patterns: list[str] = field(default_factory=list)
    paragraphs: list[str] = field(default_factory=list)


@dataclass
class HtmlCheckResult:
    """Result of HTML duplicate check."""
    passed: bool
    violations: list[str] = field(default_factory=list)


class _PageParser(HTMLParser):
    """Custom HTMLParser to extract page elements."""

    def __init__(self) -> None:
        super().__init__()
        self._title = ""
        self._h1 = ""
        self._h2_list: list[str] = []
        self._cta_patterns: list[str] = []
        self._paragraphs: list[str] = []
        self._current_tag = ""
        self._capture = False
        self._buffer = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("title", "h1", "h2", "p"):
            self._current_tag = tag
            self._capture = True
            self._buffer = ""
        elif tag == "a":
            # Check for href attribute
            for attr_name, attr_value in attrs:
                if attr_name == "href" and attr_value:
                    self._cta_patterns.append(f"href:{attr_value}")

    def handle_endtag(self, tag: str) -> None:
        if tag == self._current_tag and self._capture:
            text = self._buffer.strip()
            if tag == "title":
                self._title = text
            elif tag == "h1":
                self._h1 = text
            elif tag == "h2":
                self._h2_list.append(text)
            elif tag == "p":
                self._paragraphs.append(text)
            self._capture = False
            self._current_tag = ""

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffer += data

    def get_parsed(self) -> ParsedPage:
        """Return parsed page data."""
        # Detect CTA patterns in text content
        cta_keywords = ["다음 글", "관련 글", "함께 보면"]
        for para in self._paragraphs:
            for keyword in cta_keywords:
                if keyword in para:
                    self._cta_patterns.append(keyword)

        return ParsedPage(
            title=self._title,
            h1=self._h1,
            h2_list=self._h2_list,
            cta_patterns=self._cta_patterns,
            paragraphs=self._paragraphs,
        )


def parse_html(html_str: str) -> ParsedPage:
    """Parse HTML string and extract page elements."""
    parser = _PageParser()
    parser.feed(html_str)
    return parser.get_parsed()


def check_html_duplicates(html_str: str, contract: ContractSpec) -> HtmlCheckResult:
    """Check HTML for duplicate content issues.

    Checks:
    1. title == first H1 → duplicate_title violation
    2. CTA pattern count > contract.cta_max_count → duplicate_cta violation
    3. Same paragraph text appears 2+ times → duplicate_paragraph violation
    """
    parsed = parse_html(html_str)
    violations: list[str] = []

    # Check 1: title == first H1
    if parsed.title and parsed.h1 and parsed.title == parsed.h1:
        violations.append("duplicate_title: title tag equals first H1")

    # Check 2: CTA pattern count > contract.cta_max_count
    if len(parsed.cta_patterns) > contract.cta_max_count:
        violations.append(
            f"duplicate_cta: {len(parsed.cta_patterns)} CTA patterns found "
            f"(max allowed: {contract.cta_max_count})"
        )

    # Check 3: same paragraph text appears 2+ times
    seen_paragraphs: dict[str, int] = {}
    for para in parsed.paragraphs:
        if para:  # Skip empty paragraphs
            seen_paragraphs[para] = seen_paragraphs.get(para, 0) + 1

    for para, count in seen_paragraphs.items():
        if count >= 2:
            violations.append(
                f"duplicate_paragraph: paragraph appears {count} times"
            )

    return HtmlCheckResult(
        passed=len(violations) == 0,
        violations=violations,
    )
