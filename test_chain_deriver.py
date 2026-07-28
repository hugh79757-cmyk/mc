"""Tests for chain_deriver.py - keyword classification and chain derivation."""
import json
from unittest.mock import MagicMock, patch

import pytest


class TestClassifyKeyword:
    """키워드 성격 분류 테스트 - mc_paths.classify_keyword."""

    def test_tech_keyword_returns_etc(self):
        """기술 키워드 → etc (keyword_categories에 해당하는 IT 패턴 없으면 fallback)."""
        from mc_paths import classify_keyword

        result = classify_keyword("Python 프로그래밍")
        assert result == "etc"

    def test_shopping_keyword_returns_etc(self):
        """쇼핑 키워드 → etc (keyword_categories에 shopping 없음)."""
        from mc_paths import classify_keyword

        result = classify_keyword("아이폰 15 구매")
        assert result == "etc"

    def test_travel_keyword_returns_travel(self):
        """여행 키워드 → travel."""
        from mc_paths import classify_keyword

        result = classify_keyword("제주도 여행 코스")
        assert result == "travel"

    def test_issue_keyword_returns_etc(self):
        """이슈/시사 키워드 → etc (keyword_categories에 issue 없음)."""
        from mc_paths import classify_keyword

        result = classify_keyword("기후 변화 대응 정책")
        assert result == "etc"

    def test_unknown_keyword_returns_etc(self):
        """매핑 없는 키워드 → etc."""
        from mc_paths import classify_keyword

        result = classify_keyword("알 수 없는 키워드 zyx123")
        assert result == "etc"

    def test_stock_suffix_gaja_forces_stock(self):
        """~주가 키워드는 후처리로 stock 우선."""
        from mc_paths import classify_keyword

        assert classify_keyword("삼성전자주가") == "stock"
        assert classify_keyword("제주항공주가") == "stock"

    def test_travel_waterpark_expansion(self):
        """워터파크/온천 등 신규 P1 패턴."""
        from mc_paths import classify_keyword

        assert classify_keyword("서울 워터파크") == "travel"
        assert classify_keyword("강릉 온천") == "travel"
        assert classify_keyword("해수욕장 펜션") == "travel"

    def test_travel_location_expansion(self):
        """신규 지명 P2 패턴."""
        from mc_paths import classify_keyword

        assert classify_keyword("춘천 여행") == "travel"
        assert classify_keyword("담양 숙소") == "travel"
        assert classify_keyword("영덕파나크") == "travel"

    def test_travel_resort_brand_expansion(self):
        """리조트 브랜드 P3 패턴."""
        from mc_paths import classify_keyword

        assert classify_keyword("소노문해운대") == "travel"
        assert classify_keyword("한화리조트") == "travel"
        assert classify_keyword("신라스테이") == "travel"

    def test_stock_pattern_gaja_added(self):
        """주가 stock 패턴 추가."""
        from mc_paths import classify_keyword

        assert classify_keyword("삼성전자 주가") == "stock"
        assert classify_keyword("NAVER 주가") == "stock"

    def test_classification_order_and_postprocess(self):
        """travel→stock→real_estate→automotive→etc 순서 + ~주가 후처리."""
        from mc_paths import classify_keyword

        assert classify_keyword("ETF 투자") == "stock"
        assert classify_keyword("제주항공주가") == "stock"
        assert classify_keyword("소노벨 리조트") == "travel"

    def test_spa_context_pattern_excludes_spiderman(self):
        """스파$ 패턴: 정상 스파는 travel, 스파이더맨은 etc."""
        from mc_paths import classify_keyword

        assert classify_keyword("제주오레브스파") == "travel"
        assert classify_keyword("스파이더맨") == "etc"
        assert classify_keyword("스파이더맨노웨이홈") == "etc"
        assert classify_keyword("인스파이어뷔페") == "etc"

    def test_city_context_requirements(self):
        """도시명은 travel 접미사와 결합할 때만 travel."""
        from mc_paths import classify_keyword

        # false positives → etc
        assert classify_keyword("광주베이비페어") == "etc"
        assert classify_keyword("울산날씨") == "etc"
        assert classify_keyword("청주SK뷰자이") == "etc"
        assert classify_keyword("청주동일하이빌2차") == "etc"
        # valid prefix compounds → travel
        assert classify_keyword("광주호텔") == "travel"
        assert classify_keyword("울산펜션") == "travel"
        assert classify_keyword("청주리조트") == "travel"
        # valid brand+suffix compound → travel
        assert classify_keyword("홀리데이인광주") == "travel"
        # strong destination city alone → travel
        assert classify_keyword("제주") == "travel"
        assert classify_keyword("부산") == "travel"


