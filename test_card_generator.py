"""
test_card_generator.py — CardGenerator 카드 스펙 생성 단위 테스트 (Phase 26 W2)

CardGenerator 는 link dict + 포스트 메타 → 카드 스펙(dict) 생성기.
스펙 구조/기본값/슬라이싱/입력 검증(T-26-12)을 검증한다.
렌더링 동일성은 test_html_renderer.py 의 GOLDEN 픽스처가 담당.
"""

import pytest

from card_generator import CardGenerator


@pytest.fixture()
def gen() -> CardGenerator:
    return CardGenerator()


# ── next/internal 스펙 ────────────────────────────────────────

def test_next_spec(gen):
    spec = gen.generate_next_card_spec("제목", "https://a.com", "더 알아보기 →")
    assert spec["type"] == "next"
    assert spec["title"] == "제목"
    assert spec["url"] == "https://a.com"
    assert spec["cta"] == "더 알아보기 →"


def test_internal_spec(gen):
    spec = gen.generate_internal_card_spec("제목", "https://a.com", "더 알아보기 →")
    assert spec["type"] == "internal"
    # next 와 동일 필드 구조 (렌더 결과 동일 — html_renderer 테스트가 보장)
    assert set(spec.keys()) == {"type", "title", "url", "cta"}


def test_chain_card_spec_next_internal(gen):
    assert gen.generate_chain_card_spec("next", "t", "u", "c")["type"] == "next"
    assert gen.generate_chain_card_spec("internal", "t", "u", "c")["type"] == "internal"


def test_chain_card_spec_invalid_type(gen):
    with pytest.raises(ValueError):
        gen.generate_chain_card_spec("official", "t", "u", "c")


# ── official 스펙 ─────────────────────────────────────────────

def test_official_spec_full(gen):
    spec = gen.generate_official_card_spec(
        {"title": "동행복권", "url": "https://dhlottery.co.kr", "label": "공식 사이트"}
    )
    assert spec == {
        "type": "official",
        "title": "동행복권",
        "url": "https://dhlottery.co.kr",
        "label": "공식 사이트",
    }


def test_official_spec_defaults(gen):
    """title/label 누락 시 기본값 (기존 build_official_card_html 과 동일)."""
    spec = gen.generate_official_card_spec({"url": "https://example.com"})
    assert spec["title"] == "공식 안내"
    assert spec["label"] == "공식 사이트"


def test_official_spec_none(gen):
    assert gen.generate_official_card_spec(None) == {"type": "none"}


def test_official_spec_empty_dict(gen):
    """빈 dict 는 falsy → none 스펙 (기존 동작과 동일)."""
    assert gen.generate_official_card_spec({}) == {"type": "none"}


# ── external 스펙 ─────────────────────────────────────────────

def test_external_spec_primary_normalization(gen):
    """primary: url 필수, label/title 기본값 정규화."""
    spec = gen.generate_external_card_spec(
        {"primary": {"url": "https://dhlottery.co.kr", "label": "동행복권", "priority": 1}},
        "로또",
    )
    assert spec["primary"] == {
        "url": "https://dhlottery.co.kr",
        "label": "동행복권",
        "title": "동행복권",  # title 미제공 → label 로 대체 (기존 동작)
    }
    assert spec["secondary"] == []
    assert spec["fallback"] is None  # primary 가 있으므로 fallback 불필요


def test_external_spec_primary_title_precedence(gen):
    """primary.title 제공 시 title 우선."""
    spec = gen.generate_external_card_spec(
        {"primary": {"url": "https://dhlottery.co.kr", "label": "동행복권", "title": "동행복권 공식", "priority": 1}},
        "로또",
    )
    assert spec["primary"]["title"] == "동행복권 공식"


def test_external_spec_primary_missing_url_raises(gen):
    """primary 에 url 이 없으면 기존과 동일하게 KeyError (유효하지 않은 링크)."""
    with pytest.raises(KeyError):
        gen.generate_external_card_spec({"primary": {"label": "라벨만"}})


def test_external_spec_secondary_slice_and_defaults(gen):
    """secondary: 최대 2개, label 기본값 '더 보기'."""
    spec = gen.generate_external_card_spec(
        {
            "primary": None,
            "secondary": [
                {"url": "https://a.com", "priority": 2},
                {"url": "https://b.com", "label": "B", "priority": 2},
                {"url": "https://c.com", "label": "C", "priority": 2},
            ],
        },
        "로또",
    )
    assert len(spec["secondary"]) == 2
    assert spec["secondary"] == [
        {"url": "https://a.com", "label": "더 보기"},
        {"url": "https://b.com", "label": "B"},
    ]


def test_external_spec_fallback_normalized(gen):
    """fallback 미제공/빈 dict → url='#', label=seed_keyword 기본값."""
    for links in ({}, {"primary": None, "secondary": [], "fallback": {}}):
        spec = gen.generate_external_card_spec(links, "테스트")
        assert spec["fallback"] == {
            "url": "#",
            "label": "네이버에서 '테스트' 검색",
        }


def test_external_spec_fallback_provided(gen):
    """fallback 제공 시 그대로 사용."""
    spec = gen.generate_external_card_spec(
        {"primary": None, "secondary": [], "fallback": {"url": "https://search.naver.com", "label": "검색"}},
        "테스트",
    )
    assert spec["fallback"] == {"url": "https://search.naver.com", "label": "검색"}


def test_external_spec_no_fallback_when_parts_exist(gen):
    """primary 또는 secondary 가 있으면 fallback 은 None."""
    spec = gen.generate_external_card_spec(
        {"primary": {"url": "https://a.com", "label": "L"}, "secondary": [], "fallback": {"url": "#", "label": "F"}},
        "로또",
    )
    assert spec["fallback"] is None


# ── 입력 검증 (T-26-12: 비문자열 HTML 오염 방지) ──────────────

@pytest.mark.parametrize("bad_value", [None, 123, 1.5, True, ["a"], {"x": 1}])
def test_next_spec_rejects_non_str(gen, bad_value):
    with pytest.raises(ValueError):
        gen.generate_next_card_spec(bad_value, "u", "c")
    with pytest.raises(ValueError):
        gen.generate_next_card_spec("t", bad_value, "c")
    with pytest.raises(ValueError):
        gen.generate_next_card_spec("t", "u", bad_value)


@pytest.mark.parametrize("bad_value", [None, 123, ["x"]])
def test_official_spec_rejects_non_str_values(gen, bad_value):
    """link 내 값이 비문자열이면 ValueError — 기존 f-string 'None' 노출 차단."""
    with pytest.raises(ValueError):
        gen.generate_official_card_spec({"title": bad_value, "url": "https://a.com"})
    with pytest.raises(ValueError):
        gen.generate_official_card_spec({"url": bad_value})


def test_external_spec_rejects_non_str_seed(gen):
    with pytest.raises(ValueError):
        gen.generate_external_card_spec({}, 42)


def test_external_spec_rejects_non_str_primary_label(gen):
    with pytest.raises(ValueError):
        gen.generate_external_card_spec({"primary": {"url": "https://a.com", "label": 7}})


def test_external_spec_rejects_non_str_secondary_url(gen):
    with pytest.raises(ValueError):
        gen.generate_external_card_spec(
            {"primary": None, "secondary": [{"url": None}]}
        )
