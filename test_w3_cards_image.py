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
        assert "issue.techpawz" in draft_user
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
        assert "no hands" in prompt

    def test_no_people_block_has_body_parts(self):
        """NO_PEOPLE_BLOCK에 wrist/finger/arm/limb 포함."""
        from image.prompt_builder import NO_PEOPLE_BLOCK
        for kw in ["wrist", "finger", "arm", "limb", "body part"]:
            assert kw in NO_PEOPLE_BLOCK

    def test_forced_landscape_preamble_exists(self):
        """FORCED_LANDSCAPE_PREAMBLE이 정의되어 있음."""
        from image.prompt_builder import FORCED_LANDSCAPE_PREAMBLE
        assert "LANDSCAPE OR SCENERY ONLY" in FORCED_LANDSCAPE_PREAMBLE
        assert "NO PEOPLE" in FORCED_LANDSCAPE_PREAMBLE
        assert "NO HANDS" in FORCED_LANDSCAPE_PREAMBLE
        assert "NO BODY PARTS" in FORCED_LANDSCAPE_PREAMBLE

    def test_forced_landscape_at_beginning(self):
        """LANDSCAPE ONLY가 프롬프트 맨 앞에 배치됨."""
        from image.prompt_builder import build_full_prompt, FORCED_LANDSCAPE_PREAMBLE
        prompt = build_full_prompt("smartwatch", "rotcha")
        assert prompt.startswith(FORCED_LANDSCAPE_PREAMBLE)

    def test_landscape_topic_style(self):
        """풍경 주제는 유화/수채화 스타일 + landscape scenic 적용."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="pocheon-valley-pension",
            title="포천계곡펜션",
            blog_key="rotcha",
        )
        assert "landscape" in prompt or "scenic" in prompt or "watercolor" in prompt or "oil painting" in prompt

    def test_abstract_topic_style(self):
        """추상 주제는 스케치/인포그래픽 스타일 적용."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="ai-prompt-market",
            title="AI 프롬프트 마켓",
            blog_key="issue.techpawz",
        )
        assert "abstract" in prompt
        assert "serene background" in prompt or "symbolic" in prompt

    def test_object_topic_has_scenic_background(self):
        """사물 주제도 풍경 배경 안에 배치."""
        from image.prompt_builder import build_contextual_prompt
        prompt = build_contextual_prompt(
            image_keyword="blau-font-smartwatch",
            title="블라우풍트 스마트워치",
            blog_key="rotcha",
        )
        # "detailed still life" 대신 "scenic landscape background with" 사용
        assert "scenic" in prompt or "landscape background" in prompt
        assert "detailed still life" not in prompt

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
        """build_full_prompt에 인물 금지 + LANDSCAPE ONLY 포함."""
        from image.prompt_builder import build_full_prompt, FORCED_LANDSCAPE_PREAMBLE
        prompt = build_full_prompt("valley-pension", "rotcha")
        assert "no people" in prompt
        assert "no humans" in prompt
        assert prompt.startswith(FORCED_LANDSCAPE_PREAMBLE)


# ── 예방 조치: 미닫힌 펜스 감지 ──


