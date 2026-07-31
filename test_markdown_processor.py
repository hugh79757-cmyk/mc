"""MarkdownProcessor (Phase 26 W4, 03-04) 테스트.

기존 단일 진실 공급원(chain_card_injector.CardInjector.fix_unclosed_fences,
mc.leak_defense.strip_leaks, chain_publisher_core._clean_markdown_symbols)과의
동작 일치(parity)와 파이프라인 순서(fix_fences → strip_leaks → clean_symbols)를 검증한다.
"""

import pytest

import markdown_processor
from markdown_processor import MarkdownProcessor
from chain_card_injector import CardInjector
from mc.leak_defense import strip_leaks as leak_strip_leaks
import chain_publisher_core


# ── 단계 1: fix_fences ──────────────────────────────────────────────────

class TestFixFences:
    def test_delegates_to_card_injector(self):
        proc = MarkdownProcessor()
        md = "본문\n```json\n{\"a\": 1}\n"
        assert proc.fix_fences(md) == CardInjector.fix_unclosed_fences(md)

    def test_unclosed_fence_gets_closed(self):
        # 기존 fix_unclosed_fences 시맨틱: 펜스 뒤 내용 있으면 ``` 추가
        assert MarkdownProcessor().fix_fences("본문\n```json\n{\"a\": 1}\n") == (
            "본문\n```json\n```\n{\"a\": 1}\n"
        )

    def test_closed_fence_untouched(self):
        md = "본문\n```json\n{\"a\": 1}\n```\n"
        assert MarkdownProcessor().fix_fences(md) == md

    def test_no_fence_untouched(self):
        md = "그냥 본문입니다."
        assert MarkdownProcessor().fix_fences(md) == md


# ── 단계 2: strip_leaks ─────────────────────────────────────────────────

class TestStripLeaks:
    def test_delegates_to_leak_defense(self):
        proc = MarkdownProcessor()
        md = "---\ntitle: t\n---\n\n# Role\n\n본문입니다.\n"
        assert proc.strip_leaks(md, context="draft") == leak_strip_leaks(md, context="draft")[0]

    def test_removes_prompt_leak_header_block(self):
        # config/leak_defense.yaml prompt_leak: "^#\\s*Role" → remove_block.
        # strip_leaks 는 frontmatter(---) 이후 본문부터 처리한다.
        md = ("---\ntitle: test\n---\n\n# Role\n\n지시사항이 여기 있습니다.\n\n"
              "## 실제 본문\n\n내용입니다.\n")
        cleaned = MarkdownProcessor().strip_leaks(md, context="draft")
        assert "# Role" not in cleaned
        assert "지시사항이 여기 있습니다." not in cleaned
        assert "내용입니다." in cleaned

    def test_removes_inline_placeholder_link(self):
        # prompt_leak: "{{.*FUNNEL_LINK.*}}" → remove_inline
        md = "---\ntitle: test\n---\n\n본문입니다.\n\n{{FUNNEL_LINK}}\n"
        cleaned = MarkdownProcessor().strip_leaks(md, context="draft")
        assert "{{FUNNEL_LINK}}" not in cleaned
        assert "본문입니다." in cleaned

    def test_returns_only_cleaned_text(self):
        out = MarkdownProcessor().strip_leaks("본문입니다.", context="draft")
        assert isinstance(out, str)
        assert not isinstance(out, tuple)


# ── 단계 3: clean_symbols (기존 _clean_markdown_symbols parity) ─────────

class TestCleanSymbols:
    @pytest.mark.parametrize("body", [
        "a|b",                                            # loose pipe escape
        "```\na|b\n```",                                  # code block 보호
        "`a|b`",                                          # inline code 보호 (미보호지만 parity)
        "| a | b |\n|---|---|",                            # table separator 보호
        "| a | b |",                                      # table data row 보호
        "<!--todo:image--> 여기 이미지 필요",                 # todo marker 보호
        "$$ x | y $$",                                    # math block 보호
        "수식 $a|b$ 입니다.",                                # inline math 보호
        "**bold",                                         # unmatched ** 제거
        "정상 **볼드** 텍스트입니다.",                        # 정상 볼드 유지
    ])
    def test_parity_with_clean_markdown_symbols(self, body):
        assert MarkdownProcessor().clean_symbols(body) == (
            chain_publisher_core._clean_markdown_symbols(body)
        )

    def test_pipe_escaped_in_plain_text(self):
        assert MarkdownProcessor().clean_symbols("가나|다라") == "가나\\|다라"


# ── 파이프라인: process ─────────────────────────────────────────────────

class TestProcess:
    def test_process_pipeline_order(self):
        # unclosed fence + 프롬프트 릭 헤더 + loose pipe 가 모두 정제됨.
        # prompt_leak remove_block 은 다음 '깨끗한' 헤더까지 블록을 통째로
        # 제거하므로, 릭 블록 뒤에 정상 헤더가 있어야 나머지가 살아남는다.
        md = ("---\ntitle: test\n---\n\n# Role\n\n지시사항입니다.\n\n"
              "## 실제 제목\n\n```json\n{\"a\": 1}\n\n본문 x|y 내용\n")
        out = MarkdownProcessor().process(md, leak_context="draft")
        assert "# Role" not in out          # 릭 블록 제거
        assert "## 실제 제목" in out          # 정상 헤더 유지
        assert "```json\n```" in out        # fence 닫힘
        assert "x\\|y" in out               # pipe 이스케이프

    def test_process_equals_manual_chain(self):
        md = "---\ntitle: test\n---\n\n```json\n{\"a\": 1}\n\n# SEO 기본 원칙\n\n본문|내용\n"
        proc = MarkdownProcessor()
        expected = proc.clean_symbols(proc.strip_leaks(proc.fix_fences(md), context="draft"))
        assert proc.process(md) == expected

    def test_sanitize_markdown_body_parity(self):
        md = "---\ntitle: test\n---\n\n```json\n{\"a\": 1}\n\n## 절대 금지\n\n본문|내용\n"
        assert chain_publisher_core._sanitize_markdown_body(md) == (
            MarkdownProcessor().process(md, leak_context="draft")
        )

    def test_clean_markdown_symbols_still_works(self):
        # 기존 함수가 위임으로 동작 유지
        assert chain_publisher_core._clean_markdown_symbols("a|b") == "a\\|b"


# ── 공유 인스턴스 ───────────────────────────────────────────────────────

class TestSingleton:
    def test_shared_processor_is_instance(self):
        assert isinstance(markdown_processor.processor, MarkdownProcessor)

    def test_shared_processor_usable(self):
        assert markdown_processor.processor.clean_symbols("a|b") == "a\\|b"
