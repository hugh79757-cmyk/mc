"""Tests for W3 카드 재설계 + 외부링크 + 이미지 프롬프트."""

import pytest


# ── 서브태스크 A: 카드 3단계 체계 ──


class TestCardThreeTier:
    """3단계 카드 체계 테스트."""

    def test_inject_cards_chain_iterates_all_posts(self):
        """inject_cards_chain이 전체 포스트를 순회해야 함 (range(len(posts)))."""
        import inspect
        from chain_publisher import inject_cards_chain
        source = inspect.getsource(inject_cards_chain)
        # range(len(posts) - 1)이 아닌 range(len(posts)) 사용 확인
        assert "range(len(posts))" in source
        assert "range(len(posts) - 1)" not in source

    def test_inject_cards_chain_handles_last_post(self):
        """마지막 포스트에 is_last=True가 전달되어야 함."""
        import inspect
        from chain_publisher import inject_cards_chain
        source = inspect.getsource(inject_cards_chain)
        assert "is_last=True" in source
        assert "is_last=False" in source

    def test_inject_cards_chain_passes_seed_keyword(self):
        """seed_keyword가 카드 주입에 전달되어야 함."""
        import inspect
        from chain_publisher import inject_cards_chain
        source = inspect.getsource(inject_cards_chain)
        assert "seed_keyword" in source

    def test_inject_cards_into_draft_is_last_param(self):
        """inject_cards_into_draft가 is_last 파라미터를 지원해야 함."""
        import inspect
        from chain_card_injector import CardInjector
        sig = inspect.signature(CardInjector.inject_cards_into_draft)
        assert "is_last" in sig.parameters
        assert "seed_keyword" in sig.parameters


# ── 서브태스크 B: 외부링크 추출 + 공신력 우선순위 ──


class TestExternalLinks:
    """외부링크 공신력 우선순위 테스트."""

    def test_find_external_links_has_api_only(self):
        """find_external_links가 API 메서드를 가지며, BS4 스크래핑 없음."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        assert hasattr(injector, "_search_via_api")
        assert not hasattr(injector, "_search_via_bs4")

    def test_classify_authority_government(self):
        """공공기관 도메인은 1순위."""
        from chain_card_injector import _classify_authority
        priority, label = _classify_authority("https://www.dhlottery.co.kr/game")
        assert priority == 1

    def test_classify_authority_whitelist(self):
        """화이트리스트 도메인은 1순위."""
        from chain_card_injector import _classify_authority
        priority, label = _classify_authority("https://www.twayair.com/booking")
        assert priority == 1
        assert "티웨이항공" in label

    def test_classify_authority_platform(self):
        """네이버 플레이스는 2순위."""
        from chain_card_injector import _classify_authority
        priority, label = _classify_authority("https://pcmap.place.naver.com/hotel/123")
        assert priority == 2
        assert "네이버" in label

    def test_classify_authority_skip_blog(self):
        """블로그/뉴스는 제외 (0)."""
        from chain_card_injector import _classify_authority
        priority, _ = _classify_authority("https://blog.naver.com/post/123")
        assert priority == 0

    def test_classify_authority_fallback(self):
        """일반 사이트는 3순위."""
        from chain_card_injector import _classify_authority
        priority, _ = _classify_authority("https://example.com/info")
        assert priority == 3

    def test_build_external_link_card_primary(self):
        """1순위 링크가 있을 때 '바로가기' 카드 생성."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        links = {
            "primary": {"url": "https://dhlottery.co.kr", "label": "동행복권", "priority": 1},
            "secondary": [],
            "fallback": {"url": "https://search.naver.com/search.naver?query=test", "label": "검색"},
        }
        html = injector.build_external_link_card(links, "로또")
        assert "dhlottery.co.kr" in html
        assert "바로가기" in html

    def test_build_external_link_card_fallback(self):
        """1순위/2순위 없을 때 fallback 카드 생성."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        links = {
            "primary": None,
            "secondary": [],
            "fallback": {"url": "https://search.naver.com/search.naver?query=test", "label": "검색"},
        }
        html = injector.build_external_link_card(links, "테스트")
        assert "search.naver.com" in html
        assert "검색" in html

    def test_build_external_link_card_mixed(self):
        """1순위 + 2순위 둘 다 있을 때."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        links = {
            "primary": {"url": "https://dhlottery.co.kr", "label": "동행복권", "priority": 1},
            "secondary": [{"url": "https://pcmap.place.naver.com/lotto", "label": "네이버 플레이스", "priority": 2}],
            "fallback": {"url": "#", "label": "검색"},
        }
        html = injector.build_external_link_card(links, "로또")
        assert "dhlottery.co.kr" in html
        assert "place.naver.com" in html

    def test_bs4_removed_no_scraping(self):
        """BS4 스크래핑 메서드가 제거되었어야 함."""
        import chain_card_injector as mod
        source = open(mod.__file__).read()
        assert "_search_via_bs4" not in source
        assert "BeautifulSoup" not in source