class TestUnclosedFence:
    """미닫힌 코드 펜스 자동 닫기 테스트."""

    def test_closed_fence_unchanged(self):
        """닫힌 펜스는 수정 없음."""
        from chain_card_injector import CardInjector
        md = "---\ntitle: test\n---\n\n```json\n{}\n```\n\n본문"
        result = CardInjector.fix_unclosed_fences(md)
        assert result == md

    def test_unclosed_fence_with_content_below(self):
        """미닫힌 펜스 뒤에 내용이 있으면 닫기 추가."""
        from chain_card_injector import CardInjector
        md = "---\ntitle: test\n---\n\n```json\n{}\n\n본문입니다."
        result = CardInjector.fix_unclosed_fences(md)
        assert result.count("```") == 2  # 열기 + 닫기
        assert "본문입니다" in result

    def test_unclosed_fence_no_content_below(self):
        """미닫힌 펜스 뒤에 내용이 없으면 펜스 제거."""
        from chain_card_injector import CardInjector
        md = "---\ntitle: test\n---\n\n본문\n\n```json"
        result = CardInjector.fix_unclosed_fences(md)
        assert "```" not in result
        assert "본문" in result

    def test_unclosed_fence_in_chain28_pattern(self):
        """Chain #28 패턴: ````json` 끝에 미닫힘."""
        from chain_card_injector import CardInjector
        md = "---\ntitle: test\n---\n\n본문 끝.\n\n```json"
        result = CardInjector.fix_unclosed_fences(md)
        assert "```" not in result  # 펜스 제거됨

    def test_inject_cards_auto_fixes_fence(self):
        """카드 주입 시 미닫힌 펜스가 자동으로 닫힘."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        injector.config = {}
        injector.search_client = None
        md = "---\ntitle: test\n---\n\n본문 끝.\n\n```json"
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="다음 글",
            next_url="https://example.com",
            blog_key="rotcha",
            direction="next",
        )
        # 펜스가 닫혔거나 제거되어 shortcode가 정상적으로 주입됨
        assert "{{<" in result  # shortcode 존재

    def test_empty_md_unchanged(self):
        """빈 입력은 그대로 반환."""
        from chain_card_injector import CardInjector
        result = CardInjector.fix_unclosed_fences("")
        assert result == ""

    def test_no_fence_unchanged(self):
        """펜스가 없으면 그대로 반환."""
        from chain_card_injector import CardInjector
        md = "---\ntitle: test\n---\n\n본문만 있습니다."
        result = CardInjector.fix_unclosed_fences(md)
        assert result == md


# ── W1 카드 수정: D0/D1에 official_card 금지 ──


class TestCardFixW1:
    """W1 수정: D0/D1은 다음 글 카드 1개만, D2는 외부 링크 1개만."""

    def _make_injector(self):
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        injector.config = {}
        injector.search_client = None
        return injector

    def test_d0_has_only_next_card(self):
        """D0 (is_last=False)는 다음 글 카드 1개만."""
        injector = self._make_injector()
        md = "---\ntitle: D0\n---\n\n본문입니다."
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="D1 글",
            next_url="https://example.com/d1",
            blog_key="rotcha",
            direction="next",
            is_last=False,
        )
        # 다음 글 카드 1개
        assert result.count("chain-card") == 1
        # official-card 없음
        assert "chain-official-card" not in result
        # external link 카드 없음
        assert "바로가기" not in result

    def test_d1_has_only_next_card(self):
        """D1 (is_last=False)는 다음 글 카드 1개만."""
        injector = self._make_injector()
        md = "---\ntitle: D1\n---\n\n본문입니다."
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="D2 글",
            next_url="https://example.com/d2",
            blog_key="issue.techpawz",
            direction="next",
            is_last=False,
        )
        assert result.count("chain-card") == 1
        assert "chain-official-card" not in result

    def test_d2_has_only_external_card(self, monkeypatch):
        """D2 (is_last=True)는 외부 링크 카드 1개만."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        injector.config = {}
        # find_external_links mock
        def _mock_external(*a, **kw):
            return {
                "primary": {"url": "https://example.com", "label": "공식 사이트", "priority": 1},
                "secondary": [],
                "fallback": {"url": "https://search.naver.com", "label": "검색"},
            }
        monkeypatch.setattr(injector, "find_external_links", _mock_external)
        md = "---\ntitle: D2\n---\n\n본문입니다."
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="",
            next_url="",
            blog_key="techpawz",
            direction="next",
            is_last=True,
            seed_keyword="테스트",
        )
        # 외부 링크 카드 1개 (바로가기 링크 포함)
        assert "바로가기" in result
        # 다음 글 카드 없음
        assert result.count("chain-card") == 0

    def test_d0_no_duplicate_next_card(self):
        """D0에 다음 글 카드가 중복 주입되지 않음 (중간+하단)."""
        injector = self._make_injector()
        # H2가 3개 이상인 본문 (중간 카드 조건)
        md = "---\ntitle: D0\n---\n\n## H1\n본문1\n\n## H2\n본문2\n\n## H3\n본문3\n"
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="D1 글",
            next_url="https://example.com/d1",
            blog_key="rotcha",
            direction="next",
            is_last=False,
        )
        # 다음 글 카드 1개만 (중간 카드 제거됨)
        assert result.count("chain-card") == 1

    def test_d0_card_points_to_d1(self):
        """D0 카드가 D1 URL을 가리킴."""
        injector = self._make_injector()
        md = "---\ntitle: D0\n---\n\n본문입니다."
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="D1 글",
            next_url="https://issue.techpawz.com/d1",
            blog_key="rotcha",
            direction="next",
            is_last=False,
        )
        assert "issue.techpawz.com/d1" in result

    def test_d1_card_points_to_d2(self):
        """D1 카드가 D2 URL을 가리킴."""
        injector = self._make_injector()
        md = "---\ntitle: D1\n---\n\n본문입니다."
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="D2 글",
            next_url="https://techpawz.com/d2",
            blog_key="issue.techpawz",
            direction="next",
            is_last=False,
        )
        assert "techpawz.com/d2" in result


# ── 핫픽스: D9 게이트 외부링크 카드 중복 제거 ─────────────────


