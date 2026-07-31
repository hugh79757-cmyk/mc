"""
test_card_integration.py — CardInjector 퍼사드 리팩터링 행동 동등성 테스트 (Phase 26 W3)

02-03 리팩터링(카드 HTML 생산을 CardGenerator+HtmlRenderer 로 위임) 전후의
출력이 바이트 단위로 동일함을 검증한다.

- GOLDEN: 리팩터링 전 build_card_html / build_official_card_html /
  build_external_link_card 의 실제 출력 21건 (02-02 작성 시점 캡처)
- GINT: 리팩터링 전 inject_bottom_card / inject_mid_card /
  inject_cards_into_draft 의 실제 출력 14건 (02-03 리팩터링 직전 캡처)
- API_SURFACE: 리팩터링 전 공개 메서드 시그니처 스냅샷

리팩터링은 __init__ 을 거치지 않는 인스턴스(__new__ 패턴)에서도 동작해야 한다
(기존 테스트 test_w3_cards_image.py 가 이 패턴을 사용) — 지연(lazy) 위임 검증 포함.
"""

import inspect

import pytest

from card_generator import CardGenerator
from html_renderer import HtmlRenderer
from chain_card_injector import CardInjector, DualCTAInjector

# ── 리팩터링 전 실제 출력 골든 픽스처 ──────────────────────────

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

