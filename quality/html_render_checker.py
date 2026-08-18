from dataclasses import dataclass, field
from html.parser import HTMLParser
from quality._types import ContractSpec

_CTA_KEYWORDS = ("다음 글", "관련 글", "함께 보면", "더 알아보기", "바로가기")


@dataclass
class ParsedPage:
    title: str = ""
    h1_texts: list = field(default_factory=list)
    h2_texts: list = field(default_factory=list)
    cta_patterns: list = field(default_factory=list)
    paragraphs: list = field(default_factory=list)


@dataclass
class HtmlCheckResult:
    passed: bool = True
    violations: list = field(default_factory=list)


class _PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.h1_texts: list[str] = []
        self.h2_texts: list[str] = []
        self.paragraphs: list[str] = []
        self.cta_patterns: list[str] = []
        self._tag = ""
        self._buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        self._tag = tag
        self._buf = []

    def handle_endtag(self, tag):
        text = "".join(self._buf).strip()
        if tag == "title":
            self.title = text
        elif tag == "h1":
            self.h1_texts.append(text)
        elif tag == "h2":
            self.h2_texts.append(text)
        elif tag == "p":
            self.paragraphs.append(text)
            for kw in _CTA_KEYWORDS:
                if kw in text:
                    self.cta_patterns.append(kw)
        self._buf = []

    def handle_data(self, data):
        self._buf.append(data)


def parse_html(html_str: str) -> ParsedPage:
    parser = _PageParser()
    parser.feed(html_str)
    return ParsedPage(
        title=parser.title,
        h1_texts=parser.h1_texts,
        h2_texts=parser.h2_texts,
        cta_patterns=parser.cta_patterns,
        paragraphs=parser.paragraphs,
    )


def check_html_duplicates(html_str: str, contract: ContractSpec = None) -> HtmlCheckResult:
    if contract is None:
        contract = ContractSpec()
    page = parse_html(html_str)
    violations: list[str] = []

    title_lower = page.title.strip().lower()
    for h1 in page.h1_texts:
        if title_lower and title_lower == h1.strip().lower():
            violations.append(f"duplicate_title: {page.title}")
            break

    if len(page.cta_patterns) > contract.cta_max_count:
        violations.append(
            f"duplicate_cta: {len(page.cta_patterns)} occurrences (max {contract.cta_max_count})"
        )

    seen: dict[str, int] = {}
    for p in page.paragraphs:
        text = p.strip()
        if len(text) > 20:
            seen[text] = seen.get(text, 0) + 1
    for text, count in seen.items():
        if count >= 2:
            violations.append(f"duplicate_paragraph: '{text[:50]}...'")

    return HtmlCheckResult(passed=len(violations) == 0, violations=violations)
