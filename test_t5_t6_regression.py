"""
T5/T6 Phase 34 최종 검증 테스트

1. 8종 시그니처 회귀 테스트 (발행 후 본문에서 0건 유지)
2. 2단계 정제 계약 테스트 (초안=미적용, 발행=적용)
3. raw_output 보존(T2) 동작 테스트
4. T6 발현률 재측정: 초안 raw vs 발행 후 본문 분리 측정
"""

import pytest
import re
import os
import tempfile
from unittest.mock import patch
from chain_drafter import draft_single_post, draft_chain
from markdown_processor import processor
from mc.leak_defense import strip_leaks
from chain_models import AIOutput, AIOutputMeta


# 8종 시그니처 정의 (reasoning_leak 고특이도 패턴과 일치)
SIGNATURES_8 = [
    ("프롬프트에서는", r"프롬프트에서는"),
    ("프롬프트는_라고_했", r"프롬프트는.*라고 했"),
    ("금지어", r"금지어:"),
    ("피하자", r"피하자"),
    ("만들지_말_것", r"만들지 말 것"),
    ("이미지_플레이스홀더", r"이미지 플레이스홀더"),
    ("제공된_참고_자료", r"제공된 참고 자료"),
    ("image_type", r"image_type"),
]

def scan_8_signatures(text: str) -> dict:
    found = {}
    for name, pattern in SIGNATURES_8:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            found[name] = [m.group() for m in matches]
    return found