GINT = {'inject_bottom_card::next_link_marker': {'ok': True,
                                          'out': '본문\n'
                                                 '\n'
                                                 '{{< chain-card title="D1" url="https://d1.com" cta="더 알아보기 '
                                                 '→" >}}\n'},
 'inject_bottom_card::h2_section': {'ok': True,
                                    'out': '## 제목\n'
                                           '본문\n'
                                           '\n'
                                           '## 마지막\n'
                                           '끝\n'
                                           '\n'
                                           '{{< chain-card title="D1" url="https://d1.com" cta="더 알아보기 →" '
                                           '>}}\n'},
 'inject_bottom_card::no_h2': {'ok': True,
                               'out': '본문만 있음\n'
                                      '\n'
                                      '{{< chain-card title="D1" url="https://d1.com" cta="더 알아보기 →" >}}'},
 'inject_bottom_card::empty': {'ok': True,
                               'out': '\n'
                                      '\n'
                                      '{{< chain-card title="D1" url="https://d1.com" cta="더 알아보기 →" >}}'},
 'inject_mid_card::3_h2': {'ok': True,
                           'out': '## A\n'
                                  '1\n'
                                  '\n'
                                  '## B\n'
                                  '2\n'
                                  '\n'
                                  '{{< chain-card title="D1" url="https://d1.com" cta="더 알아보기 →" >}}\n'
                                  '\n'
                                  '## C\n'
                                  '3\n'},
 'inject_mid_card::2_h2_noop': {'ok': True, 'out': '## A\n1\n\n## B\n2\n'},
 'inject_mid_card::no_h2': {'ok': True, 'out': '본문'},
 'inject_draft::d0_short': {'ok': True,
                            'out': '---\n'
                                   'title: D0\n'
                                   '---\n'
                                   '\n'
                                   '본문입니다.\n'
                                   '\n'
                                   '{{< chain-card title="D1 글" url="https://issue.techpawz.com/d1" cta="더 '
                                   '알아보기 →" >}}'},
 'inject_draft::d0_3h2': {'ok': True,
                          'out': '---\n'
                                 'title: D0\n'
                                 '---\n'
                                 '\n'
                                 '## H1\n'
                                 '본문1\n'
                                 '\n'
                                 '## H2\n'
                                 '본문2\n'
                                 '\n'
                                 '{{< chain-card title="D1 글" url="https://issue.techpawz.com/d1" cta="더 '
                                 '알아보기 →" >}}\n'
                                 '\n'
                                 '## H3\n'
                                 '본문3\n'
                                 '\n'
                                 '{{< chain-card title="D1 글" url="https://issue.techpawz.com/d1" cta="더 '
                                 '알아보기 →" >}}\n'},
 'inject_draft::d2_external': {'ok': True,
                               'out': '---\n'
                                      'title: D2\n'
                                      '---\n'
                                      '\n'
                                      '## H1\n'
                                      '본문1\n'
                                      '\n'
                                      '## H2\n'
                                      '본문2\n'
                                      '\n'
                                      '<div style="margin:1.5em '
                                      '0;padding:1em;border-radius:8px;background:#DC2626;text-align:center"><p '
                                      'style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 0 0.3em '
                                      '0">관련 공식 사이트</p><p '
                                      'style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 0 0.5em '
                                      '0">공식 사이트</p><a href="https://example.com" target="_blank" '
                                      'rel="noopener" style="display:inline-block;padding:0.5em '
                                      '1.5em;background:rgba(255,255,255,0.2);color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">예시 '
                                      '공식 바로가기 →</a></div>\n'
                                      '\n'
                                      '<div style="margin:1em 0;text-align:center"><a '
                                      'href="https://pcmap.place.naver.com/x" target="_blank" rel="noopener" '
                                      'style="display:inline-block;margin:0.2em;padding:0.4em '
                                      '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">네이버 '
                                      '플레이스 →</a></div>\n'
                                      '\n'
                                      '## H3\n'
                                      '본문3\n'
                                      '\n'
                                      '<div style="margin:1.5em '
                                      '0;padding:1em;border-radius:8px;background:#DC2626;text-align:center"><p '
                                      'style="font-size:0.85em;color:rgba(255,255,255,0.85);margin:0 0 0.3em '
                                      '0">관련 공식 사이트</p><p '
                                      'style="font-size:1.05em;font-weight:bold;color:#fff;margin:0 0 0.5em '
                                      '0">공식 사이트</p><a href="https://example.com" target="_blank" '
                                      'rel="noopener" style="display:inline-block;padding:0.5em '
                                      '1.5em;background:rgba(255,255,255,0.2);color:#fff;border-radius:4px;text-decoration:none;font-weight:600;font-size:0.9em">예시 '
                                      '공식 바로가기 →</a></div>\n'
                                      '\n'
                                      '<div style="margin:1em 0;text-align:center"><a '
                                      'href="https://pcmap.place.naver.com/x" target="_blank" rel="noopener" '
                                      'style="display:inline-block;margin:0.2em;padding:0.4em '
                                      '1em;background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">네이버 '
                                      '플레이스 →</a></div>\n'},
 'inject_draft::d9_existing_shortcode': {'ok': True,
                                         'out': '---\n'
                                                'title: D0\n'
                                                '---\n'
                                                '\n'
                                                '## H1\n'
                                                '본문\n'
                                                '\n'
                                                '\n'
                                                '\n'
                                                '## H2\n'
                                                '끝\n'
                                                '\n'
                                                '{{< chain-card title="D1 글" '
                                                'url="https://issue.techpawz.com/d1" cta="더 알아보기 →" >}}\n'},
 'inject_draft::unclosed_fence': {'ok': True,
                                  'out': '---\n'
                                         'title: D0\n'
                                         '---\n'
                                         '\n'
                                         '## H1\n'
                                         '본문\n'
                                         '```json\n'
                                         '{"a": 1}\n'
                                         '```\n'
                                         '\n'
                                         '## H2\n'
                                         '끝\n'
                                         '\n'
                                         '{{< chain-card title="D1 글" url="https://issue.techpawz.com/d1" '
                                         'cta="더 알아보기 →" >}}\n'},
 'inject_draft::no_frontmatter': {'ok': True,
                                  'out': '## H1\n'
                                         '본문\n'
                                         '\n'
                                         '## H2\n'
                                         '끝\n'
                                         '\n'
                                         '{{< chain-card title="D1 글" url="https://issue.techpawz.com/d1" '
                                         'cta="더 알아보기 →" >}}\n'},
 'inject_draft::d2_no_primary': {'ok': True,
                                 'out': '---\n'
                                        'title: D2\n'
                                        '---\n'
                                        '\n'
                                        '본문입니다.\n'
                                        '\n'
                                        '<div style="margin:1.5em 0;padding:1em;border:1px solid '
                                        '#e5e7eb;border-radius:8px;background:#fafafa;text-align:center"><p '
                                        'style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">더 많은 '
                                        '정보</p><a href="https://search.naver.com/search.naver?query=t" '
                                        'target="_blank" rel="noopener" '
                                        'style="display:inline-block;padding:0.5em '
                                        '1.5em;background:#333;color:#fff;border-radius:4px;text-decoration:none;font-size:0.9em">네이버에서 '
                                        "'테스트' 검색 →</a></div>"}}

