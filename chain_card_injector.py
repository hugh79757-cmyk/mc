"""
chain_card_injector.py — 발행된 체인 포스트에 카드 후처리 삽입 (Phase 5)

카드 삽입 규칙 (정규화, AI 임의 결정 금지):
  3단계 카드 체계:
    - Depth 0 (rotcha): "더 알아보기" → Depth 1 URL
    - Depth 1 (issue.techpawz): "더 깊이 분석" → Depth 2 URL
    - Depth 2 (techpawz): 외부 링크 → 가장 공신력 있는 출처
  - 하단 Next 카드: 모든 글 기본 삽입 (본문 마지막 H2 섹션 이후)
  - 중간 관련 카드: H2가 3개 이상일 때 2번째 H2 직후 1개 삽입
  - 상단: 카드 금지 (광고 전용 영역)
  - CTA 문구: chain_config.yaml의 blog별 card_cta 블록에서 읽기

공신력 우선순위:
  1순위: 공식 운영 사이트 (.go.kr, .or.kr, 화이트리스트)
  2순위: 인정된 플랫폼 (naver place, instagram, kakao map)
  3순위: 네이버 검색 fallback
"""

import re
import os
import json
import logging
from datetime import datetime

from mc_paths import load_config, CHAIN_CONFIG_PATH
from mc.cta import get_cta, get_official_cta_text

from url_utils import extract_domain, normalize_url, strip_tracking_params, decode_idn  # noqa: F401 — URL 처리 단일 진실 공급원 (Phase 26)

from constants import (  # noqa: F401 — 상수 단일 진실 공급원 (Phase 26)
    AUTHORITY_PLATFORMS, SKIP_DOMAINS, SKIP_PATHS, KNOWN_OFFICIAL_SITE_DOMAINS,
)

from link_finder import LinkFinder  # noqa: F401 — 링크 추출 단일 진실 공급원 (Phase 26 W2)

from card_generator import CardGenerator  # noqa: F401 — 카드 스펙 생성 단일 진실 공급원 (Phase 26 W2)
from mc.year_guard import validate_and_fix_years
from html_renderer import HtmlRenderer  # noqa: F401 — 카드 HTML 렌더링 단일 진실 공급원 (Phase 26 W2)


logger = logging.getLogger(__name__)
from chain_db import get_post
from search_retriever import NaverSearchClient


# ── 공신력 도메인 화이트리스트 ──────────────────────────────
# 정의는 constants.py 로 이동 (단일 진실 공급원). 여기서는 import 만 유지한다.


def _extract_domain(url: str) -> str:
    """backward-compat wrapper; use url_utils.extract_domain."""
    return extract_domain(url)


def _decode_idn(domain: str) -> str:
    """backward-compat wrapper; use url_utils.decode_idn.

    punycode(xn--) 도메인을 유니코드로 디코딩. 실패 시 원본 반환.
    """
    return decode_idn(domain)


def _keyword_tokens(keyword: str) -> list[str]:
    """키워드에서 토큰 추출. 영문(2자+) + 한글(2자+) + 숫자 포함. 도메인 대조용."""
    tokens = [t.lower() for t in re.findall(r"[A-Za-z]{2,}", keyword)]
    # 한글 단어도 토큰으로 추출 (띄어쓰기 기준)
    for word in keyword.split():
        word = word.strip()
        if len(word) >= 2:
            tokens.append(word.lower())
    return tokens


