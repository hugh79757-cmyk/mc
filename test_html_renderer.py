"""
test_html_renderer.py — HtmlRenderer 카드 HTML 렌더링 단위 테스트 (Phase 26 W2)

핵심 계약: HtmlRenderer + CardGenerator 파이프라인 출력이 리팩터링 전
chain_card_injector.CardInjector 의 출력과 바이트 단위로 동일하다.
GOLDEN 픽스처는 02-03 리팩터링 전 현재 구현에서 캡처한 실제 출력이다.
"""

import pytest

from card_generator import CardGenerator
from html_renderer import HtmlRenderer

# 리팩터링 전 CardInjector 출력 골든 픽스처 (캡처: 02-02 작성 시점, pre-refactor)
GOLDEN = {'build_card_html::기본': {'ok': True,
                         'out': '{{< chain-card title="더 깊이 분석" url="https://issue.techpawz.com/post/123" '
                                'cta="더 알아보기 →" >}}'},
 'build_card_html::한글+숫자': {'ok': True,
                            'out': '{{< chain-card title="2026년 자동차 보험 비교" url="https://techpawz.com/a/42" '
                                   'cta="더 알아보기 →" >}}'},
 'build_card_html::특수문자': {'ok': True,
                           'out': '{{< chain-card title="title with "quote" & <b>html</b>" '
                                  'url="https://example.com/a?b=1&c=2" cta="더 알아보기 →" >}}'},
 'build_card_html::빈 문자열': {'ok': True, 'out': '{{< chain-card title="" url="" cta="" >}}'},
 'build_card_html::유니코드 URL': {'ok': True,
                               'out': '{{< chain-card title="이벤트" '
                                      'url="https://xn--example.com/이벤트?utm_source=x" cta="더 알아보기 →" >}}'},
 'build_official_card_html::기본': {'ok': True,
                                  'out': '{{< chain-official-card title="동행복권" url="https://dhlottery.co.kr" '
                                         'label="공식 사이트" >}}'},
 'build_official_card_html::빈 dict': {'ok': True, 'out': ''},
 'build_official_card_html::None': {'ok': True, 'out': ''},
 'build_official_card_html::title/label 누락': {'ok': True,
                                              'out': '{{< chain-official-card title="공식 안내" '
                                                     'url="https://example.com" label="공식 사이트" >}}'},
 'build_official_card_html::한글+특수': {'ok': True,
                                     'out': '{{< chain-official-card title="공식"사이트"" '
                                            'url="https://xn--b1a.com/path?q=1&x=2" label="공식 안내" >}}'},
 'build_external_link_card::primary+secondary2+fallback': {'ok': True,
                                                           'out': '<div style="margin:1.5em '
                                                                  '0;padding:1em;border-radius:8px;background:#DC2626;text-align:center"><p '
                                                                  'style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 '
                                                                  '0 0.3em 0">관련 공식 사이트</p><p '
                                                                  'style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 '
                                                                  '0 0.5em 0">동행복권</p><a '
                                                                  'href="https://dhlottery.co.kr" '
                                                                  'target="_blank" rel="noopener" '
                                                                  'style="display:inline-block;padding:0.5em '
                                                                  '1.5em;background:rgba(255,255,255,0.2);color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">동행복권 '
                                                                  '바로가기 →</a></div>\n'
                                                                  '\n'
                                                                  '<div style="margin:1em '
                                                                  '0;text-align:center"><a '
                                                                  'href="https://pcmap.place.naver.com/lotto" '
                                                                  'target="_blank" rel="noopener" '
                                                                  'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                                  '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">네이버 '
                                                                  '플레이스 →</a> <a '
                                                                  'href="https://map.kakao.com/lotto" '
                                                                  'target="_blank" rel="noopener" '
                                                                  'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                                  '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">카카오맵 '
                                                                  '→</a></div>'},
 'build_external_link_card::primary only': {'ok': True,
                                            'out': '<div style="margin:1.5em '
                                                   '0;padding:1em;border-radius:8px;background:#DC2626;text-align:center"><p '
                                                   'style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 '
                                                   '0 0.3em 0">관련 공식 사이트</p><p '
                                                   'style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 '
                                                   '0 0.5em 0">동행복권</p><a href="https://dhlottery.co.kr" '
                                                   'target="_blank" rel="noopener" '
                                                   'style="display:inline-block;padding:0.5em '
                                                   '1.5em;background:rgba(255,255,255,0.2);color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">동행복권 '
                                                   '공식 바로가기 →</a></div>'},
 'build_external_link_card::primary w/o title': {'ok': True,
                                                 'out': '<div style="margin:1.5em '
                                                        '0;padding:1em;border-radius:8px;background:#DC2626;text-align:center"><p '
                                                        'style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 '
                                                        '0 0.3em 0">관련 공식 사이트</p><p '
                                                        'style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 '
                                                        '0 0.5em 0">동행복권</p><a '
                                                        'href="https://dhlottery.co.kr" target="_blank" '
                                                        'rel="noopener" '
                                                        'style="display:inline-block;padding:0.5em '
                                                        '1.5em;background:rgba(255,255,255,0.2);color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">동행복권 '
                                                        '바로가기 →</a></div>'},
 'build_external_link_card::secondary only': {'ok': True,
                                              'out': '<div style="margin:1em 0;text-align:center"><a '
                                                     'href="https://pcmap.place.naver.com/lotto" '
                                                     'target="_blank" rel="noopener" '
                                                     'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                     '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">네이버 '
                                                     '플레이스 →</a> <a href="https://map.kakao.com/lotto" '
                                                     'target="_blank" rel="noopener" '
                                                     'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                     '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">카카오맵 '
                                                     '→</a></div>'},
 'build_external_link_card::fallback only': {'ok': True,
                                             'out': '<div style="margin:1.5em 0;padding:1em;border:1px solid '
                                                    '#e5e7eb;border-radius:8px;background:#fafafa;text-align:center"><p '
                                                    'style="font-size:0.85em;color:#666;margin:0 0 0.3em '
                                                    '0">더 많은 정보</p><a '
                                                    'href="https://search.naver.com/search.naver?query=로또" '
                                                    'target="_blank" rel="noopener" '
                                                    'style="display:inline-block;padding:0.5em '
                                                    '1.5em;background:#333;color:#fff;border-radius:4px;text-decoration:none;font-size:0.9em">네이버에서 '
                                                    "'로또' 검색 →</a></div>"},
 'build_external_link_card::empty dict': {'ok': True,
                                          'out': '<div style="margin:1.5em 0;padding:1em;border:1px solid '
                                                 '#e5e7eb;border-radius:8px;background:#fafafa;text-align:center"><p '
                                                 'style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">더 '
                                                 '많은 정보</p><a href="#" target="_blank" rel="noopener" '
                                                 'style="display:inline-block;padding:0.5em '
                                                 '1.5em;background:#333;color:#fff;border-radius:4px;text-decoration:none;font-size:0.9em">네이버에서 '
                                                 "'로또' 검색 →</a></div>"},
 'build_external_link_card::empty fallback dict': {'ok': True,
                                                   'out': '<div style="margin:1.5em 0;padding:1em;border:1px '
                                                          'solid '
                                                          '#e5e7eb;border-radius:8px;background:#fafafa;text-align:center"><p '
                                                          'style="font-size:0.85em;color:#666;margin:0 0 '
                                                          '0.3em 0">더 많은 정보</p><a href="#" target="_blank" '
                                                          'rel="noopener" '
                                                          'style="display:inline-block;padding:0.5em '
                                                          '1.5em;background:#333;color:#fff;border-radius:4px;text-decoration:none;font-size:0.9em">네이버에서 '
                                                          "'테스트' 검색 →</a></div>"},
 'build_external_link_card::secondary w/o label': {'ok': True,
                                                   'out': '<div style="margin:1em 0;text-align:center"><a '
                                                          'href="https://a.com/x" target="_blank" '
                                                          'rel="noopener" '
                                                          'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                          '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">더 '
                                                          '보기 →</a></div>'},
 'build_external_link_card::secondary 5 items slice2': {'ok': True,
                                                        'out': '<div style="margin:1em '
                                                               '0;text-align:center"><a '
                                                               'href="https://pcmap.place.naver.com/lotto" '
                                                               'target="_blank" rel="noopener" '
                                                               'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                               '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">네이버 '
                                                               '플레이스 →</a> <a '
                                                               'href="https://map.kakao.com/lotto" '
                                                               'target="_blank" rel="noopener" '
                                                               'style="display:inline-block;margin:0.2em;padding:0.4em '
                                                               '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">카카오맵 '
                                                               '→</a></div>'},
 'build_external_link_card::primary no url key': {'ok': False, 'exc': 'KeyError'},
 'build_external_link_card::unicode hangul': {'ok': True,
                                              'out': '<div style="margin:1.5em '
                                                     '0;padding:1em;border-radius:8px;background:#DC2626;text-align:center"><p '
                                                     'style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 '
                                                     '0 0.3em 0">관련 공식 사이트</p><p '
                                                     'style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 '
                                                     '0 0.5em 0">시포트리조트</p><a '
                                                     'href="https://xn--oy2b11opse0mmca85p.kr" '
                                                     'target="_blank" rel="noopener" '
                                                     'style="display:inline-block;padding:0.5em '
                                                     '1.5em;background:rgba(255,255,255,0.2);color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">시포트리조트 '
                                                     '바로가기 →</a></div>'}}