# ── 리팩터링 전 공개 API 시그니처 스냅샷 ───────────────────────

API_SURFACE = {
    "CardInjector_methods": {
        "__init__": "(self, config: dict = None)",
        "_domain": "(self, url: str) -> str",
        "_naver_fallback": "(self, keyword: str) -> dict",
        "_search_via_api": "(self, query: str) -> list[dict]",
        "build_card_html": "(self, title: str, url: str, cta: str) -> str",
        "build_external_link_card": "(self, links: dict, seed_keyword: str = '') -> str",
        "build_official_card_html": "(self, link: dict) -> str",
        "find_external_links": "(self, title: str = '', keyword: str = '', seed: str = '') -> dict",
        "find_official_link": "(self, title: str = '', keyword: str = '', body: str = '') -> dict | None",
        "fix_unclosed_fences": "(draft_md: str) -> str",
        "get_cta": "(self, blog_key: str, direction: str, post_id: int = None, next_title: str = '', next_url: str = '') -> str",
        "inject_bottom_card": "(self, content: str, card_html: str) -> str",
        "inject_cards_into_draft": "(self, draft_md: str, next_title: str, next_url: str, blog_key: str, direction: str, post_title: str = '', post_keyword: str = '', post_body: str = '', is_last: bool = False, seed_keyword: str = '') -> str",
        "inject_into_post": "(self, publisher_core, post_id: int, next_title: str, next_url: str, blog_key: str, direction: str, is_last: bool = False, seed_keyword: str = '') -> bool",
        "inject_mid_card": "(self, content: str, card_html: str) -> str",
    },
    "DualCTAInjector_methods": {
        "__init__": "(self, config: dict = None)",
        "build_dual_cta_html": "(self, hub_url: str, hub_title: str, conv_cta_url: str = None) -> str",
        "inject_dual_cta_into_draft": "(self, draft_md: str, hub_url: str, hub_title: str, conv_cta_url: str = None) -> str",
        "inject_into_post": "(self, publisher_core, post_id: int, hub_url: str, hub_title: str, conv_cta_url: str = None) -> bool",
    },
}


@pytest.fixture()
def injector() -> CardInjector:
    """__init__ 미거치 인스턴스 — 기존 테스트 패턴(test_w3_cards_image)과 동일."""
    inj = CardInjector.__new__(CardInjector)
    inj.config = {}
    inj.search_client = None
    return inj


# ── API 서피스 보존 ──────────────────────────────────────────

def _actual_signature(cls, name):
    member = getattr(cls, name)
    return str(inspect.signature(member))


@pytest.mark.parametrize("name", sorted(API_SURFACE["CardInjector_methods"]))
def test_cardinjector_signature_unchanged(name):
    assert _actual_signature(CardInjector, name) == API_SURFACE["CardInjector_methods"][name]


@pytest.mark.parametrize("name", sorted(API_SURFACE["DualCTAInjector_methods"]))
def test_dualctainjector_signature_unchanged(name):
    """DualCTAInjector 는 이번 리팩터링에서 손대지 않음 — 시그니처/행동 보존."""
    assert _actual_signature(DualCTAInjector, name) == API_SURFACE["DualCTAInjector_methods"][name]


