"""
test_url_utils.py — url_utils 모듈 단위 테스트 (Phase 26, Plan 01-02)

다양한 URL 형식, 엣지 케이스, 오류 조건을 커버한다.
"""

import pytest


# ── extract_domain ──────────────────────────────────────────────────

class TestExtractDomain:
    def test_basic_http(self):
        from url_utils import extract_domain

        assert extract_domain("http://example.com/path") == "example.com"

    def test_https_with_path_and_query(self):
        from url_utils import extract_domain

        assert extract_domain("https://www.example.com/a/b?x=1#frag") == "www.example.com"

    def test_subdomain(self):
        from url_utils import extract_domain

        assert extract_domain("https://blog.naver.com/post/123") == "blog.naver.com"

    def test_port_stripped(self):
        from url_utils import extract_domain

        assert extract_domain("https://example.com:8080/path") == "example.com"

    def test_no_scheme(self):
        from url_utils import extract_domain

        assert extract_domain("example.com/path") == "example.com"

    def test_uppercase_host(self):
        from url_utils import extract_domain

        assert extract_domain("https://EXAMPLE.com/path") == "example.com"

    def test_invalid_url(self):
        from url_utils import extract_domain

        assert extract_domain("not a url at all") == ""

    def test_empty_and_none(self):
        from url_utils import extract_domain

        assert extract_domain("") == ""
        assert extract_domain(None) == ""

    def test_non_string_raises(self):
        from url_utils import extract_domain

        with pytest.raises(TypeError):
            extract_domain(12345)

    def test_oversized_input(self):
        from url_utils import extract_domain, MAX_URL_LENGTH

        huge = "https://example.com/" + "x" * (MAX_URL_LENGTH + 100)
        assert extract_domain(huge) == ""


# ── decode_idn ──────────────────────────────────────────────────────

class TestDecodeIdn:
    def test_punycode_decoded(self):
        from url_utils import decode_idn

        assert decode_idn("xn--oy2b11opse0mmca85p.kr") == "시포트리조트.kr"

    def test_plain_domain_unchanged(self):
        from url_utils import decode_idn

        assert decode_idn("example.com") == "example.com"

    def test_multi_label_partial_punycode(self):
        from url_utils import decode_idn

        assert decode_idn("xn--9t4b11yi5a.kr") == "테스트.kr"

    def test_empty(self):
        from url_utils import decode_idn

        assert decode_idn("") == ""
        assert decode_idn(None) == ""


# ── strip_tracking_params ───────────────────────────────────────────

class TestStripTrackingParams:
    def test_utm_params_removed(self):
        from url_utils import strip_tracking_params

        url = "http://example.com/path?utm_source=test&utm_medium=test"
        assert strip_tracking_params(url) == "http://example.com/path"

    def test_tracking_and_normal_params(self):
        from url_utils import strip_tracking_params

        url = "http://example.com/path?utm_source=x&id=42&fbclid=abc"
        assert strip_tracking_params(url) == "http://example.com/path?id=42"

    def test_no_tracking_params(self):
        from url_utils import strip_tracking_params

        url = "http://example.com/path?id=42&page=2"
        assert strip_tracking_params(url) == url

    def test_no_query(self):
        from url_utils import strip_tracking_params

        url = "http://example.com/path"
        assert strip_tracking_params(url) == url

    def test_empty(self):
        from url_utils import strip_tracking_params

        assert strip_tracking_params("") == ""
        assert strip_tracking_params(None) == ""

    def test_fragment_preserved(self):
        from url_utils import strip_tracking_params

        url = "http://example.com/path?utm_source=x&id=1#section"
        assert strip_tracking_params(url) == "http://example.com/path?id=1#section"

    def test_encoding_preserved(self):
        """원본 인코딩 보존: 파싱/재인코딩 하지 않음."""
        from url_utils import strip_tracking_params

        url = "http://example.com/search?q=%ED%95%9C%EA%B8%80&utm_source=x"
        assert strip_tracking_params(url) == "http://example.com/search?q=%ED%95%9C%EA%B8%80"

    def test_uppercase_tracking_keys(self):
        from url_utils import strip_tracking_params

        url = "http://example.com/path?UTM_SOURCE=x&FBclid=y"
        assert strip_tracking_params(url) == "http://example.com/path"


# ── normalize_url ───────────────────────────────────────────────────

class TestNormalizeUrl:
    def test_strips_utm(self):
        from url_utils import normalize_url

        assert normalize_url("http://example.com/path?utm_source=test") == "http://example.com/path"

    def test_strips_fragment(self):
        from url_utils import normalize_url

        assert normalize_url("http://example.com/path?x=1#section") == "http://example.com/path?x=1"

    def test_lowercases_scheme_and_host(self):
        from url_utils import normalize_url

        assert normalize_url("HTTPS://EXAMPLE.com/Path") == "https://example.com/Path"

    def test_preserves_path_case(self):
        """경로 대소문자는 보존 (대소문자 구분)."""
        from url_utils import normalize_url

        assert normalize_url("http://example.com/Path/To") == "http://example.com/Path/To"

    def test_combined(self):
        from url_utils import normalize_url

        url = "HTTP://Example.COM/a?utm_campaign=x&keep=1#frag"
        assert normalize_url(url) == "http://example.com/a?keep=1"

    def test_empty(self):
        from url_utils import normalize_url

        assert normalize_url("") == ""
        assert normalize_url(None) == ""


# ── ensure_scheme ───────────────────────────────────────────────────

class TestEnsureScheme:
    def test_adds_scheme(self):
        from url_utils import ensure_scheme

        assert ensure_scheme("example.com/path") == "https://example.com/path"

    def test_keeps_existing_scheme(self):
        from url_utils import ensure_scheme

        assert ensure_scheme("http://example.com") == "http://example.com"

    def test_custom_scheme(self):
        from url_utils import ensure_scheme

        assert ensure_scheme("example.com", scheme="http") == "http://example.com"


# ── 모듈 통합 (chain_card_injector wrapper) ─────────────────────────

class TestCardInjectorIntegration:
    def test_extract_domain_wrapper_delegates(self):
        from chain_card_injector import _extract_domain
        from url_utils import extract_domain

        assert _extract_domain("http://example.com/path") == extract_domain("http://example.com/path")
        assert _extract_domain("https://www.nhis.or.kr/menu") == "www.nhis.or.kr"

    def test_decode_idn_wrapper_delegates(self):
        from chain_card_injector import _decode_idn
        from url_utils import decode_idn

        assert _decode_idn("xn--oy2b11opse0mmca85p.kr") == decode_idn("xn--oy2b11opse0mmca85p.kr")

    def test_card_injector_exports_url_utils_names(self):
        import chain_card_injector
        import url_utils

        assert chain_card_injector.extract_domain is url_utils.extract_domain
        assert chain_card_injector.normalize_url is url_utils.normalize_url
        assert chain_card_injector.strip_tracking_params is url_utils.strip_tracking_params

    def test_image_modules_export_normalize_url(self):
        from image.prompt_builder import normalize_url as pb_norm
        from image.search_providers import normalize_url as sp_norm
        from url_utils import normalize_url

        assert pb_norm is normalize_url
        assert sp_norm is normalize_url

    def test_drafter_publisher_export_extract_domain(self):
        import chain_drafter
        import chain_publisher_core
        from url_utils import extract_domain

        assert chain_drafter.extract_domain is extract_domain
        assert chain_publisher_core.extract_domain is extract_domain