def _score_official(url: str, title: str = "", keyword: str = "", rank: int = 99) -> tuple[int, int, str]:
    """검색 결과 신호로 공식성 점수 산출 (화이트리스트 없음).

    Returns:
        (priority, score, label)
        priority: 1=공식, 2=플랫폼, 0=제외
        score: 정렬용 세부 점수 (높을수록 공식에 가까움)
    """
    domain = _extract_domain(url)
    if not domain:
        return (0, 0, "invalid URL")

    # punycode 디코딩: 한글 도메인(시포트리조트.kr → xn--oy2b11opse0mmca85p.kr) 대응
    domain_unicode = _decode_idn(domain)
    if domain in KNOWN_OFFICIAL_SITE_DOMAINS or any(domain.endswith("." + d) for d in KNOWN_OFFICIAL_SITE_DOMAINS):
        return (1, 100, "\uacf5\uc2dd \uc0ac\uc774\ud2b8")
    url_lower = url.lower()
    url_unicode = url_lower.replace(domain, domain_unicode)  # URL 내 punycode를 한글로 치환

    # 플랫폼 (지도/SNS 등) → priority 2 (SKIP보다 먼저 검사: place.naver.com 등이 naver.com skip에 걸리지 않도록)
    for plat_domain, plat_name in AUTHORITY_PLATFORMS.items():
        if plat_domain in domain:
            return (2, 40, plat_name)

    # 구조적 배제 (블로그/뉴스/위키 등)
    if any(sk in domain for sk in SKIP_DOMAINS):
        return (0, 0, "skip domain")
    if any(s in url for s in SKIP_PATHS):
        return (0, 0, "skip path")

    score = 0
    label = "관련 사이트"

    # (신호 1 제거 — 공공 TLD 특별 취급 폐기, Phase 31)
    # 모든 도메인은 동일하게 키워드-도메인 일치, 제목 "공식" 표현, 순위 등 신호로만 판정.

    # 신호 2: 제목에 공식 표현
    tl = (title or "").lower()
    if any(w in title for w in ("공식", "공식홈페이지", "공식 홈페이지")) or "official" in tl:
        score += 30
        if label == "관련 사이트":
            label = "공식 사이트"

    # 신호 2B: 검색 결과 제목에 키워드(전체)가 포함 → 강력한 관련성 증거
    if keyword and title and keyword in title:
        score += 30
        if label == "관련 사이트":
            label = "공식 사이트"

    # 신호 3: 브랜드 토큰(영문+한글)이 도메인에 포함 (한글 도메인=punycode 디코딩 대응)
    for tok in _keyword_tokens(keyword):
        if tok in domain or (domain_unicode != domain and tok in domain_unicode):
            score += 25
            break

    # 신호 4: 상용 TLD 소폭 가점
    if domain.endswith((".co.kr", ".com", ".kr", ".net")):
        score += 10

    # 신호 5: 네이버 검색 상위 순위일수록 가점 (rank 0이 최상위)
    if rank <= 2:
        score += 20
    elif rank <= 4:
        score += 10

    # 신호 6: 키워드 단어가 URL 경로에 포함 (한글/영문 모두 + punycode 대응)
    for word in keyword.split():
        word = word.strip().lower()
        if len(word) >= 2 and (word in url_lower or word in url_unicode):
            score += 15
            break

    # 임계값: 55 이상이면 공식(priority 1)
    if score >= 55:
        return (1, score, label if label != "관련 사이트" else "공식 사이트")

    # 그 외: 배제 (fallback으로 넘김)
    return (0, score, label)