class TestResolveChainType:
    """체인 타입 결정 테스트 - mc_paths.resolve_chain_type."""

    def test_explicit_override_overrides_classification(self):
        """override 파라미터가 키워드 분류보다 우선."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("Python", override="swallow")
        assert result == "swallow"

    def test_etc_maps_to_depth_python(self):
        """etc → depth (Python 키워드는 이제 etc 분류)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("Python 프로그래밍")
        assert result == "depth"

    def test_etc_maps_to_depth(self):
        """etc → depth (기본 매핑)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("아이폰 15 구매")
        assert result == "depth"

    def test_travel_maps_to_lateral(self):
        """travel → lateral (기본 매핑)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("제주도 여행 코스")
        assert result == "lateral"

    def test_etc_maps_to_depth_daily(self):
        """etc → depth (일반 키워드는 etc 분류)."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("일상 이야기")
        assert result == "depth"

    def test_invalid_override_falls_back_to_classification(self):
        """잘못된 override는 무시하고 분류 결과 사용."""
        from mc_paths import resolve_chain_type

        result = resolve_chain_type("Python", override="INVALID")
        assert result == "depth"  # etc → depth (fallback)


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


class TestDeriveLateralCategoryDispatch:
    """category별 lateral 프롬프트 분기 검증."""

    LATERAL_ANGLES = {
        "travel": "현장 실전과 방문 전 체크포인트",
        "real_estate": "계약 확정과 입주 완료",
        "automotive": "구매 확정과 인도 완료",
        "stock": "매수/매도 실행과 포트폴리오 관리",
        "etc": "최종 구매 확정과 장기 활용",
    }
    OLD_GENERIC_ANGLE = "산업 구조와 수익화 전망"

    @pytest.mark.parametrize("keyword,expected_category", [
        ("하이바이풀빌라", "travel"),
        ("아파트 분양", "real_estate"),
        ("전기차 추천", "automotive"),
        ("ETF 투자", "stock"),
        ("아이폰 17", "etc"),
    ])
    @patch("chain_deriver.generate")
    @patch("chain_deriver.load_config")
    @patch("chain_deriver.load_prompts")
    @patch("chain_deriver.db.create_chain")
    @patch("chain_deriver.db.create_chain_post")
    def test_lateral_category_uses_correct_angle(
        self,
        mock_create_post,
        mock_create_chain,
        mock_load_prompts,
        mock_load_config,
        mock_generate,
        sample_chain_config,
        sample_prompts,
        keyword,
        expected_category,
    ):
        """category별 lateral derive prompt에 올바른 angle 포함."""
        mock_load_config.return_value = sample_chain_config
        mock_load_prompts.return_value = sample_prompts
        mock_create_chain.return_value = 42

        mock_generate.return_value = {
            "content": json.dumps([
                {"title": "Step 1", "depth": 0, "step": 1, "angle": "기초", "category_guess": "일반", "bridge_logic": "다음"},
                {"title": "Step 2", "depth": 1, "step": 2, "angle": "비교", "category_guess": "일반", "bridge_logic": "다음"},
                {"title": "Step 3", "depth": 2, "step": 3, "angle": "실전", "category_guess": "일반", "bridge_logic": "완결"},
            ]),
            "model": "test-model",
            "provider": "test",
            "tier": "default",
            "tokens_used": 100,
        }

        from chain_deriver import derive_chain
        derive_chain(keyword, chain_type="lateral")

        # capture the user_prompt sent to generate() (keyword arg)
        user_prompt = mock_generate.call_args.kwargs["user_prompt"]

        expected_angle = self.LATERAL_ANGLES[expected_category]

        # ✅ category-specific angle must be present
        assert expected_angle in user_prompt, (
            f"[{expected_category}] '{expected_angle}' not in prompt:\n{user_prompt}"
        )

        # ❌ old generic angle must NOT be present
        assert self.OLD_GENERIC_ANGLE not in user_prompt, (
            f"[{expected_category}] Old generic angle '{self.OLD_GENERIC_ANGLE}' still present"
        )


class TestCLI:
    """CLI 엔트리포인트 테스트."""

    def test_cli_entry_point_module(self):
        """__main__ 블록이 derive_chain을 호출하는 구조."""
        import chain_deriver
        source = open(chain_deriver.__file__).read()
        assert "if __name__ == \"__main__\"" in source
        assert "derive_chain" in source


class TestGolfCoursePriority:
    """골프장 우선순위 회귀 테스트 (priority 필드 도입).

    골프장 키워드는 지역명(travel 패턴)을 포함해도 golf_course로 분류되어야 한다.
    예: '남서울CC' 의 '서울' 이 travel 지역 패턴에 걸리지만, golf_course.priority=10
    이 travel(기본 100)보다 먼저 검사되므로 golf_course 가 우선한다.
    """

    def test_golf_with_region_name_prefers_golf(self):
        from mc_paths import classify_keyword

        assert classify_keyword("남서울CC 예약") == "golf_course"
        assert classify_keyword("부산CC 그린피") == "golf_course"
        assert classify_keyword("제주 골프장") == "golf_course"
        assert classify_keyword("남서울CC 라운딩") == "golf_course"

    def test_priority_does_not_break_plain_travel(self):
        """priority 도입이 기존 travel 분류를 깨지 않는다."""
        from mc_paths import classify_keyword

        assert classify_keyword("제주도 여행 코스") == "travel"
        assert classify_keyword("서울 워터파크") == "travel"
        assert classify_keyword("한화리조트") == "travel"


class TestNewCategoryClassification:
    """신규 카테고리(customer_service/gov_finance/medicine) 분류 회귀."""

    def test_customer_service(self):
        from mc_paths import classify_keyword
        assert classify_keyword("삼성전자서비스 고객센터") == "customer_service"

    def test_gov_finance(self):
        from mc_paths import classify_keyword
        assert classify_keyword("근로장려금 신청자격") == "gov_finance"

    def test_medicine(self):
        from mc_paths import classify_keyword
        assert classify_keyword("타이레놀정 복용법") == "medicine"
        assert classify_keyword("이부프로펜 부작용") == "medicine"
        assert classify_keyword("두통 초기증상") == "medicine"