def test_module_level_functions_preserved():
    """테스트가 import 하는 모듈 레벨 함수 보존."""
    from chain_card_injector import _extract_domain, _decode_idn, _keyword_tokens, _score_official
    assert callable(_extract_domain)
    assert callable(_decode_idn)
    assert callable(_keyword_tokens)
    assert callable(_score_official)


def test_dualcta_injector_behavior_preserved():
    """DualCTAInjector.build_dual_cta_html 출력은 그대로 (v2: info CTA only)."""
    dci = DualCTAInjector.__new__(DualCTAInjector)
    html = dci.build_dual_cta_html("https://rotcha.kr/series/1", "시리즈 제목")
    assert html.startswith('{{< dual-cta hub_url="https://rotcha.kr/series/1"')
    assert 'info_cta="이 시리즈 보기 →"' in html
    assert "conv_cta=""" in html


# ── build_card_html (chain-card shortcode) ───────────────────

CARD_CASES = [
    ("기본", "더 깊이 분석", "https://issue.techpawz.com/post/123", "더 알아보기 →"),
    ("한글+숫자", "2026년 자동차 보험 비교", "https://techpawz.com/a/42", "더 알아보기 →"),
    ("특수문자", 'title with "quote" & <b>html</b>', "https://example.com/a?b=1&c=2", "더 알아보기 →"),
    ("빈 문자열", "", "", ""),
    ("유니코드 URL", "이벤트", "https://xn--example.com/이벤트?utm_source=x", "더 알아보기 →"),
]


@pytest.mark.parametrize("name,title,url,cta", CARD_CASES)
def test_build_card_html_byte_identical(injector, name, title, url, cta):
    assert injector.build_card_html(title, url, cta) == GOLDEN[f"build_card_html::{name}"]["out"]


# ── build_official_card_html ─────────────────────────────────

OFFICIAL_CASES = [
    ("기본", {"title": "동행복권", "url": "https://dhlottery.co.kr", "label": "공식 사이트"}),
    ("빈 dict", {}),
    ("None", None),
    ("title/label 누락", {"url": "https://example.com"}),
    ("한글+특수", {"title": '공식"사이트"', "url": "https://xn--b1a.com/path?q=1&x=2", "label": "공식 안내"}),
]


@pytest.mark.parametrize("name,link", OFFICIAL_CASES)
def test_build_official_card_html_byte_identical(injector, name, link):
    assert injector.build_official_card_html(link) == GOLDEN[f"build_official_card_html::{name}"]["out"]


# ── build_external_link_card ─────────────────────────────────

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
def test_build_external_link_card_byte_identical(injector, name, links, seed):
    exp = GOLDEN[f"build_external_link_card::{name}"]
    if exp["ok"] is False:
        with pytest.raises(KeyError):
            injector.build_external_link_card(links, seed)
    else:
        assert injector.build_external_link_card(links, seed) == exp["out"]


# ── 위임 검증: CardInjector 가 실제로 CardGenerator+HtmlRenderer 사용 ──

def test_facade_delegates_to_components(injector, monkeypatch):
    """build_card_html / build_official_card_html / build_external_link_card 가
    CardGenerator + HtmlRenderer 로 위임하는지 (스파이로 호출 확인)."""
    calls = {"gen": 0, "ren": 0}

    class SpyGenerator(CardGenerator):
        def generate_next_card_spec(self, *a, **kw):
            calls["gen"] += 1
            return super().generate_next_card_spec(*a, **kw)

        def generate_official_card_spec(self, *a, **kw):
            calls["gen"] += 1
            return super().generate_official_card_spec(*a, **kw)

        def generate_external_card_spec(self, *a, **kw):
            calls["gen"] += 1
            return super().generate_external_card_spec(*a, **kw)

    class SpyRenderer(HtmlRenderer):
        def render(self, spec):
            calls["ren"] += 1
            return super().render(spec)

    injector._card_generator = SpyGenerator()
    injector._html_renderer = SpyRenderer()

    injector.build_card_html("T", "U", "C")
    injector.build_official_card_html({"url": "https://a.com"})
    injector.build_external_link_card({"primary": None, "secondary": [], "fallback": {}}, "로또")
    assert calls["gen"] == 3
    assert calls["ren"] == 3