class CardInjector:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.search_client = NaverSearchClient()

    # ── 카드 생성/렌더링 위임 (Phase 26 W2) ─────────────────────
    # 카드 HTML 생산은 CardGenerator(스펙) + HtmlRenderer(HTML) 로 위임한다.
    # 출력은 리팩터링 전과 바이트 단위로 동일 (test_card_integration.py 스냅샷 보장).
    # __new__ 로 생성된 인스턴스(테스트에서 __init__ 미경유)에서도 동작하도록 지연 생성.

    def _generator(self) -> "CardGenerator":
        """CardGenerator 지연 생성 (__init__ 미거치 인스턴스 대응)."""
        if not hasattr(self, "_card_generator"):
            self._card_generator = CardGenerator()
        return self._card_generator

    def _renderer(self) -> "HtmlRenderer":
        """HtmlRenderer 지연 생성 (__init__ 미거치 인스턴스 대응)."""
        if not hasattr(self, "_html_renderer"):
            self._html_renderer = HtmlRenderer()
        return self._html_renderer

    # ── 공식 안내 링크 동적 검색 (Naver API) ────────────────────────

    OFFICIAL_QUERY_TEMPLATES = [
        "{keyword} 공식 사이트",
        "{keyword} 공식 홈페이지",
        "{keyword} 예약 공식",
        "{keyword} 안내 공식",
        "{keyword} 공식 안내",
    ]

    def _domain(self, url: str) -> str:
        return url.split("//", 1)[1].split("/", 1)[0] if "//" in url else url

    def find_external_links(self, title: str = "", keyword: str = "", seed: str = "") -> dict:
        """공신력 있는 외부 링크를 우선순위별로 추출.

        1순위: Naver Search API
        최종: Naver 검색 URL fallback (스크래핑 절대 금지)

        모든 도메인은 동일하게 검색 신호(키워드-도메인 일치, 제목 "공식" 표현, 순위)로만 판정.
        정부 TLD 특별 취급 없음 (Phase 31).

        Returns:
            {
                "primary": {"url": ..., "label": ..., "priority": 1},
                "secondary": [{"url": ..., "label": ..., "priority": 2}, ...],
                "fallback": {"url": ..., "label": ...},
            }
        """
        search_text = keyword or seed or title
        if not search_text:
            return {"primary": None, "secondary": [], "fallback": self._naver_fallback(search_text)}

        # Naver Search API only — 스크래핑 금지
        all_links = self._search_via_api(search_text)

        # Sort by priority (lower = better), then by score (higher = better)
        all_links.sort(key=lambda x: (x["priority"], -x.get("score", 0)))

        primary = None
        secondary = []
        seen_urls = set()
        for link in all_links:
            if link["url"] in seen_urls:
                continue
            seen_urls.add(link["url"])
            if link["priority"] == 1 and primary is None:
                primary = link
            elif link["priority"] == 2:
                secondary.append(link)

        fallback = self._naver_fallback(search_text)

        return {
            "primary": primary,
            "secondary": secondary[:3],  # max 3
            "fallback": fallback,
        }

    def _search_via_api(self, query: str) -> list[dict]:
        """Naver Search API로 검색."""
        all_links = []
        for template in self.OFFICIAL_QUERY_TEMPLATES:
            q = template.format(keyword=query)
            ok, data = self.search_client.search(q, endpoint="webkr", display=10)
            if not ok:
                continue
            try:
                results = json.loads(data).get("items", [])
                for rank, item in enumerate(results):
                    link = item.get("link", "")
                    if not link.startswith("http"):
                        continue
                    clean_title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    priority, score, label = _score_official(link, clean_title, query, rank)
                    if priority == 0:
                        continue
                    all_links.append({
                        "url": link,
                        "title": clean_title[:50],
                        "label": label,
                        "priority": priority,
                        "score": score,
                    })
            except json.JSONDecodeError:
                continue
        return all_links

    def _naver_fallback(self, keyword: str) -> dict:
        """네이버 검색 fallback URL."""
        from urllib.parse import quote
        q = quote(keyword) if keyword else ""
        return {
            "url": f"https://search.naver.com/search.naver?query={q}",
            "label": f"네이버에서 '{keyword}' 검색",
        }

    def find_official_link(self, title: str = "", keyword: str = "", body: str = "") -> dict | None:
        """find_external_links의 하위 호환 래퍼. 기존 호출 지점 호환."""
        result = self.find_external_links(title=title, keyword=keyword)
        if result["primary"]:
            return result["primary"]
        if result["secondary"]:
            return result["secondary"][0]
        return result.get("fallback")

    def build_official_card_html(self, link: dict) -> str:
        """공식 안내 링크 카드 shortcode.

        Phase 26: CardGenerator.generate_official_card_spec + HtmlRenderer 에 위임.
        출력은 리팩터링 전과 바이트 단위로 동일.
        """
        if not link:
            return ""
        spec = self._generator().generate_official_card_spec(link)
        return self._renderer().render(spec)

    # ── CTA 조회 ──────────────────────────────────────────────

