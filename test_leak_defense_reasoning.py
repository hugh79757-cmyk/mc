"""
reasoning_leak 문단 단위 제거 테스트 (T4)

고특이도 시그니처 2개 이상 동시 출현 시 문단 제거 검증
"""

import pytest
from mc.leak_defense import strip_leaks, _remove_reasoning_leaks_paragraph


class TestReasoningLeakParagraphRemoval:
    """문단 단위 reasoning leak 제거 테스트"""

    def test_two_high_specificity_signals_removed(self):
        """고특이도 2개 이상 동시 출현 시 문단 제거"""
        text = """정상 문단입니다.

프롬프트에서는 이렇게 작성하라고 했습니다. 피하자라는 규칙도 있습니다.

정상 문단입니다."""

        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1
        assert "프롬프트에서는" not in cleaned
        assert "피하자" not in cleaned
        assert "정상 문단입니다." in cleaned

    def test_single_high_specificity_preserved(self):
        """고특이도 1개만 있는 경우 보존"""
        text = """정상 문단입니다.

프롬프트에서는 이렇게 작성하라고 했습니다.

정상 문단입니다."""

        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        assert "프롬프트에서는" in cleaned

    def test_low_specificity_only_preserved(self):
        """저특이도만 있는 경우 보존 (오탐 방지)"""
        text = """정상 문단입니다.

주의: 이것은 주의 사항입니다.

이것은 또 다른 정상 문단입니다."""

        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        assert "주의:" in cleaned

    def test_table_protection(self):
        """표/코드블록/리스트 보호 - 보호된 라인 내 시그니처는 무시"""
        text = """정상 문단입니다.

| 표 | 헤더 |
|----|------|
| 프롬프트에서는 | 데이터 |

프롬프트에서는 이렇게. 피하자.

정상 문단입니다."""

        cleaned, report = strip_leaks(text, context="body")
        # 표 안의 "프롬프트에서는"은 보호됨, 일반 문단의 "피하자"만으로는 1신호라 제거 안됨
        # 하지만 "프롬프트에서는"이 일반 문단에 있으면 제거됨
        # 이 경우 표 안의 것은 보호되므로 신호 1개로 카운트 안됨
        pass  # 복잡한 케이스는 별도 검증

    def test_code_block_protection(self):
        """코드 블록 보호"""
        text = """정상 문단입니다.

```
프롬프트에서는 이렇게 작성하라고 했습니다.
피하자
```

정상 문단입니다."""

        cleaned, report = strip_leaks(text, context="body")
        # 코드 블록은 보호되어야 함
        assert report["reasoning_leak"]["removed"] == 0

    def test_header_protection(self):
        """헤더 보호"""
        text = """# 프롬프트에서는 이렇게

정상 문단입니다.

피하자 규칙이 있습니다.

정상 문단."""
        # 헤더는 protected로 처리되어야 함
        pass

    def test_context_draft_no_trigger(self):
        """context=draft에서는 reasoning_leak 미적용"""
        text = """프롬프트에서는 이렇게 작성하라고 했습니다. 피하자."""
        cleaned, report = strip_leaks(text, context="draft")
        # draft에서는 reasoning_leak 미적용
        assert report["reasoning_leak"]["removed"] == 0

    def test_context_test_triggers(self):
        """context=test에서는 적용"""
        text = "프롬프트에서는 이렇게 작성하라고 했습니다. 피하자."
        cleaned, report = strip_leaks(text, context="test")
        assert report["reasoning_leak"]["removed"] == 1

    def test_two_signals_different_types(self):
        """서로 다른 고특이도 2개 (프롬프트에서는 + 이미지 플레이스홀더)"""
        text = """정상 문단입니다.

프롬프트에서는 이렇게 작성하세요. 이미지 플레이스홀더를 넣으세요.

정상 문단."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1

    def test_multiple_paragraphs_mixed(self):
        """여러 문단 중 일부만 제거"""
        text = """첫 번째 정상 문단.

프롬프트에서는 이렇게. 피하자.

두 번째 정상 문단.

이미지 플레이스홀더를 넣으세요. 금지어: 주의.

세 번째 정상 문단."""
        cleaned, report = strip_leaks(text, context="body")
        # 첫 번째 의심 문단(2신호) 제거, 두 번째(2신호) 제거
        assert report["reasoning_leak"]["removed"] == 2
        assert "첫 번째 정상 문단" in cleaned
        assert "세 번째 정상 문단" in cleaned


class TestReasoningLeakDirect:
    """_remove_reasoning_leaks_paragraph 직접 테스트"""

    def test_min_signals_1_no_removal(self):
        """min_signals=1이면 1개만 있어도 제거 (설정 변경 시)"""
        # 현재 설정은 min_signals=2이므로 이 테스트는 설정 변경 시 검증용
        pass

    def test_empty_text(self):
        """빈 텍스트 처리"""
        cleaned, report = _remove_reasoning_leaks_paragraph("")
        assert report["removed"] == 0
        assert cleaned == ""

    def test_frontmatter_preserved(self):
        """frontmatter 보존"""
        text = """---
title: 테스트
---

프롬프트에서는 이렇게. 피하자."""
        cleaned, report = _remove_reasoning_leaks_paragraph(text)
        assert "title: 테스트" in cleaned
        # frontmatter 뒤 문단은 제거되어야 함
        assert report["removed"] == 1


class TestReasoningLeakEdgeCases:
    """엣지 케이스"""

    def test_high_specificity_3_signals(self):
        """3개 시그니처"""
        text = """정상.

프롬프트에서는 이렇게. 피하자. 금지어: 없음.

정상."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1

    def test_code_block_with_signals(self):
        """코드 블록 내부 시그니처 무시"""
        text = """정상.

```
프롬프트에서는 이렇게. 피하자.
```

정상."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0

    def test_table_with_signals(self):
        """표 내부 시그니처 보호"""
        text = """정상.

| 컬럼 | 값 |
|------|------|
| 프롬프트에서는 | 데이터 |

정상."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0

    def test_list_with_signals(self):
        """리스트 내부 시그니처 보호"""
        text = """정상.

- 프롬프트에서는 이렇게
- 피하자 규칙

정상."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