@pytest.fixture()
def gen() -> CardGenerator:
    return CardGenerator()


@pytest.fixture()
def ren() -> HtmlRenderer:
    return HtmlRenderer()


# ── next/internal 카드 (chain-card shortcode) ──────────────────

CARD_CASES = [
    ("기본", "더 깊이 분석", "https://issue.techpawz.com/post/123", "더 알아보기 →"),
    ("한글+숫자", "2026년 자동차 보험 비교", "https://techpawz.com/a/42", "더 알아보기 →"),
    ("특수문자", 'title with "quote" & <b>html</b>', "https://example.com/a?b=1&c=2", "더 알아보기 →"),
    ("빈 문자열", "", "", ""),
    ("유니코드 URL", "이벤트", "https://xn--example.com/이벤트?utm_source=x", "더 알아보기 →"),
]


@pytest.mark.parametrize("name,title,url,cta", CARD_CASES)
def test_next_card_matches_golden(gen, ren, name, title, url, cta):
    """next 카드 스펙 렌더 == 리팩터링 전 build_card_html 출력."""
    spec = gen.generate_next_card_spec(title, url, cta)
    assert ren.render(spec) == GOLDEN[f"build_card_html::{name}"]["out"]


@pytest.mark.parametrize("name,title,url,cta", CARD_CASES)
def test_internal_card_matches_golden(gen, ren, name, title, url, cta):
    """internal 카드도 next 와 동일한 chain-card shortcode 출력."""
    spec = gen.generate_internal_card_spec(title, url, cta)
    assert ren.render(spec) == GOLDEN[f"build_card_html::{name}"]["out"]