def test_lazy_init_without_dunder_init(injector):
    """__new__ 만으로 생성된 인스턴스에서도 위임 동작 (지연 생성)."""
    assert not hasattr(injector, "_card_generator")
    assert not hasattr(injector, "_html_renderer")
    html = injector.build_card_html("T", "U", "C")
    assert html == '{{< chain-card title="T" url="U" cta="C" >}}'
    assert isinstance(injector._card_generator, CardGenerator)
    assert isinstance(injector._html_renderer, HtmlRenderer)


def test_pipeline_equivalence_injector_vs_components():
    """CardInjector 경유 출력 == CardGenerator+HtmlRenderer 직접 파이프라인 출력."""
    inj = CardInjector.__new__(CardInjector)
    cg, hr = CardGenerator(), HtmlRenderer()
    links = {"primary": LOTTO_PRIMARY, "secondary": [NAVER_PLACE], "fallback": FALLBACK}
    assert inj.build_card_html("T", "U", "C") == hr.render(cg.generate_next_card_spec("T", "U", "C"))
    assert inj.build_official_card_html({"title": "동행복권", "url": "https://dhlottery.co.kr", "label": "공식 사이트"}) ==         hr.render(cg.generate_official_card_spec({"title": "동행복권", "url": "https://dhlottery.co.kr", "label": "공식 사이트"}))
    assert inj.build_external_link_card(links, "로또") == hr.render(cg.generate_external_card_spec(links, "로또"))


# ── inject_bottom_card / inject_mid_card (변경 없음 보존) ──────

NEXT_CARD = '{{< chain-card title="D1" url="https://d1.com" cta="더 알아보기 →" >}}'

BOTTOM_CASES = [
    ("next_link_marker", "본문\n\n<!--next_link-->\n"),
    ("h2_section", "## 제목\n본문\n\n## 마지막\n끝"),
    ("no_h2", "본문만 있음"),
    ("empty", ""),
]


@pytest.mark.parametrize("name,content", BOTTOM_CASES)
def test_inject_bottom_card_byte_identical(injector, name, content):
    assert injector.inject_bottom_card(content, NEXT_CARD) == GINT[f"inject_bottom_card::{name}"]["out"]


MID_CASES = [
    ("3_h2", "## A\n1\n\n## B\n2\n\n## C\n3\n"),
    ("2_h2_noop", "## A\n1\n\n## B\n2\n"),
    ("no_h2", "본문"),
]


@pytest.mark.parametrize("name,content", MID_CASES)
def test_inject_mid_card_byte_identical(injector, name, content):
    assert injector.inject_mid_card(content, NEXT_CARD) == GINT[f"inject_mid_card::{name}"]["out"]


# ── inject_cards_into_draft (전체 파이프라인) ─────────────────

def _make_draft_injector():
    inj = CardInjector.__new__(CardInjector)
    inj.config = {}
    inj.find_external_links = lambda *a, **kw: {
        "primary": {"url": "https://example.com", "label": "공식 사이트", "priority": 1, "title": "예시 공식"},
        "secondary": [{"url": "https://pcmap.place.naver.com/x", "label": "네이버 플레이스", "priority": 2}],
        "fallback": {"url": "https://search.naver.com/search.naver?query=t", "label": "네이버 검색"},
    }
    inj.search_client = None
    return inj