# REPLACING METHOD - see below
    def get_cta(self, blog_key: str, direction: str, post_id: int = None, next_title: str = "", next_url: str = "") -> str:
        """블로그별 + 방향별 CTA 문구. 없으면 기본값.

        Phase 22: mc.cta.get_cta 사용으로 리다이렉트 (하위호환 유지).
        """
        if post_id is None:
            # Fallback to original behavior for backward compatibility
            return "더 알아보기 →"
        # Get post information
        post = get_post(post_id)
        if not post:
            return "더 알아보기 →"

        # Determine depth from step (step 1,2,3 -> depth 0,1,2)
        step = post.get("step", 1)
        depth = min(max(step - 1, 0), 2)  # Ensure 0-2 range

        # Get category
        category = post.get("category_guess", "etc")

        # Get next_url (for depth 0,1) or hub_url (for depth 2)
        next_url_param = None
        hub_url = None

        if depth < 2:  # Depth 0 or 1 - needs next_url for chain-card
            next_url_param = next_url
        else:  # Depth 2 - needs hub_url for hub CTA
            hub_url = self._get_hub_url(post["chain_id"])

        # Use the proper mc.cta.get_cta function
        from mc.cta import get_cta as mcta_get_cta
        result = mcta_get_cta(
            category=category,
            depth=depth,
            next_url=next_url_param,
            hub_url=hub_url
        )
        return result["html"]

    # ── 카드 HTML 생성 ────────────────────────────────────────

    def build_card_html(self, title: str, url: str, cta: str) -> str:
        """Hugo shortcode card (ChainInjector).

        Phase 26: CardGenerator.generate_next_card_spec + HtmlRenderer 에 위임.
        출력은 리팩터링 전과 바이트 단위로 동일.
        """
        spec = self._generator().generate_next_card_spec(title, url, cta)
        return self._renderer().render(spec)

    def build_external_link_card(self, links: dict, seed_keyword: str = "") -> str:
        """외부 링크 카드 HTML (Depth 2용). 공신력 우선순위 적용.

        Phase 26: CardGenerator.generate_external_card_spec + HtmlRenderer 에 위임.
        출력은 리팩터링 전과 바이트 단위로 동일.

        links: {"primary": {...}, "secondary": [...], "fallback": {...}}
        """
        spec = self._generator().generate_external_card_spec(links, seed_keyword)
        return self._renderer().render(spec)

    # ── 삽입 위치 정규화 ──────────────────────────────────────

    def inject_bottom_card(self, content: str, card_html: str) -> str:
        """마지막 H2 섹션 이후에 하단 카드 삽입."""
        if "<!--next_link-->" in content:
            return content.replace("<!--next_link-->", card_html)
        if "<!-- next_link -->" in content:
            return content.replace("<!-- next_link -->", card_html)
        h2_positions = [
            m.start() for m in re.finditer(r"^##\s", content, re.MULTILINE)
        ]
        if h2_positions:
            insert_at = h2_positions[-1]
            next_section = content[insert_at:]
            next_h2 = re.search(r"\n##\s", next_section[3:])
            if next_h2:
                section_end = insert_at + 3 + next_h2.start()
            else:
                section_end = len(content)
            before = content[:section_end].rstrip()
            after = content[section_end:]
            return before + "\n\n" + card_html + "\n" + after
        return content + "\n\n" + card_html

    def inject_mid_card(self, content: str, card_html: str) -> str:
        """H2가 3개 이상일 때만 2번째 H2 섹션 직후에 중간 카드 삽입.

        상단(첫 H2 이전)은 광고 전용이라 건드리지 않고,
        하단 카드와 겹치지 않도록 마지막 H2 섹션에는 넣지 않는다.
        조건 미충족 시 원본을 그대로 반환.
        """
        h2_positions = [
            m.start() for m in re.finditer(r"^##\s", content, re.MULTILINE)
        ]
        # H2가 3개 미만이면 중간 카드 없음 (본문이 짧아 광고 밀도 보호)
        if len(h2_positions) < 3:
            return content
        # 2번째 H2 섹션의 끝 = 3번째 H2 시작 직전
        second_h2_start = h2_positions[1]
        third_h2_start = h2_positions[2]
        before = content[:third_h2_start].rstrip()
        after = content[third_h2_start:]
        return before + "\n\n" + card_html + "\n\n" + after

    # ── 메인 진입점 (draft_md 기반) ────────────────────────────────

    @staticmethod
    def fix_unclosed_fences(draft_md: str) -> str:
        """미닫힌 코드 펜스(```)를 자동으로 닫거나 제거.

        ````json ... ``` 이 닫히지 않은 경우:
          - 펜스 뒤에 내용이 있으면 → 닫기 ``` 추가
          - 펜스 뒤에 내용이 없으면 → 펜스 자체 제거

        Returns:
            수정된 draft_md (변경 없으면 원본 그대로)
        """
        lines = draft_md.split("\n")
        fence_stack = []  # (line_index, fence_char)
        fence_pattern = re.compile(r'^(`{3,})\s*(\w+)?')
        in_frontmatter = False

        for i, line in enumerate(lines):
            stripped = line.strip()
            # frontmatter 처리 (--- 로 열고 닫힘)
            if stripped == "---":
                in_frontmatter = not in_frontmatter
                continue
            if in_frontmatter:
                continue

            m = fence_pattern.match(stripped)
            if m:
                fence_char = m.group(1)[:3]  # ```
                if fence_stack and fence_stack[-1][1] == fence_char:
                    fence_stack.pop()
                else:
                    fence_stack.append((i, fence_char))

        if not fence_stack:
            return draft_md  # 닫힌 펜스 없음

        # 마지막 미닫힌 펜스 처리
        last_open_line, fence_char = fence_stack[-1]
        remaining_after = "\n".join(lines[last_open_line + 1:]).strip()

        if remaining_after:
            # 펜스 뒤에 내용이 있으면 → 닫기 추가
            insert_at = last_open_line + 1
            lines.insert(insert_at, fence_char)
            return "\n".join(lines)
        else:
            # 펜스 뒤에 내용이 없으면 → 펜스 자체 제거
            del lines[last_open_line]
            return "\n".join(lines)

    def inject_cards_into_draft(
        self,
        draft_md: str,
        next_title: str,
        next_url: str,
        blog_key: str,
        direction: str,
        post_title: str = "",
        post_keyword: str = "",
        post_body: str = "",
        is_last: bool = False,
        seed_keyword: str = "",
    ) -> str:
        """
        draft_md (frontmatter + body)에 카드 주입.

        3단계 카드 체계:
          - Depth 0/1 (is_last=False): 다음 글 카드 + 공식 안내 링크
          - Depth 2 (is_last=True): 외부 링크 카드 (공신력 우선순위)

        삽입 순서 (하단에서 위로):
          1. 공식/외부 링크 카드 (맨 마지막)
          2. 다음 글 카드 (is_last=False일 때만)
          3. 중간 관련 카드 (H2 >= 3일 때 2번째 H2 직후)
        """
        # D9: 기존 chain-card/chain-official-card shortcode 제거 (중복 주입 방지)
        _old_count = len(re.findall(r'\{\{<\s*chain-(?:card|official-card)\s', draft_md))
        if _old_count > 0:
            draft_md = re.sub(r'\{\{<\s*chain-card\s+.*?\}\}', '', draft_md)
            draft_md = re.sub(r'\{\{<\s*chain-official-card\s+.*?\}\}', '', draft_md)
            logger.warning(f"[D9-GATE] Removed {_old_count} existing chain-card/chain-official-card shortcode(s) from draft")

        # D9-EXT: dual-cta shortcode 제거 (중복 주입 방지)
        _dual_cta_count = len(re.findall(r'\{\{<\s*dual-cta\s', draft_md))
        if _dual_cta_count > 0:
            draft_md = re.sub(r'\{\{<\s*dual-cta\s+.*?\}\}', '', draft_md)
            logger.warning(f"[D9-GATE] Removed {_dual_cta_count} existing dual-cta shortcode(s) from draft")

        # D9-EXT: 외부 링크 카드 raw HTML 제거 (중복 주입 방지)
        # build_external_link_card가 생성하는 패턴들:
        # 1. Primary: <div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;border-radius:8px;background:#f0fdf4;text-align:center">...관련 공식 사이트...바로가기 →...</div>
        # 2. Secondary: <div style="margin:1em 0;text-align:center">...<a ...>...</a>...</div>
        # 3. Fallback: <div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;border-radius:8px;background:#fafafa;text-align:center">...더 많은 정보...</div>
        _ext_card_count = 0
        # Pattern 1: Primary card with "관련 공식 사이트" + "바로가기"
        # 색상/스타일 무관하게 내용 키워드로 매칭 (붉은/초록 카드 모두 제거)
        primary_pattern = (
            r'<div style="margin:1\.5em 0;padding:1em;[^"]*text-align:center">'
            r'.*?관련 공식 사이트.*?'
            r'바로가기 →</a>'
            r'.*?</div>'
        )
        # Pattern 2: Secondary links div
        secondary_pattern = (
            r'<div style="margin:1em 0;text-align:center">'
            r'.*?<a href="[^"]*" target="_blank" rel="noopener" '
            r'style="display:inline-block;margin:0\.2em;padding:0\.4em 1em;'
            r'background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0\.85em">'
            r'.*?→</a>'
            r'.*?</div>'
        )
        # Pattern 3: Fallback card with "더 많은 정보"
        fallback_pattern = (
            r'<div style="margin:1\.5em 0;padding:1em;border:1px solid #e5e7eb;'
            r'border-radius:8px;background:#fafafa;text-align:center">'
            r'.*?더 많은 정보.*?'
            r'→</a>'
            r'.*?</div>'
        )

        for pattern in (primary_pattern, secondary_pattern, fallback_pattern):
            matches = re.findall(pattern, draft_md, re.DOTALL)
            _ext_card_count += len(matches)
            if matches:
                draft_md = re.sub(pattern, '', draft_md, flags=re.DOTALL)

        if _ext_card_count > 0:
            logger.warning(f"[D9-GATE] Removed {_ext_card_count} existing external link card HTML block(s) from draft")

        # 미닫힌 코드 펜스 자동 닫기
        draft_md = self.fix_unclosed_fences(draft_md)

        # frontmatter 분리
        if draft_md.startswith("---"):
            end = draft_md.find("---", 3)
            if end != -1:
                fm = draft_md[: end + 3]
                body = draft_md[end + 3 :].lstrip()
            else:
                fm = ""
                body = draft_md
        else:
            fm = ""
            body = draft_md

        if is_last:
            # Depth 2: 외부 링크 카드 (공신력 우선순위) — seed_keyword(원본 주제) 기준 검색
            links = self.find_external_links(
                title=post_title, keyword=seed_keyword, seed=seed_keyword
            )
            external_card = self.build_external_link_card(links, seed_keyword=seed_keyword)
            if external_card:
                body = self.inject_bottom_card(body, external_card)
        else:
            # Depth 0/1: 다음 글 카드 (1개만)
            cta = self.get_cta(blog_key, direction)
            next_card = self.build_card_html(next_title, next_url, cta)
            body = self.inject_bottom_card(body, next_card)

        # Travel chains use one CTA at the end; legacy behavior remains for other categories.
        # This prevents short travel posts from being interrupted by duplicate cards.
        try:
            from mc_paths import classify_keyword
            travel_single_cta = classify_keyword(seed_keyword) == "travel"
        except Exception:
            travel_single_cta = False
        if travel_single_cta:
            mid_card = None
        elif is_last:
            mid_links = self.find_external_links(
                title=post_title, keyword=seed_keyword, seed=seed_keyword
            )
            mid_card = self.build_external_link_card(mid_links, seed_keyword=seed_keyword)
        else:
            mid_cta = self.get_cta(blog_key, direction)
            mid_card = self.build_card_html(next_title, next_url, mid_cta)
        if mid_card:
            body = self.inject_mid_card(body, mid_card)

        # Phase 32: 카드 주입 후 최종 draft_md 연도 검증
        result = fm + "\n\n" + body if fm else body
        result, _year_warnings = validate_and_fix_years(result, fix_mode=True)
        return result

    # ── Hugo/Blogger 업데이트 (PublisherCore 위임) ─────────────────

    def inject_into_post(
        self,
        publisher_core,
        post_id: int,
        next_title: str,
        next_url: str,
        blog_key: str,
        direction: str,
        is_last: bool = False,
        seed_keyword: str = "",
    ) -> bool:
        """
        DB에서 published_md(또는 draft_md fallback) 조회 → 카드 주입 → 기존 frontmatter 보존 후 파일 업데이트.
        published_md가 있으면 R2 URL이 포함된 버전을 사용 (본문 이미지 깨짐 방지).
        is_last=True일 때는 외부 링크 카드 (공신력 우선순위) 주입.
        """
        post = get_post(post_id)
        if not post or not post.get("draft_md"):
            return False

        # published_md优先: R2 URL이 포함된 버전. 없으면 draft_md fallback.
        source_md = post.get("published_md") or post.get("draft_md")

        post_title = post.get("title", "")
        post_keyword = post.get("target_keyword", "")
        post_body = source_md

        updated_md = self.inject_cards_into_draft(
            source_md,
            next_title,
            next_url,
            blog_key,
            direction,
            post_title=post_title,
            post_keyword=post_keyword,
            post_body=post_body,
            is_last=is_last,
            seed_keyword=seed_keyword,
        )

        # 기존 파일에서 frontmatter 보존 (publish 시 적용된 draft:false, date, featureimage 등)
        hugo_file = post.get("hugo_file_path")
        if hugo_file and os.path.exists(hugo_file):
            with open(hugo_file, "r", encoding="utf-8") as f:
                existing = f.read()
            fm_end = existing.find("---", 4)
            if fm_end != -1:
                existing_fm = existing[:fm_end + 3]
                # updated_md에서 frontmatter 제거 후 기존 frontmatter와 결합
                if updated_md.startswith("---"):
                    body_end = updated_md.find("---", 4)
                    if body_end != -1:
                        updated_md = updated_md[body_end + 3:].lstrip("\n")
                updated_md = existing_fm + "\n\n" + updated_md

        publisher_core.update_post_content(
            blog_key,
            hugo_file or post_id,
            updated_md,
            is_html=False,
        )
        # 카드 주입 결과를 published_md에 저장 (다음 republish 시 R2 URL 보존)
        try:
            from chain_db import update_post_published_md
            update_post_published_md(post_id, updated_md)
        except Exception:
            pass
        return True