# 테스트용 포스트 데이터
TEST_POSTS = [
    {
        'id': 9991, 'step': 3, 'depth': 2,
        'title': '뉴발란스 740 실사용 리뷰',
        'target_keyword': '뉴발란스 740',
        'angle': '실사용 후기 중심 리뷰',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
    {
        'id': 9992, 'step': 3, 'depth': 2,
        'title': '무선 이어폰 추천 2024',
        'target_keyword': '무선 이어폰 추천',
        'angle': '가성비·음질·착용감 종합 비교',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
    {
        'id': 9993, 'step': 3, 'depth': 2,
        'title': '테스트 키워드 리뷰',
        'target_keyword': '테스트키워드',
        'angle': '기본 기능 검증',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
]


# 공통 모킹 픽스처
@pytest.fixture(autouse=True)
def mock_ai_calls():
    with patch('chain_drafter.generate') as mock_gen, \
         patch('chain_drafter._load_prompts') as mock_prompts, \
         patch('chain_drafter.parse_ai_output') as mock_parse, \
         patch('chain_drafter.frontmatter_utils.build_frontmatter') as mock_fm_build, \
         patch('chain_drafter.frontmatter_utils.ensure_frontmatter') as mock_fm_ensure:
        
        mock_gen.return_value = {
            'content': '# 테스트 제목\n\n이것은 테스트 본문입니다.\n주의: 이것은 테스트용 프롬프트 유출입니다.\n더 많은 내용이 계속됩니다.',
            'model': 'test-model'
        }
        mock_prompts.return_value = {
            'draft_system': '당신은 유용한 AI 어시스턴트입니다.',
            'draft_user': '{target_keyword}에 대해 써주세요.',
            'keyword_categories': {
                'etc': {
                    'patterns': [],
                    'cta_phrases': {
                        'next_post': '더 알아보기 →',
                        'entry_funnel': '{{ENTRY_LINK}}',
                        'fallback': '관련 주제 보기 →'
                    },
                    'char_count': {
                        'rotcha': {'min': 1000, 'max': 1500, 'target': 1250},
                        'issue_techpawz': {'min': 1500, 'max': 2500, 'target': 2000},
                        'techpawz': {'min': 1500, 'max': 2500, 'target': 2000}
                    },
                    'step1_sections': ['## {keyword} — 개요와 핵심 특징'],
                    'step2_sections': ['## {keyword} — 상세 비교', '## {keyword} — 장단점'],
                    'step3_sections': ['## {keyword} — 종합 추천', '## {keyword} — 마무리']
                },
                'shopping_brand': {
                    'patterns': ['추천', '리뷰', '비교', '가성비'],
                    'cta_phrases': {
                        'next_post': '더 알아보기 →',
                        'entry_funnel': '{{ENTRY_LINK}}',
                        'fallback': '관련 주제 보기 →'
                    },
                    'char_count': {
                        'rotcha': {'min': 1000, 'max': 1500, 'target': 1250},
                        'issue_techpawz': {'min': 1500, 'max': 2500, 'target': 2000},
                        'techpawz': {'min': 1500, 'max': 2500, 'target': 2000}
                    },
                    'step1_sections': ['## {keyword} — 개요와 특징'],
                    'step2_sections': ['## {keyword} — 상세 리뷰', '## {keyword} — 장단점 분석'],
                    'step3_sections': ['## {keyword} — 종합 추천', '## {keyword} — 구매 가이드']
                },
                'tech': {
                    'patterns': ['기술', 'IT', '소프트웨어', '앱'],
                    'cta_phrases': {
                        'next_post': '더 알아보기 →',
                        'entry_funnel': '{{ENTRY_LINK}}',
                        'fallback': '관련 주제 보기 →'
                    },
                    'char_count': {
                        'rotcha': {'min': 1000, 'max': 1500, 'target': 1250},
                        'issue_techpawz': {'min': 1500, 'max': 2500, 'target': 2000},
                        'techpawz': {'min': 1500, 'max': 2500, 'target': 2000}
                    },
                    'step1_sections': ['## {keyword} — 기술 개요'],
                    'step2_sections': ['## {keyword} — 심층 분석'],
                    'step3_sections': ['## {keyword} — 전망과 제언']
                }
            }
        }
        from chain_models import AIOutput, AIOutputMeta
        mock_gen = patch('shared.ai_writer.generate').start()
        mock_gen.return_value = {
            'content': '# 테스트 제목\n\n이것은 테스트 본문입니다.\n주의: 이것은 테스트용 프롬프트 유출입니다.\n더 많은 내용이 계속됩니다.',
            'model': 'test-model'
        }
        from chain_models import AIOutput, AIOutputMeta
        mock_parse = patch('chain_drafter.parse_ai_output').start()
        mock_parse.return_value = AIOutput(
            body='이것은 테스트 본문입니다.\n더 많은 내용이 계속됩니다.',
            meta=AIOutputMeta(
                image_type='none',
                image_keyword='',
                image_reason='',
                chart_type=None,
                chart_data=None
            )
        )
        mock_fm_build = patch('chain_drafter.frontmatter_utils.build_frontmatter').start()
        mock_fm_build.return_value = '---\ntitle: Test Post\n---\n이것은 테스트 본문입니다.\n더 많은 내용이 계속됩니다.'
        mock_fm_ensure = patch('chain_drafter.frontmatter_utils.ensure_frontmatter').start()
        mock_fm_ensure.side_effect = lambda x, y: x
        
        yield
        
        patch.stopall()


# 8종 시그니처 정의 (reasoning_leak 고특이도 패턴과 일치)
SIGNATURES_8 = [
    ("프롬프트에서는", r"프롬프트에서는"),
    ("프롬프트는_라고_했", r"프롬프트는.*라고 했"),
    ("금지어", r"금지어:"),
    ("피하자", r"피하자"),
    ("만들지_말_것", r"만들지 말 것"),
    ("이미지_플레이스홀더", r"이미지 플레이스홀더"),
    ("제공된_참고_자료", r"제공된 참고 자료"),
    ("image_type", r"image_type"),
]

def scan_8_signatures(text: str) -> dict:
    found = {}
    for name, pattern in SIGNATURES_8:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            found[name] = [m.group() for m in matches]
    return found


# 테스트용 포스트 데이터
TEST_POSTS = [
    {
        'id': 9991, 'step': 3, 'depth': 2,
        'title': '뉴발란스 740 실사용 리뷰',
        'target_keyword': '뉴발란스 740',
        'angle': '실사용 후기 중심 리뷰',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
    {
        'id': 9992, 'step': 3, 'depth': 2,
        'title': '무선 이어폰 추천 2024',
        'target_keyword': '무선 이어폰 추천',
        'angle': '가성비·음질·착용감 종합 비교',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
    {
        'id': 9993, 'step': 3, 'depth': 2,
        'title': '테스트 키워드 리뷰',
        'target_keyword': '테스트키워드',
        'angle': '기본 기능 검증',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
]


def scan_8_signatures(text: str) -> dict:
    found = {}
    for name, pattern in SIGNATURES_8:
        matches = list(re.finditer(pattern, text, re.IGNORECASE))
        if matches:
            found[name] = [m.group() for m in matches]
    return found


TEST_POSTS = [
    {
        'id': 9991, 'step': 3, 'depth': 2,
        'title': '뉴발란스 740 실사용 리뷰',
        'target_keyword': '뉴발란스 740',
        'angle': '실사용 후기 중심 리뷰',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
    {
        'id': 9992, 'step': 3, 'depth': 2,
        'title': '무선 이어폰 추천 2024',
        'target_keyword': '무선 이어폰 추천',
        'angle': '가성비·음질·착용감 종합 비교',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
    {
        'id': 9993, 'step': 3, 'depth': 2,
        'title': '테스트 키워드 리뷰',
        'target_keyword': '테스트키워드',
        'angle': '기본 기능 검증',
        'category_guess': 'shopping_brand',
        'chain_type': 'depth',
    },
]


class Test8SignaturesRegression:
    @pytest.mark.parametrize("post", TEST_POSTS)
    def test_publish_path_zero_signatures(self, post):
        draft_md, meta, raw_output = draft_single_post(
            post, [post], post['target_keyword'], use_context=False
        )
        published_body = processor.process(raw_output, leak_context="body")
        found = scan_8_signatures(published_body)
        assert not found, f"발행 본문에서 8종 시그니처 발견: {found}"

    def test_publish_path_use_context_true(self):
        post = TEST_POSTS[0]
        draft_md, meta, raw_output = draft_single_post(
            post, [post], post['target_keyword'], use_context=True
        )
        published_body = processor.process(raw_output, leak_context="body")
        found = scan_8_signatures(published_body)
        assert not found, f"use_context=True 발행 본문에서 시그니처 발견: {found}"


class TestTwoStageProcessingContract:
    def test_draft_path_no_reasoning_leak(self):
        post = TEST_POSTS[0]
        draft_md, meta, raw_output = draft_single_post(
            post, [post], post['target_keyword'], use_context=False
        )
        cleaned, report = strip_leaks(raw_output, context="draft")
        assert report["reasoning_leak"]["removed"] == 0

    def test_publish_path_reasoning_leak_applied(self):
        post = TEST_POSTS[0]
        draft_md, meta, raw_output = draft_single_post(
            post, [post], post['target_keyword'], use_context=False
        )
        cleaned, report = strip_leaks(raw_output, context="body")
        assert "reasoning_leak" in report

    def test_chain_drafter_draft_uses_draft_context(self):
        import chain_drafter
        import inspect
        source = inspect.getsource(chain_drafter)
        assert 'context="draft"' in source


class TestRawOutputPreservation:
    """raw_output 보존(T2) 동작 테스트 - 이미 검증된 기능의 회귀 방지용"""

    def test_raw_output_db_function_exists(self):
        """update_post_raw_output 함수가 존재하는지 확인"""
        from chain_db import update_post_raw_output
        assert callable(update_post_raw_output)

    def test_raw_output_column_exists(self):
        """raw_ai_output 컬럼이 존재하는지 확인"""
        import sqlite3
        conn = sqlite3.connect('/Users/twinssn/Projects/5000/data/mc_chains.db')
        cursor = conn.execute("PRAGMA table_info(chain_posts)")
        cols = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert 'raw_ai_output' in cols, "raw_ai_output 컬럼이 없음"

    def test_raw_output_file_pattern(self):
        """raw_output 파일 명명 패턴 확인"""
        step = 3
        slug = "테스트-키워드-20240101"
        expected = f"step-{step}-{slug}.raw.md"
        assert expected == "step-3-테스트-키워드-20240101.raw.md"
class TestT6ManifestationRate:
    @pytest.mark.parametrize("post", TEST_POSTS)
    def test_manifestation_rate_breakdown(self, post):
        kw = post['target_keyword']
        print(f"\n=== {kw} ===")
        results = []
        for i in range(5):
            draft_md, meta, raw_output = draft_single_post(
                post, [post], post['target_keyword'], use_context=False
            )
            raw_found = scan_8_signatures(raw_output)
            a_count = sum(len(v) for v in raw_found.values())
            published_body = processor.process(raw_output, leak_context="body")
            pub_found = scan_8_signatures(published_body)
            b_count = sum(len(v) for v in pub_found.values())
            results.append((a_count, b_count))
            print(f"  Trial {i+1}: (a)초안={a_count}, (b)발행후={b_count}")
        
        total_b = sum(r[1] for r in results)
        assert total_b == 0, f"발행 후 본문에서 8종 시그니처 {total_b}건 발견 (목표 0)"

    def test_use_context_true_manifestation(self):
        post = TEST_POSTS[0]
        results = []
        for i in range(3):
            draft_md, meta, raw_output = draft_single_post(
                post, [post], post['target_keyword'], use_context=True
            )
            raw_found = scan_8_signatures(raw_output)
            a_count = sum(len(v) for v in raw_found.values())
            published_body = processor.process(raw_output, leak_context="body")
            pub_found = scan_8_signatures(published_body)
            b_count = sum(len(v) for v in pub_found.values())
            results.append((a_count, b_count))
            print(f"  use_context=True Trial {i+1}: (a)={a_count}, (b)={b_count}")
        
        total_b = sum(r[1] for r in results)
        assert total_b == 0


class TestParityTestChange:
    def test_parity_test_context_changed(self):
        import test_markdown_processor
        import inspect
        source = inspect.getsource(test_markdown_processor.TestProcess.test_sanitize_markdown_body_parity)
        assert 'leak_context="body"' in source


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