# ── 서브태스크 C: 내용 겸침 방지 ──


class TestContentOverlapPrevention:
    """프롬프트 역할 분담 + 중복 금지 테스트."""

    def test_prompts_yaml_has_role_definitions(self):
        """prompts.yaml에 역할 분담 규칙이 있어야 함."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        draft_user = prompts.get("draft_user", "")
        assert "역할 분담" in draft_user
        assert "rotcha" in draft_user
        assert "informationhot" in draft_user
        assert "techpawz" in draft_user

    def test_prompts_yaml_has_no_overlap_rule(self):
        """prompts.yaml에 중복 금지 규칙이 있어야 함."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        draft_user = prompts.get("draft_user", "")
        assert "반복하지 말 것" in draft_user or "중복" in draft_user or "겸침" in draft_user

    def test_prompts_yaml_has_independent_reading(self):
        """각 포스트 독립적 읽기 가능 명시."""
        import yaml
        with open("config/prompts.yaml", encoding="utf-8") as f:
            prompts = yaml.safe_load(f)
        draft_user = prompts.get("draft_user", "")
        assert "독립적으로 읽을 수 있되" in draft_user


# ── W3 이미지: Pollinations 프롬프트 규칙 ──


class TestPollinationsPromptRules:
    """Pollinations 프롬프트 규칙 테스트."""

    def test_no_people_block_always_included(self):
        """인물 금지 블록이 프롬프트에 항상 포함되어야 함."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="pension-overview",
            title="포천계곡펜션 추천",
            blog_key="rotcha",
        )
        assert "no people" in prompt
        assert "no humans" in prompt
        assert "no faces" in prompt

    def test_landscape_topic_style(self):
        """풍경 주제는 유화/수채화 스타일 적용."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="pocheon-valley-pension",
            title="포천계곡펜션",
            blog_key="rotcha",
        )
        # 풍경 키워드가 포함되어야 함
        assert "landscape" in prompt or "natural" in prompt or "watercolor" in prompt or "oil painting" in prompt

    def test_abstract_topic_style(self):
        """추상 주제는 스케치/인포그래픽 스타일 적용."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="ai-prompt-market",
            title="AI 프롬프트 마켓",
            blog_key="informationhot",
        )
        assert "sketch" in prompt or "infographic" in prompt or "abstract" in prompt

    def test_object_topic_style(self):
        """사물 주제는 적절한 스타일 적용."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="fashion-platform",
            title="업클로젯 패션 플랫폼",
            blog_key="rotcha",
        )
        assert "pastel" in prompt or "illustration" in prompt or "fashion" in prompt

    def test_infer_topic_type_landscape(self):
        """풍경 키워드 추론."""
        from image.prompt_builder import _infer_topic_type
        assert _infer_topic_type("pocheon-valley-pension") == "landscape"
        assert _infer_topic_type("haeundae-hotel-resort") == "landscape"
        assert _infer_topic_type("travel-healing-cafe") == "landscape"

    def test_infer_topic_type_abstract(self):
        """추상 키워드 추론."""
        from image.prompt_builder import _infer_topic_type
        assert _infer_topic_type("ai-prompt-market") == "abstract"
        assert _infer_topic_type("software-testing") == "abstract"
        assert _infer_topic_type("finance-investment") == "abstract"

    def test_infer_topic_type_object(self):
        """사물 키워드 추론 (기본값)."""
        from image.prompt_builder import _infer_topic_type
        assert _infer_topic_type("upcloset-fashion") == "object"

    def test_negative_includes_people_keywords(self):
        """POLLINATIONS_NEGATIVE에 인물 키워드 포함."""
        from image.prompt_builder import POLLINATIONS_NEGATIVE
        assert "people" in POLLINATIONS_NEGATIVE
        assert "person" in POLLINATIONS_NEGATIVE
        assert "portrait" in POLLINATIONS_NEGATIVE

    def test_build_full_prompt_no_people(self):
        """build_full_prompt에도 인물 금지 포함."""
        from image.prompt_builder import build_full_prompt
        prompt = build_full_prompt("valley-pension", "rotcha")
        assert "no people" in prompt
        assert "no humans" in prompt