@pytest.mark.parametrize("name,title,url,cta", CARD_CASES)
def test_chain_card_spec_matches_golden(gen, ren, name, title, url, cta):
    """공용 generate_chain_card_spec 도 동일 출력 (next/internal)."""
    for card_type in ("next", "internal"):
        spec = gen.generate_chain_card_spec(card_type, title, url, cta)
        assert ren.render(spec) == GOLDEN[f"build_card_html::{name}"]["out"]


def test_next_card_spec_structure(gen):
    """next 스펙 구조: type/title/url/cta 필드."""
    spec = gen.generate_next_card_spec("제목", "https://a.com", "더 알아보기 →")
    assert spec == {
        "type": "next",
        "title": "제목",
        "url": "https://a.com",
        "cta": "더 알아보기 →",
    }


def test_internal_card_spec_structure(gen):
    """internal 스펙 구조: type 만 next 와 다름."""
    spec = gen.generate_internal_card_spec("제목", "https://a.com", "더 알아보기 →")
    assert spec["type"] == "internal"
    assert spec["title"] == "제목"


def test_chain_card_spec_bad_type(gen):
    """지원하지 않는 chain-card 타입은 ValueError."""
    with pytest.raises(ValueError):
        gen.generate_chain_card_spec("bogus", "t", "u", "c")


