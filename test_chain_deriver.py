"""Tests for chain_deriver.py - keyword classification and chain derivation."""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestClassifyKeyword:
    """키워드 성격 분류 테스트 - mc_paths.classify_keyword."""

    def test_tech_keyword_returns_tech(self):
        """기술 키워드 → tech."""
        from mc_paths import classify_keyword

        result = classify_keyword("Python 프로그래밍")
        assert result == "tech"

    def test_shopping_keyword_returns_shopping(self):
        """쇼핑 키워드 → shopping."""
        from mc_paths import classify_keyword

        result = classify_keyword("아이폰 15 구매")
        assert result == "shopping"

    def test_travel_keyword_returns_travel(self):
        """여행 키워드 → travel."""
        from mc_paths import classify_keyword

        result = classify_keyword("제주도 여행 코스")
        assert result == "travel"

    def test_issue_keyword_returns_issue(self):
        """이슈/시사 키워드 → issue."""
        from mc_paths import classify_keyword

        result = classify_keyword("기후 변화 대응 정책")
        assert result == "issue"

    def test_general_keyword_returns_general(self):
        """매핑 없는 키워드 → general."""
        from mc_paths import classify_keyword

        result = classify_keyword("알 수 없는 키워드 zyx123")
        assert result == "general"


class TestResolveChainType:
    """체인 타입 결정 테스트 - mc_paths.resolve_chain_type."""

    def test_explicit_override_overrides_classification(self):
        """override 파라미터가 키워드 분류보다 우선."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("Python", override="swallow")
        assert result == "swallow"

    def test_tech_maps_to_depth(self):
        """tech → depth (기본 매핑)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("Python 프로그래밍")
        assert result == "depth"

    def test_shopping_maps_to_swallow(self):
        """shopping → swallow (기본 매핑)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("아이폰 15 구매")
        assert result == "swallow"

    def test_travel_maps_to_lateral(self):
        """travel → lateral (기본 매핑)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("제주도 여행 코스")
        assert result == "lateral"

    def test_general_maps_to_depth(self):
        """general → depth (기본 매핑)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("일상 이야기")
        assert result == "depth"

    def test_invalid_override_falls_back_to_classification(self):
        """잘못된 override는 무시하고 분류 결과 사용."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("Python", override="INVALID")
        assert result == "depth"  # tech → depth


class TestDeriveChain:
    """derive_chain 통합 테스트."""

    @patch("chain_deriver.generate")
    @patch("chain_deriver.load_config")
    @patch("chain_deriver.load_prompts")
    @patch("chain_deriver.db.create_chain")
    @patch("chain_deriver.db.create_chain_post")
    def test_derive_chain_creates_chain_and_posts(
        self,
        mock_create_post,
        mock_create_chain,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
    ):
        """정상적인 체인 생성 흐름."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts
        mock_create_chain.return_value = 42

        mock_generate.return_value = {
            "content": json.dumps([
                {"title": "1단계: 기초", "depth": 0, "step": 1, "angle": "입문", "category_guess": "기술", "bridge_logic": "기초 설명"},
                {"title": "2단계: 심화", "depth": 1, "step": 2, "angle": "분석", "category_guess": "기술", "bridge_logic": "심화"},
                {"title": "3단계: 전문", "depth": 2, "step": 3, "angle": "고급 활용", "category_guess": "기술", "bridge_logic": "완결"},
            ]),
            "model": "test-model",
            "provider": "test",
            "tier": "default",
            "tokens_used": 100,
        }

        from chain_deriver import derive_chain
        chain_id = derive_chain("테스트 키워드", chain_type="depth")

        assert chain_id == 42
        mock_create_chain.assert_called_once()
        assert mock_create_post.call_count == 3
        first_call = mock_create_post.call_args_list[0]
        assert first_call.kwargs["chain_id"] == 42
        assert first_call.kwargs["depth"] == 0
        assert first_call.kwargs["title"] == "1단계: 기초"

    @patch("chain_deriver.generate")
    @patch("chain_deriver.load_config")
    @patch("chain_deriver.load_prompts")
    @patch("chain_deriver.db.create_chain")
    def test_derive_chain_handles_invalid_json(
        self,
        mock_create_chain,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
    ):
        """JSON 파싱 실패 시 0 반환."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts
        mock_create_chain.return_value = 1

        mock_generate.return_value = {
            "content": "not valid json",
            "model": "test-model",
        }

        from chain_deriver import derive_chain
        result = derive_chain("테스트")
        assert result == 0

    @patch("chain_deriver.generate")
    @patch("chain_deriver.load_config")
    @patch("chain_deriver.load_prompts")
    @patch("chain_deriver.db.create_chain")
    def test_derive_chain_validates_topic_count(
        self,
        mock_create_chain,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
    ):
        """토픽이 3개가 아니면 ValidationError."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts
        mock_create_chain.return_value = 1

        mock_generate.return_value = {
            "content": json.dumps({"topics": [{"title": "Only One", "depth": 0}]}),
            "model": "test-model",
        }

        from chain_deriver import _parse_derivation, derive_chain

        parsed = _parse_derivation(mock_generate.return_value["content"])
        assert parsed == []

        result = derive_chain("테스트")
        assert result == 0


class TestCLI:
    """CLI 엔트리포인트 테스트."""

    def test_cli_entry_point_module(self):
        """__main__ 블록이 derive_chain을 호출하는 구조."""
        import chain_deriver
        source = open(chain_deriver.__file__).read()
        assert "if __name__ == \"__main__\"" in source
        assert "derive_chain" in source