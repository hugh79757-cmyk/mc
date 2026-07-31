"""Phase 26 (Wave 4) 최종 검증 smoke tests — 03-05.

리팩터링(단일 진실 공급원 통합: frontmatter_utils / url_utils / constants /
markdown_processor / image providers) 이후 핵심 기능이 그대로 동작하는지
경량 스모크 테스트로 확인한다. 네트워크 호출 없음 (구조/시그니처/로컬 로직만).
"""

import pytest

# ── 1. frontmatter handling ─────────────────────────────────────────────

from frontmatter_utils import (
    ensure_frontmatter,
    ensure_frontmatter_closer,
    extract_description,
)


class TestFrontmatterHandling:
    def test_ensure_frontmatter_adds_metadata(self):
        md = ensure_frontmatter("본문 내용입니다.", {"title": "테스트 글"})
        assert md.startswith("---\n")
        assert "title:" in md.split("---")[1]
        assert "테스트 글" in md
        assert md.rstrip().endswith("본문 내용입니다.")

    def test_ensure_frontmatter_preserves_existing(self):
        original = "---\ntitle: 기존\n---\n\n본문입니다.\n"
        assert ensure_frontmatter(original, {"title": "새 제목"}) == original

    def test_ensure_frontmatter_closer(self):
        # 미닫힌 --- 를 닫는다
        md = "---\ntitle: test\n\n본문입니다.\n"
        closed = ensure_frontmatter_closer(md)
        assert "---\n" in closed.split("\n")[1] or closed.count("---") >= 2

    def test_extract_description_truncates(self):
        body = "첫 문장입니다.\n\n두 번째 문단."
        desc = extract_description(body, max_len=10)
        assert len(desc) <= 10
        assert isinstance(desc, str)


# ── 2. link detection ───────────────────────────────────────────────────

from url_utils import extract_domain, normalize_url, strip_tracking_params
from link_finder import LinkFinder


class TestLinkDetection:
    def test_extract_domain(self):
        assert extract_domain("https://example.com/path?q=1") == "example.com"

    def test_normalize_url(self):
        # scheme 없이 들어온 URL 은 그대로 정규화 대상 — 원본 형태 유지 검증
        assert normalize_url("https://Example.com/PATH") == "https://example.com/PATH"
        # 트래킹 파라미터 + fragment 제거
        assert normalize_url("https://a.com/x?utm_source=y&b=2#frag") == "https://a.com/x?b=2"

    def test_strip_tracking_params(self):
        assert strip_tracking_params("https://a.com/x?utm_source=x&b=2") == "https://a.com/x?b=2"

    def test_link_finder_finds_markdown_links(self):
        text = "본문 [네이버](https://www.naver.com) 그리고 [다음](https://daum.net) 끝"
        links = LinkFinder().find_links(text)
        assert len(links) == 2
        assert links[0]["url"] == "https://www.naver.com"
        assert "text" in links[0] and "kind" in links[0]

    def test_link_finder_ignores_fenced_code(self):
        text = "본문\n```\n[가짜](https://fake.com)\n```\n끝"
        assert LinkFinder().find_links(text) == []


# ── 3. card generation ──────────────────────────────────────────────────

from card_generator import CardGenerator
from chain_card_injector import CardInjector


class TestCardGeneration:
    def test_generate_next_card_spec(self):
        spec = CardGenerator().generate_next_card_spec("제목", "https://example.com", "더 알아보기 →")
        assert isinstance(spec, dict)
        assert spec.get("type") == "next"
        assert spec.get("title") == "제목"
        assert spec.get("url") == "https://example.com"

    def test_card_injector_fix_unclosed_fences_static(self):
        # 정적 메서드로 유지 — MarkdownProcessor 가 위임 대상으로 사용
        assert CardInjector.fix_unclosed_fences('```json\n{"a":1}\n') == (
            '```json\n```\n{"a":1}\n'
        )


# ── 4. image fetching (구조 smoke — 네트워크 호출 없음) ──────────────────

from image.search_providers import UnsplashProvider, PexelsProvider, search_body_image
from image.prompt_builder import build_contextual_prompt, build_full_prompt
from image.base_provider import BaseImageProvider


class TestImageFetching:
    def test_providers_instantiate(self):
        up = UnsplashProvider(access_key="test-key")
        pp = PexelsProvider(api_key="test-key")
        assert isinstance(up, BaseImageProvider)
        assert isinstance(pp, BaseImageProvider)

    def test_providers_expose_fetch_and_validate(self):
        up = UnsplashProvider(access_key="test-key")
        assert callable(getattr(up, "fetch"))
        assert callable(getattr(up, "validate"))
        # 빈/무효 결과는 False — 네트워크 없이 로컬 검증 로직만 확인
        assert up.validate(None) is False

    def test_legacy_search_body_image_importable(self):
        assert callable(search_body_image)

    def test_prompt_builder_functions(self):
        prompt = build_contextual_prompt(
            image_keyword="자동차 연비",
            title="자동차 연비 비교",
            blog_key="rotcha",
            post_angle="비교",
            step=1,
            chain_type="depth",
        )
        assert isinstance(prompt, str) and len(prompt) > 0
        assert callable(build_full_prompt)


# ── 5. markdown pipeline (03-04 산출물 연동) ────────────────────────────

import chain_publisher_core
from markdown_processor import MarkdownProcessor


class TestMarkdownPipelineIntegration:
    def test_sanitize_markdown_body_available(self):
        assert callable(chain_publisher_core._sanitize_markdown_body)

    def test_clean_markdown_symbols_delegates(self):
        assert chain_publisher_core._clean_markdown_symbols("a|b") == (
            MarkdownProcessor().clean_symbols("a|b")
        )