# ── official 카드 (chain-official-card shortcode) ──────────────

OFFICIAL_CASES = [
    ("기본", {"title": "동행복권", "url": "https://dhlottery.co.kr", "label": "공식 사이트"}),
    ("빈 dict", {}),
    ("None", None),
    ("title/label 누락", {"url": "https://example.com"}),
    ("한글+특수", {"title": '공식"사이트"', "url": "https://xn--b1a.com/path?q=1&x=2", "label": "공식 안내"}),
]


@pytest.mark.parametrize("name,link", OFFICIAL_CASES)
def test_official_card_matches_golden(gen, ren, name, link):
    """official 카드 스펙 렌더 == 리팩터링 전 build_official_card_html 출력."""
    spec = gen.generate_official_card_spec(link)
    assert ren.render(spec) == GOLDEN[f"build_official_card_html::{name}"]["out"]


def test_official_card_spec_structure(gen):
    """official 스펙 구조 + 기본값."""
    spec = gen.generate_official_card_spec({"url": "https://example.com"})
    assert spec == {
        "type": "official",
        "title": "공식 안내",
        "url": "https://example.com",
        "label": "공식 사이트",
    }


def test_official_card_none_spec(gen, ren):
    """falsy link → none 스펙 → 빈 문자열."""
    assert gen.generate_official_card_spec(None) == {"type": "none"}
    assert ren.render({"type": "none"}) == ""


# ── external 카드 (raw HTML 복합) ──────────────────────────────

LOTTO_PRIMARY = {"url": "https://dhlottery.co.kr", "label": "동행복권", "priority": 1}
LOTTO_PRIMARY_TITLE = {"url": "https://dhlottery.co.kr", "label": "동행복권", "priority": 1, "title": "동행복권 공식"}
NAVER_PLACE = {"url": "https://pcmap.place.naver.com/lotto", "label": "네이버 플레이스", "priority": 2}
KAKAO = {"url": "https://map.kakao.com/lotto", "label": "카카오맵", "priority": 2}
INSTA = {"url": "https://instagram.com/lotto", "label": "인스타그램", "priority": 2}
FALLBACK = {"url": "https://search.naver.com/search.naver?query=로또", "label": "네이버에서 '로또' 검색"}

EXTERNAL_CASES = [
    ("primary+secondary2+fallback", {"primary": LOTTO_PRIMARY, "secondary": [NAVER_PLACE, KAKAO, INSTA], "fallback": FALLBACK}, "로또"),
    ("primary only", {"primary": LOTTO_PRIMARY_TITLE, "secondary": [], "fallback": FALLBACK}, "로또"),
    ("primary w/o title", {"primary": LOTTO_PRIMARY, "secondary": [], "fallback": FALLBACK}, "로또"),
    ("secondary only", {"primary": None, "secondary": [NAVER_PLACE, KAKAO], "fallback": FALLBACK}, "로또"),
    ("fallback only", {"primary": None, "secondary": [], "fallback": FALLBACK}, "로또"),
    ("empty dict", {}, "로또"),
    ("empty fallback dict", {"primary": None, "secondary": [], "fallback": {}}, "테스트"),
    ("secondary w/o label", {"primary": None, "secondary": [{"url": "https://a.com/x", "priority": 2}], "fallback": FALLBACK}, "로또"),
    ("secondary 5 items slice2", {"primary": None, "secondary": [NAVER_PLACE, KAKAO, INSTA, {"url": "https://d.com", "label": "D", "priority": 2}, {"url": "https://e.com", "label": "E", "priority": 2}], "fallback": FALLBACK}, "로또"),
    ("unicode hangul", {"primary": {"url": "https://xn--oy2b11opse0mmca85p.kr", "label": "시포트리조트", "priority": 1}, "secondary": [], "fallback": {"url": "https://search.naver.com/search.naver?query=%EC%8B%9C%ED%8F%AC", "label": "네이버 검색"}}, "시포트리조트"),
]


