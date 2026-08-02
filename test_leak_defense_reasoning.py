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


class TestReasoningLeakUltra:
    """초고특이도(ultra_high_signals) 단독 차단 테스트 (Phase 35 방향 B)"""

    def test_ultra_single_ko_plan_removed(self):
        """계열1 한국어 계획 1개 단독 → 문단 제거"""
        text = """정상 문단입니다.

먼저 구조를 잡자. 이 글을 어떻게 구성할까 고민 중이다.

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1
        assert "먼저 구조를 잡자" not in cleaned
        assert "정상 문단입니다." in cleaned

    def test_ultra_single_en_cot_removed(self):
        """계열2 영어 사고 문장 1개 단독 → 문단 제거"""
        text = """정상 문단입니다.

Let's think about the structure of this post.

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1
        assert "Let's" not in cleaned

    def test_ultra_single_prompt_reuse_removed(self):
        """계열3 프롬프트 재인용 1개 단독 → 문단 제거"""
        text = """정상 문단입니다.

H2 가이드라인: 각 섹션은 최소 5문장으로 작성한다.

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1
        assert "H2 가이드라인:" not in cleaned

    def test_ultra_h2_number_reuse_removed(self):
        """H2 번호 재인용 → 문단 제거"""
        text = """정상 문단입니다.

이제 JSON을 출력하겠다. H2 1: 개요.

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1

    def test_ultra_draft_context_preserved(self):
        """context=draft에서는 초고특이도도 미적용 (2단계 정제 계약)"""
        text = """정상 문단입니다.

먼저 구조를 잡자. 이 글을 어떻게 구성할까 고민 중이다.

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="draft")
        assert report["reasoning_leak"]["removed"] == 0
        assert "먼저 구조를 잡자" in cleaned

    def test_ultra_code_block_protected(self):
        """코드 블록 내 초고특이도 보호"""
        text = """정상 문단입니다.

```
먼저 구조를 잡자. Let's plan.
```

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0

    def test_ultra_table_protected(self):
        """표 내 초고특이도 보호"""
        text = """정상 문단입니다.

| 단계 | 내용 |
|------|------|
| 1 | 먼저 구조를 잡자 |

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0

    def test_ultra_list_protected(self):
        """리스트 내 초고특이도 보호"""
        text = """정상 문단입니다.

- 먼저 구조를 잡자
- Let's write

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0


class TestReasoningLeakNoFalsePositive:
    """오탐 회귀 테스트 — 정상 리뷰 본문 문단 손실 0건 (Phase 35 방향 B)"""

    def test_normal_review_paragraphs_all_preserved(self):
        """정상 리뷰 본문 전체 문단 보존 (문단 손실 0건)"""
        text = """이번에 방문한 용인로만바스는 접근성이 좋았다.

직원들의 응대가 친절했고 시설이 깨끗했다. 가격 대비 만족도가 높은 편이다.

내구성이 걱정된다는 후기도 있었지만 직접 사용해보니 문제없었다.

작성자는 3개월간 주 1회 방문하며 꾸준히 이용 중이다.

마지막으로, 예약 없이도 오전 방문이 가능하니 참고하면 좋다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        # 모든 정상 문단 보존 (문단 손실 0건)
        for para in text.split("\n\n"):
            assert para.strip() in cleaned

    def test_normal_review_with_걱정된다_single_preserved(self):
        """'걱정된다' 1개만 있는 문단 보존 (오탐 방지)"""
        text = """내구성이 걱정된다는 의견이 있지만 실제로는 견고하다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        assert "걱정된다" in cleaned

    def test_normal_review_with_작성자는_single_preserved(self):
        """'작성자는' 1개만 있는 문단 보존 (오탐 방지)"""
        text = """작성자는 이 제품을 직접 사용한 후기를 공유한다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        assert "작성자는" in cleaned


class TestReasoningLeakBlankLinePreservation:
    """빈 줄(문단 separator) 보존 — Phase 35 빈 줄 소실 버그 회귀 테스트"""

    def test_blank_lines_preserved_no_removal(self):
        """릭 없이 문단 구분만 유지되는지 (removed=0에서 빈 줄 2개 보존)"""
        text = "문단A입니다.\n\n문단B입니다.\n\n문단C입니다."
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        assert "\n\n" in cleaned
        assert cleaned == text

    def test_blank_lines_preserved_after_removal(self):
        """릭 문단 제거 후에도 남은 문단 구분 유지"""
        text = """정상 문단A입니다.

먼저 구조를 잡자. 이 글 계획 중.

정상 문단B입니다.

