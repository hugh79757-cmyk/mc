"""Tests for mc/year_guard.py — 연도 오류 방지 유틸리티 (Phase 32)."""
import sys
from unittest.mock import patch

import pytest


class TestBuildAllowedYears:
    """build_allowed_years() 함수 테스트."""

    def test_default_only_current_year(self):
        """source_years 없이 호출 시 현재 연도만 포함."""
        from mc.year_guard import build_allowed_years
        from datetime import datetime

        result = build_allowed_years()
        assert datetime.now().year in result
        assert len(result) == 1

    def test_includes_source_years(self):
        """source_years 포함 시 현재 연도와 합집합."""
        from mc.year_guard import build_allowed_years
        from datetime import datetime

        result = build_allowed_years({2024, 2025})
        assert datetime.now().year in result
        assert 2024 in result
        assert 2025 in result

    def test_empty_source_years(self):
        """빈 source_years 전달 시 현재 연도만."""
        from mc.year_guard import build_allowed_years
        from datetime import datetime

        result = build_allowed_years(set())
        assert result == {datetime.now().year}


class TestValidateAndFixYears:
    """validate_and_fix_years() 함수 테스트."""

    def test_replace_year_with_context_basic(self):
        """과거연도+최신 → 현재 연도 치환."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2025 최신 정보입니다", fix_mode=True)
        assert "2026 최신 정보입니다" == text
        assert len(warns) == 1

    def test_replace_year_with_context_gijun(self):
        """과거연도+기준 → 현재 연도 치환."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2024년 기준 가격", fix_mode=True)
        assert "2026년 기준 가격" == text
        assert len(warns) == 1

    def test_replace_context_before_year(self):
        """최신+과거연도 → 현재 연도 치환 (패턴 2)."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("최신 2025년 트렌드", fix_mode=True)
        assert "최신 2026년 트렌드" == text
        assert len(warns) == 1

    def test_factual_date_protected_festival(self):
        """사실 날짜 보호: 축제 개최."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2025년 축제 개최", fix_mode=True)
        assert "2025년 축제 개최" == text
        assert len(warns) == 0

    def test_factual_date_protected_period(self):
        """사실 날짜 보호: 기간 표현."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2025년부터 적용", fix_mode=True)
        assert "2025년부터 적용" == text
        assert len(warns) == 0

    def test_factual_date_protected_month(self):
        """사실 날짜 보호: 구체적 월."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2025년 3월 개장", fix_mode=True)
        assert "2025년 3월 개장" == text
        assert len(warns) == 0

    def test_factual_date_protected_date(self):
        """사실 날짜 보호: 구체적 일."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2025년 3월 15일 행사", fix_mode=True)
        assert "2025년 3월 15일 행사" == text
        assert len(warns) == 0

    def test_standalone_year_warning(self):
        """standalone 과거 연도 → 플래그만 (치환 안 함)."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2024년 매출", fix_mode=True)
        assert "2024년 매출" == text  # 변경 없음
        assert any("2024" in w for w in warns)

    def test_allowed_year_no_warning(self):
        """허용 목록에 있는 연도 → 경고 없음."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years(
            "2026년 신규 프로그램", allowed_years={2026}, fix_mode=True
        )
        assert "2026년 신규 프로그램" == text
        assert len(warns) == 0

    def test_fix_mode_false_no_replacement(self):
        """fix_mode=False → 플래그만, 치환 없음."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("2025 최신 정보", fix_mode=False)
        assert "2025 최신 정보" == text  # 원본 유지
        assert len(warns) > 0

    def test_multiple_year_patterns(self):
        """여러 연도 패턴 혼재 시 처리."""
        from mc.year_guard import validate_and_fix_years

        text = "2025 최신 정보와 2024년 기준 가격, 그리고 2025년 축제"
        result, warns = validate_and_fix_years(text, fix_mode=True)
        # "2025 최신" → 치환, "2024년 기준" → 치환, "2025년 축제" → 보호
        assert "2026 최신" in result
        assert "2026년 기준" in result
        assert "2025년 축제" in result  # 사실 날짜 보호

    def test_current_year_unchanged(self):
        """현재 연도는 그대로 유지."""
        from mc.year_guard import validate_and_fix_years
        from datetime import datetime

        current = datetime.now().year
        text, warns = validate_and_fix_years(f"{current} 최신 정보", fix_mode=True)
        assert f"{current} 최신 정보" == text
        assert len(warns) == 0

    def test_fix_mode_false_multiple_warnings(self):
        """fix_mode=False에서 여러 경고 생성."""
        from mc.year_guard import validate_and_fix_years

        text = "2025 최신 정보와 2024년 기준"
        _, warns = validate_and_fix_years(text, fix_mode=False)
        assert len(warns) >= 2

    def test_empty_text(self):
        """빈 텍스트 처리."""
        from mc.year_guard import validate_and_fix_years

        text, warns = validate_and_fix_years("", fix_mode=True)
        assert text == ""
        assert len(warns) == 0

    def test_no_year_patterns(self):
        """연도 패턴 없는 텍스트 → 변경 없음."""
        from mc.year_guard import validate_and_fix_years

        text = "오늘 날씨가 좋습니다. 블로그 포스트를 작성합니다."
        result, warns = validate_and_fix_years(text, fix_mode=True)
        assert result == text
        assert len(warns) == 0


class TestYearGuardPatterns:
    """정규식 패턴 자체 동작 검증."""

    def test_pattern1_matches_year_context(self):
        """PATTERN_YEAR_WITH_CONTEXT 매칭 확인."""
        from mc.year_guard import PATTERN_YEAR_WITH_CONTEXT

        m = PATTERN_YEAR_WITH_CONTEXT.search("2025 최신 정보")
        assert m is not None
        assert m.group(1) == "2025"
        assert m.group(2) == "최신"

    def test_pattern2_matches_context_year(self):
        """PATTERN_CONTEXT_WITH_YEAR 매칭 확인."""
        from mc.year_guard import PATTERN_CONTEXT_WITH_YEAR

        m = PATTERN_CONTEXT_WITH_YEAR.search("기준 2024년")
        assert m is not None
        assert m.group(1) == "기준"
        assert m.group(2) == "2024"

    def test_pattern3_matches_standalone(self):
        """PATTERN_STANDALONE_YEAR 매칭 확인."""
        from mc.year_guard import PATTERN_STANDALONE_YEAR

        m = PATTERN_STANDALONE_YEAR.search("2023년 매출")
        assert m is not None
        assert m.group(1) == "2023"

    def test_factual_pattern_matches_event(self):
        """사실 날짜 패턴 매칭 확인."""
        from mc.year_guard import FACTUAL_DATE_PATTERNS
        import re

        # 첫 번째 패턴(이벤트 날짜)이 매칭되는지 확인
        assert re.search(FACTUAL_DATE_PATTERNS[0], "2025년 축제 개최")
        # 네 번째 패턴(구체적 일)이 매칭되는지 확인
        assert re.search(FACTUAL_DATE_PATTERNS[3], "2025년 3월 15일 행사")
