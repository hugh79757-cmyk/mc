"""
test_constants.py — constants 모듈 단위 테스트 (Phase 26, Plan 01-03)

모든 기대 상수가 존재하고 올바른 값을 가지는지 검증한다.
"""


class TestAuthorityConstants:
    def test_authority_government(self):
        from constants import AUTHORITY_GOVERNMENT

        assert AUTHORITY_GOVERNMENT == (".go.kr", ".or.kr", ".gov.kr")

    def test_authority_platforms(self):
        from constants import AUTHORITY_PLATFORMS

        assert AUTHORITY_PLATFORMS["place.naver.com"] == "네이버 플레이스"
        assert AUTHORITY_PLATFORMS["instagram.com"] == "인스타그램"
        assert "map.naver.com" in AUTHORITY_PLATFORMS
        assert "map.kakao.com" in AUTHORITY_PLATFORMS
        assert "facebook.com" in AUTHORITY_PLATFORMS

    def test_skip_domains(self):
        from constants import SKIP_DOMAINS

        for d in ("naver.com", "blog.naver.com", "tistory.com",
                  "medium.com", "youtube.com", "wikipedia.org"):
            assert d in SKIP_DOMAINS

    def test_skip_paths(self):
        from constants import SKIP_PATHS

        for p in ("/board/", "/faq", "/bbs/", "/terms/"):
            assert p in SKIP_PATHS

    def test_authority_domains_union(self):
        """AUTHORITY_DOMAINS = 정부 접미사 + 플랫폼 도메인."""
        from constants import AUTHORITY_DOMAINS, AUTHORITY_GOVERNMENT, AUTHORITY_PLATFORMS

        expected = AUTHORITY_GOVERNMENT + tuple(AUTHORITY_PLATFORMS.keys())
        assert AUTHORITY_DOMAINS == expected
        assert ".go.kr" in AUTHORITY_DOMAINS
        assert "place.naver.com" in AUTHORITY_DOMAINS


class TestRegexConstants:
    def test_url_pattern_matches_http(self):
        from constants import URL_PATTERN

        m = URL_PATTERN.search("본문 링크 https://example.com/a?b=1 참고")
        assert m is not None
        assert m.group().startswith("https://example.com")

    def test_url_pattern_ignores_markdown_chars(self):
        from constants import URL_PATTERN

        # 닫는 괄호/따옴표/<> 는 URL 에 포함하지 않는다
        m = URL_PATTERN.search("(https://example.com/a)")
        assert m is not None
        assert m.group() == "https://example.com/a"

    def test_email_pattern(self):
        from constants import EMAIL_PATTERN

        assert EMAIL_PATTERN.search("contact@example.com") is not None
        assert EMAIL_PATTERN.search("no email here") is None

    def test_html_tag_re(self):
        from constants import HTML_TAG_RE

        assert HTML_TAG_RE.search('<div class="x">') is not None
        assert HTML_TAG_RE.search('<span>text</span>') is not None
        assert HTML_TAG_RE.search('<b>bold</b>') is None  # 허용 태그 목록 밖

    def test_r2_image_domains(self):
        from constants import R2_IMAGE_DOMAINS

        assert R2_IMAGE_DOMAINS == ("r2.dev", "img.")


class TestLeakConstants:
    def test_leak_patterns_are_strings(self):
        from constants import LEAK_PATTERNS

        assert isinstance(LEAK_PATTERNS, list)
        assert len(LEAK_PATTERNS) > 0
        assert all(isinstance(p, str) for p in LEAK_PATTERNS)

    def test_leak_regex_are_compiled(self):
        from constants import LEAK_REGEX

        assert isinstance(LEAK_REGEX, list)
        assert len(LEAK_REGEX) > 0
        assert all(hasattr(r, "search") for r in LEAK_REGEX)

    def test_no_sensitive_info(self):
        """T-26-06: 상수에 API 키/시크릿이 없어야 한다."""
        import re
        import constants

        source = open(constants.__file__, encoding="utf-8").read()
        for secret_key in ("api_key", "secret", "password", "token"):
            # 값 대입 (예: "api_key = ...") 이 아니라 설명 문구만 있는지 확인
            assert not re.search(rf'^\s*{secret_key}\s*=\s*["\']', source, re.MULTILINE), \
                f"constants.py 에 {secret_key} 리터럴 대입이 존재합니다"


class TestCardInjectorIntegration:
    def test_card_injector_constants_match(self):
        """chain_card_injector 의 상수가 constants 와 동일 객체인지."""
        import chain_card_injector
        import constants

        # AUTHORITY_GOVERNMENT: chain_card_injector에서 더 이상 import하지 않음 (Phase 31 — 공공기관 분기 제거)
        assert chain_card_injector.AUTHORITY_PLATFORMS is constants.AUTHORITY_PLATFORMS
        assert chain_card_injector.SKIP_DOMAINS is constants.SKIP_DOMAINS
        assert chain_card_injector.SKIP_PATHS is constants.SKIP_PATHS