# ── Phase 6: Dual CTA Injector (기존 CardInjector 보존) ──


class DualCTAInjector:
    """Dual CTA (정보성 only — 전환성 CTA 폐기, v2) 카드 주입. Blowfish-compatible Tailwind HTML."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        loop_cfg = self.config.get("loop", {})
        cta_cfg = loop_cfg.get("cta", {})
        self.info_cta_text = cta_cfg.get("info_cta_text", "이 시리즈 보기 →")
        # conv CTA 폐기 (애드센스 모델에서 목적지 없음)
        self.conv_cta_text = ""
        self.conv_cta_url = ""

    # ── HTML 생성 ──────────────────────────────────────────

    def build_dual_cta_html(
        self,
        hub_url: str,
        hub_title: str,
        conv_cta_url: str = None,
    ) -> str:
        """Dual CTA shortcode — info CTA only (conv CTA removed in v2)."""
        return (
            f'{{{{< dual-cta '
            f'hub_url="{hub_url}" '
            f'hub_title="{hub_title}" '
            f'info_url="{hub_url}" '
            f'info_title="이 시리즈 전체 보기" '
            f'info_desc="이 시리즈의 모든 글을 한곳에서 확인하세요." '
            f'info_cta="이 시리즈 보기 →" '
            f'conv_url="" '
            f'conv_title="" '
            f'conv_desc="" '
            f'conv_cta="" >}}}}'
        )

    # ── draft_md 주입 ──────────────────────────────────────

    def inject_dual_cta_into_draft(
        self,
        draft_md: str,
        hub_url: str,
        hub_title: str,
        conv_cta_url: str = None,
    ) -> str:
        """Frontmatter 보존 + body 마지막에 듀얼 CTA 삽입."""
        if draft_md.startswith("---"):
            end = draft_md.find("---", 3)
            if end != -1:
                fm = draft_md[: end + 3]
                body = draft_md[end + 3 :].lstrip()
            else:
                fm = ""
                body = draft_md
        else:
            fm = ""
            body = draft_md

        card_html = self.build_dual_cta_html(hub_url, hub_title, conv_cta_url)

        # 기존 단일 CTA 카드 제거 (Phase 5 card_injected 클리어)
        body = re.sub(
            r'<div style="padding:1em;margin:2em 0;border:1px solid #ddd;'
            r'border-radius:8px;background:#fafafa;text-align:center;">.*?</div>',
            "",
            body,
            flags=re.DOTALL,
        )

        body = body.rstrip() + "\n\n" + card_html + "\n"
        return fm + "\n\n" + body if fm else body

    # ── 포스트 단위 실행 ───────────────────────────────────

    def inject_into_post(
        self,
        publisher_core,
        post_id: int,
        hub_url: str,
        hub_title: str,
        conv_cta_url: str = None,
    ) -> bool:
        """Load draft_md → inject dual CTA → republish via PublisherCore."""
        post = get_post(post_id)
        if not post or not post.get("draft_md"):
            return False

        # DB draft_md 백업 (원본 보존)
        orig_draft = post["draft_md"]

        # 듀얼 CTA 주입
        updated_md = self.inject_dual_cta_into_draft(
            orig_draft, hub_url, hub_title, conv_cta_url
        )

        # DB 업데이트 (draft_md + card_injected 플래그)
        from chain_db import update_post_draft, update_card_injected
        import chain_db as db

        slug = post.get("slug", "")
        db_conn = db.get_conn()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db_conn.execute(
            "UPDATE chain_posts SET draft_md = ?, card_injected = 1, "
            "card_injected_at = ?, updated_at = ? WHERE id = ?",
            (updated_md, now, now, post_id),
        )
        db_conn.commit()
        db_conn.close()

        # 재발행 (full hugo build + wrangler deploy)
        blog_key = post.get("publish_method") or "rotcha"
        published_url, method, file_path = publisher_core.publish_post(
            blog_key,
            updated_md,
            slug,
            post.get("title", ""),
            chain_type=post.get("chain_type", "depth"),
        )

        if published_url:
            print(f"  [dual-cta] ✅ Post #{post_id} republished: {published_url}")
            return True
        else:
            print(f"  [dual-cta] ❌ Post #{post_id} republish failed")
            return False