DRAFT_CASES = [
    ("d0_short", dict(
        draft_md="---\ntitle: D0\n---\n\n본문입니다.",
        next_title="D1 글", next_url="https://issue.techpawz.com/d1",
        blog_key="rotcha", direction="next", is_last=False)),
    ("d0_3h2", dict(
        draft_md="---\ntitle: D0\n---\n\n## H1\n본문1\n\n## H2\n본문2\n\n## H3\n본문3\n",
        next_title="D1 글", next_url="https://issue.techpawz.com/d1",
        blog_key="rotcha", direction="next", is_last=False)),
    ("d2_external", dict(
        draft_md="---\ntitle: D2\n---\n\n## H1\n본문1\n\n## H2\n본문2\n\n## H3\n본문3\n",
        next_title="", next_url="", blog_key="techpawz",
        direction="next", is_last=True, seed_keyword="테스트")),
    ("d9_existing_shortcode", dict(
        draft_md="---\ntitle: D0\n---\n\n## H1\n본문\n\n{{< chain-card title=\"old\" url=\"https://old.com\" cta=\"old →\" >}}\n\n## H2\n끝",
        next_title="D1 글", next_url="https://issue.techpawz.com/d1",
        blog_key="rotcha", direction="next", is_last=False)),
    ("unclosed_fence", dict(
        draft_md="---\ntitle: D0\n---\n\n## H1\n본문\n```json\n{\"a\": 1}\n```\n\n## H2\n끝\n```\n",
        next_title="D1 글", next_url="https://issue.techpawz.com/d1",
        blog_key="rotcha", direction="next", is_last=False)),
    ("no_frontmatter", dict(
        draft_md="## H1\n본문\n\n## H2\n끝",
        next_title="D1 글", next_url="https://issue.techpawz.com/d1",
        blog_key="rotcha", direction="next", is_last=False)),
]


@pytest.mark.parametrize("name,kwargs", DRAFT_CASES)
def test_inject_cards_into_draft_byte_identical(name, kwargs):
    """전체 파이프라인 출력 == 리팩터링 전 출력 (D9 게이트/펜스 수정 포함)."""
    inj = _make_draft_injector()
    assert inj.inject_cards_into_draft(**kwargs) == GINT[f"inject_draft::{name}"]["out"]


def test_inject_draft_d2_no_primary():
    """D2 + primary/secondary 없음 → fallback 카드만 (리팩터링 전과 동일)."""
    inj = CardInjector.__new__(CardInjector)
    inj.config = {}
    inj.find_external_links = lambda *a, **kw: {
        "primary": None, "secondary": [],
        "fallback": {"url": "https://search.naver.com/search.naver?query=t", "label": "네이버에서 '테스트' 검색"},
    }
    inj.search_client = None
    out = inj.inject_cards_into_draft(
        draft_md="---\ntitle: D2\n---\n\n본문입니다.",
        next_title="", next_url="", blog_key="techpawz",
        direction="next", is_last=True, seed_keyword="테스트")
    assert out == GINT["inject_draft::d2_no_primary"]["out"]


# ── fix_unclosed_fences (정적 메서드 보존) ─────────────────────

def test_fix_unclosed_fences_still_static_and_working():
    """정적 메서드 유지 + 기존 동작 보존 (test_w3_cards_image.py 의 의미론과 동일)."""
    assert isinstance(inspect.getattr_static(CardInjector, "fix_unclosed_fences"), staticmethod)
    # 내용이 남아 있으면 열기 직후 닫기 추가
    assert CardInjector.fix_unclosed_fences('```json\n{"a":1}\n') == '```json\n```\n{"a":1}\n'
    # 닫힌 펜스는 그대로
    assert CardInjector.fix_unclosed_fences('```json\n{"a":1}\n```') == '```json\n{"a":1}\n```'
    # 펜스만 남고 내용이 없으면 제거
    assert CardInjector.fix_unclosed_fences("본문\n\n```json") == "본문\n"
