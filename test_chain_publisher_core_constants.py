"""
test_chain_publisher_core_constants.py — chain_publisher_core 상수 연동 테스트
(Phase 26, Plan 01-03/01-04)

chain_publisher_core 가 constants 모듈의 상수를 올바르게 노출하는지 검증한다.
"""


class TestChainPublisherCoreConstants:
    def test_exports_authority_domains(self):
        import chain_publisher_core
        from constants import AUTHORITY_DOMAINS

        assert chain_publisher_core.AUTHORITY_DOMAINS is AUTHORITY_DOMAINS

    def test_exports_skip_domains(self):
        import chain_publisher_core
        from constants import SKIP_DOMAINS

        assert chain_publisher_core.SKIP_DOMAINS is SKIP_DOMAINS

    def test_exports_html_tag_re(self):
        """HTML_TAG_RE 가 constants 와 동일 객체이며 검증 로직에 사용 가능."""
        import chain_publisher_core
        from constants import HTML_TAG_RE

        assert chain_publisher_core.HTML_TAG_RE is HTML_TAG_RE
        assert chain_publisher_core.HTML_TAG_RE.search("<script>") is not None

    def test_exports_r2_image_domains(self):
        import chain_publisher_core
        from constants import R2_IMAGE_DOMAINS

        assert chain_publisher_core.R2_IMAGE_DOMAINS is R2_IMAGE_DOMAINS

    def test_html_tag_re_still_guards_extract_clean_body(self):
        """_extract_clean_body 의 HTML 태그 거부 동작이 유지되는지."""
        from chain_publisher_core import _extract_clean_body

        result = _extract_clean_body("<div>raw html</div>\n\n## 제목\n\n본문")
        assert "<div>" not in result.body
        assert "## 제목" in result.body