class TestD9GateExternalCardDedup:
    """D9 게이트: 외부 링크 카드 raw HTML + dual-cta shortcode 중복 제거 테스트."""

    def _make_injector(self):
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        injector.config = {}
        # find_external_links mock
        def _mock_external(*a, **kw):
            return {
                "primary": {"url": "https://example.com", "label": "공식 사이트", "priority": 1},
                "secondary": [],
                "fallback": {"url": "https://search.naver.com", "label": "검색"},
            }
        injector.find_external_links = _mock_external
        injector.search_client = None
        return injector

    def test_external_link_card_single_in_draft(self):
        """외부 링크 카드 1개 있는 draft → inject 후 카드 정확히 1개."""
        injector = self._make_injector()
        # build_external_link_card가 생성하는 primary 카드 HTML
        ext_card_html = (
            '<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;'
            'border-radius:8px;background:#f0fdf4;text-align:center">'
            '<p style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">관련 공식 사이트</p>'
            '<p style="font-size:0.95em;font-weight:bold;margin:0 0 0.5em 0">공식 사이트</p>'
            '<a href="https://example.com" target="_blank" rel="noopener" '
            'style="display:inline-block;padding:0.5em 1.5em;background:#16a34a;color:#fff;'
            'border-radius:4px;text-decoration:none;font-size:0.9em">'
            '바로가기 →</a>'
            '</div>'
        )
        md = f"---\ntitle: D2\n---\n\n본문입니다.\n\n{ext_card_html}"
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="",
            next_url="",
            blog_key="techpawz",
            direction="next",
            is_last=True,
            seed_keyword="테스트",
        )
        # 기존 카드 제거 후 새로 1개 주입 = 총 1개
        assert result.count("관련 공식 사이트") == 1
        assert result.count("바로가기") == 1

    def test_external_link_card_duplicate_in_draft(self):
        """외부 링크 카드 2개 중복 있는 draft → inject 후 카드 정확히 1개."""
        injector = self._make_injector()
        ext_card_html = (
            '<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;'
            'border-radius:8px;background:#f0fdf4;text-align:center">'
            '<p style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">관련 공식 사이트</p>'
            '<p style="font-size:0.95em;font-weight:bold;margin:0 0 0.5em 0">공식 사이트</p>'
            '<a href="https://example.com" target="_blank" rel="noopener" '
            'style="display:inline-block;padding:0.5em 1.5em;background:#16a34a;color:#fff;'
            'border-radius:4px;text-decoration:none;font-size:0.9em">'
            '바로가기 →</a>'
            '</div>'
        )
        md = f"---\ntitle: D2\n---\n\n본문입니다.\n\n{ext_card_html}\n\n{ext_card_html}"
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="",
            next_url="",
            blog_key="techpawz",
            direction="next",
            is_last=True,
            seed_keyword="테스트",
        )
        # 중복 2개 제거 후 새로 1개 주입 = 총 1개
        assert result.count("관련 공식 사이트") == 1
        assert result.count("바로가기") == 1

    def test_external_link_card_zero_in_draft(self):
        """외부 링크 카드 0개인 draft → inject 후 카드 정확히 1개 추가."""
        injector = self._make_injector()
        md = "---\ntitle: D2\n---\n\n본문입니다."
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="",
            next_url="",
            blog_key="techpawz",
            direction="next",
            is_last=True,
            seed_keyword="테스트",
        )
        # 새로 1개 주입 = 총 1개
        assert result.count("관련 공식 사이트") == 1
        assert result.count("바로가기") == 1

    def test_dual_cta_shortcode_duplicate_removed(self):
        """dual-cta shortcode 중복 제거 확인."""
        from chain_card_injector import CardInjector
        injector = CardInjector.__new__(CardInjector)
        injector.config = {}
        # D0/D1용 mock (is_last=False)
        def _mock_external(*a, **kw):
            return {"primary": None, "secondary": [], "fallback": {"url": "#", "label": "검색"}}
        injector.find_external_links = _mock_external
        injector.search_client = None

        dual_cta = '{{{{< dual-cta hub_url="https://example.com" hub_title="허브" info_url="https://example.com" info_title="시리즈" info_desc="설명" info_cta="보기 →" conv_url="" conv_title="" conv_desc="" conv_cta="" >}}}}'
        md = f"---\ntitle: D0\n---\n\n본문입니다.\n\n{dual_cta}\n\n{dual_cta}"
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="D1 글",
            next_url="https://example.com/d1",
            blog_key="rotcha",
            direction="next",
            is_last=False,
        )
        # dual-cta shortcode 2개 → 0개 제거 후 chain-card 1개 주입
        assert result.count("dual-cta") == 0
        assert result.count("chain-card") == 1

    def test_no_false_positive_on_body_text(self):
        """본문에 '관련 공식 사이트'라는 텍스트가 일반 문장으로 있는 경우 오탐 없음."""
        injector = self._make_injector()
        # 외부 링크 카드 HTML이 아닌 일반 텍스트로 "관련 공식 사이트" 언급
        md = (
            "---\ntitle: D2\n---\n\n"
            "이곳은 관련 공식 사이트에서 확인할 수 있습니다.\n"
            "관련 공식 사이트 링크를 참고하세요.\n"
        )
        result = injector.inject_cards_into_draft(
            draft_md=md,
            next_title="",
            next_url="",
            blog_key="techpawz",
            direction="next",
            is_last=True,
            seed_keyword="테스트",
        )
        # 일반 텍스트는 건드리지 않고, 새로 카드 1개만 주입
        # "관련 공식 사이트" 텍스트가 2번 (본문) + 1번 (새 카드) = 3번 나와야 함
        assert result.count("관련 공식 사이트") == 3
        assert result.count("바로가기") == 1  # 카드의 버튼만 1개
