"""
test_chain_drafter_constants.py — chain_drafter 상수 연동 테스트
(Phase 26, Plan 01-03/01-04)

chain_drafter 가 constants 모듈의 상수를 올바르게 노출하는지 검증한다.
"""


class TestChainDrafterConstants:
    def test_exports_authority_domains(self):
        import chain_drafter
        from constants import AUTHORITY_DOMAINS

        assert chain_drafter.AUTHORITY_DOMAINS is AUTHORITY_DOMAINS

    def test_exports_skip_domains(self):
        import chain_drafter
        from constants import SKIP_DOMAINS

        assert chain_drafter.SKIP_DOMAINS is SKIP_DOMAINS

    def test_exports_url_pattern(self):
        import chain_drafter
        from constants import URL_PATTERN

        assert chain_drafter.URL_PATTERN is URL_PATTERN

    def test_values_are_usable(self):
        """상수가 실제 판별 로직에서 사용 가능한 값인지."""
        import chain_drafter

        assert chain_drafter.SKIP_DOMAINS[0] == "naver.com"
        assert ".go.kr" in chain_drafter.AUTHORITY_DOMAINS