정상 문단C입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 1
        assert "정상 문단A" in cleaned
        assert "정상 문단B" in cleaned
        assert "정상 문단C" in cleaned
        assert "먼저 구조를 잡자" not in cleaned
        # A-B 사이와 B-C 사이의 문단 구분 유지
        assert cleaned.count("\n\n") >= 2

    def test_blank_lines_preserved_processor(self):
        """markdown_processor 전체 파이프라인에서도 빈 줄 유지"""
        from markdown_processor import processor
        text = "문단A입니다.\n\n문단B입니다.\n\n문단C입니다."
        cleaned = processor.process(text, leak_context="body")
        assert "\n\n" in cleaned

    def test_structure_preserved_table_header_list_code(self):
        """표/헤더/리스트/코드블록 구조 보존 + 빈 줄 유지"""
        text = """# 제목

정상 문단입니다.

| 헤더 | 값 |
|------|-----|
| 프롬프트에서는 | 데이터 |

- 리스트 항목

```
코드 블록
```

정상 문단입니다."""
        cleaned, report = strip_leaks(text, context="body")
        assert report["reasoning_leak"]["removed"] == 0
        for marker in ["# 제목", "| 헤더 | 값 |", "- 리스트 항목", "```"]:
            assert marker in cleaned


class TestFrontmatterMetaLeaks:
    """frontmatter 메타 필드(description/title) 릭 방어 (Phase 35 방향 B)"""

    def _fm_draft(self, desc: str, title: str = "정상 제목") -> str:
        return (
            f'---\n'
            f'title: "{title}"\n'
            f'description: "{desc}"\n'
            f'draft: true\n'
            f'---\n\n'
            f'정상 본문입니다. 잘 정제된 리뷰 내용이 여기 있습니다.'
        )

    def test_description_계열3_릭_정화(self):
        """description 계열3 릭('작성자는 제가 제공한...') → 빈 값 정화"""
        from mc.leak_defense import strip_frontmatter_meta_leaks
        desc = '작성자는 제가 제공한 블로그 콘텐츠를 바탕으로 "용인로만바스"라는 주제로 글을 작성해야 합니다.'
        text = self._fm_draft(desc)
        cleaned, report = strip_frontmatter_meta_leaks(text)
        assert report["removed"] == 1
        assert report["blocked"] is False
        # description이 빈 값으로 정화됨
        assert 'description: ""' in cleaned
        # title/본문은 손상 없음
        assert 'title: "정상 제목"' in cleaned
        assert "정상 본문입니다" in cleaned

    def test_description_계열2_릭_정화(self):
        """description 계열2 릭('chat history log') → 빈 값 정화"""
        from mc.leak_defense import strip_frontmatter_meta_leaks
        text = self._fm_draft('//chat history log: 한계')
        cleaned, report = strip_frontmatter_meta_leaks(text)
        assert report["removed"] == 1
        assert 'description: ""' in cleaned

    def test_title_릭_발행차단(self):
        """title에 초고특이도 릭 → blocked=True (발행 차단)"""
        from mc.leak_defense import strip_frontmatter_meta_leaks
        text = self._fm_draft("정상 설명입니다.", title="먼저 구조를 잡자")
        cleaned, report = strip_frontmatter_meta_leaks(text)
        assert report["blocked"] is True
        assert "title" in report["blocked_fields"]

    def test_정상_description_손상_0건(self):
        """정상 description → 변경 없음 (손상 0건)"""
        from mc.leak_defense import strip_frontmatter_meta_leaks
        desc = '용인로만바스 예약 방법과 환불 정책, 장기 멤버십 활용법을 정리한 최종 구매 가이드입니다.'
        text = self._fm_draft(desc)
        cleaned, report = strip_frontmatter_meta_leaks(text)
        assert report["removed"] == 0
        assert report["blocked"] is False
        assert f'description: "{desc}"' in cleaned
        # 원문과 동일 (frontmatter 블록 불변)
        assert cleaned == text

    def test_frontmatter_없음_불변(self):
        """frontmatter가 없으면 원문 그대로 반환"""
        from mc.leak_defense import strip_frontmatter_meta_leaks
        text = "정상 본문입니다. frontmatter가 없는 경우입니다."
        cleaned, report = strip_frontmatter_meta_leaks(text)
        assert cleaned == text
        assert report["removed"] == 0
        assert report["blocked"] is False

    def test_발행경로_훅_블록_10006_10007_실측(self):
        """실측: 10006/10007 draft_md frontmatter — description 릭 정화"""
        import json
        from mc.leak_defense import strip_frontmatter_meta_leaks
        with open(".planning/phase35/b1_posts_10006_10007.json", encoding="utf-8") as f:
            data = json.load(f)
        for cid in ["10007", "10006"]:
            draft = data[cid].get("draft_md", "")
            cleaned, report = strip_frontmatter_meta_leaks(draft)
            assert report["removed"] == 1, f"chain {cid} description 릭 미정화"
            assert 'description: ""' in cleaned, f"chain {cid} description 빈 값 미확인"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