@pytest.mark.parametrize("name,links,seed", EXTERNAL_CASES)
def test_external_card_matches_golden(gen, ren, name, links, seed):
    """external 카드 스펙 렌더 == 리팩터링 전 build_external_link_card 출력."""
    spec = gen.generate_external_card_spec(links, seed)
    assert ren.render(spec) == GOLDEN[f"build_external_link_card::{name}"]["out"]


def test_external_card_primary_no_url_key_raises(gen):
    """primary 에 url 키가 없으면 기존 구현과 동일하게 KeyError 전파."""
    with pytest.raises(KeyError):
        gen.generate_external_card_spec({"primary": {"label": "라벨만"}, "secondary": [], "fallback": FALLBACK})


def test_external_spec_secondary_slice2(gen):
    """secondary 는 최대 2개로 슬라이싱."""
    spec = gen.generate_external_card_spec(
        {"primary": None, "secondary": [NAVER_PLACE, KAKAO, INSTA], "fallback": FALLBACK}, "로또"
    )
    assert len(spec["secondary"]) == 2
    assert [s["url"] for s in spec["secondary"]] == [
        "https://pcmap.place.naver.com/lotto",
        "https://map.kakao.com/lotto",
    ]


def test_external_spec_fallback_defaults(gen):
    """fallback 미제공 시 url='#', label=seed_keyword 기반 기본값."""
    spec = gen.generate_external_card_spec({}, "로또")
    assert spec["primary"] is None
    assert spec["secondary"] == []
    assert spec["fallback"] == {
        "url": "#",
        "label": "네이버에서 '로또' 검색",
    }


def test_external_renderer_parts_joined_double_newline(gen, ren):
    """primary+secondary 블록이 \n\n 로 결합."""
    spec = gen.generate_external_card_spec(
        {"primary": LOTTO_PRIMARY, "secondary": [NAVER_PLACE], "fallback": FALLBACK}, "로또"
    )
    html = ren.render(spec)
    assert html.count("\n\n") == 1
    assert "관련 공식 사이트" in html
    assert "place.naver.com" in html
    assert "더 많은 정보" not in html  # primary/secondary 가 있으면 fallback 미렌더


# ── 렌더러 디스패치 / 엣지 ───────────────────────────────────

def test_render_unknown_type_raises(ren):
    """지원하지 않는 스펙 타입은 ValueError."""
    with pytest.raises(ValueError):
        ren.render({"type": "bogus"})


def test_render_none_returns_empty(ren):
    """none 스펙 → 빈 문자열."""
    assert ren.render({"type": "none"}) == ""


def test_render_shortcode_structure(gen, ren):
    """shortcode 정확한 구조: {{< chain-card ... >}} / {{< chain-official-card ... >}}."""
    assert ren.render(gen.generate_next_card_spec("T", "U", "C")) == '{{< chain-card title="T" url="U" cta="C" >}}'
    assert ren.render(gen.generate_official_card_spec({"url": "U"})) == (
        '{{< chain-official-card title="공식 안내" url="U" label="공식 사이트" >}}'
    )


def test_render_does_not_escape_quotes(gen, ren):
    """현재 구현은 따옴표/HTML을 이스케이프하지 않는다 — 바이트 동일성 계약 유지."""
    html = ren.render(gen.generate_next_card_spec('a"b', "u", "c"))
    assert html == '{{< chain-card title="a"b" url="u" cta="c" >}}'
