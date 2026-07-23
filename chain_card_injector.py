"""
chain_card_injector.py — 발행된 체인 포스트에 카드 후처리 삽입 (Phase 5)

카드 삽입 규칙 (정규화, AI 임의 결정 금지):
  3단계 카드 체계:
    - Depth 0 (rotcha): "더 알아보기" → Depth 1 URL
    - Depth 1 (informationhot): "더 깊이 분석" → Depth 2 URL
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
from datetime import datetime

from mc_paths import load_config, CHAIN_CONFIG_PATH
from chain_db import get_post
from search_retriever import NaverSearchClient


# ── 공신력 도메인 화이트리스트 ──────────────────────────────

AUTHORITY_GOVERNMENT = (".go.kr", ".or.kr", ".gov.kr")
AUTHORITY_PLATFORMS = {
    "place.naver.com": "네이버 플레이스",
    "map.naver.com": "네이버 지도",
    "map.kakao.com": "카카오맵",
    "instagram.com": "인스타그램",
    "facebook.com": "페이스북",
}
# 잘 알려진 공식 사이트 (도메인 → 설명) — 2026-07 HTTP 검증 완료
AUTHORITY_WHITELIST = {
    "dhlottery.co.kr": "동행복권",
    "letskorail.com": "코레일",
    "ktx.co.kr": "KTX",
    "jejuair.net": "제주항공",
    "twayair.com": "티웨이항공",
    "jinair.com": "진에어",
    "koreanair.com": "대한항공",
    # 제거됨 (2026-07 검증): ferrypark.co.kr(미해석), airbusan.com(미해석), phr.co.kr(미해석)
}
SKIP_DOMAINS = (
    "naver.com", "blog.naver.com", "brunch.co.kr", "tistory.com",
    "velog.io", "medium.com", "news.naver.com", "dispatch.co.kr",
    "youtube.com", "wikipedia.org",
)
SKIP_PATHS = (
    "/board/", "/faq", "/customer", "/bbs/", "/menu/",
    "/cruiseinfo/", "/useinfo/", "/terms/", "/?type=",
)


def _classify_authority(url: str, keyword: str = "") -> tuple[int, str]:
    """URL의 공신력 순위를 반환. (순위, 설명) — 높을수록 좋음.

    Returns:
        (priority, label) — priority: 1=공식, 2=플랫폼, 3=fallback, 0=제외
    """
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
    except Exception:
        return (0, "invalid URL")

    # 1순위: 공식 운영 사이트
    if any(domain.endswith(d) for d in AUTHORITY_GOVERNMENT):
        return (1, "공공기관")
    if domain in AUTHORITY_WHITELIST:
        return (1, AUTHORITY_WHITELIST[domain])
    # 서브도메인도 확인 (예: www.dhlottery.co.kr → dhlottery.co.kr)
    for wl_domain in AUTHORITY_WHITELIST:
        if domain == wl_domain or domain.endswith("." + wl_domain):
            return (1, AUTHORITY_WHITELIST[wl_domain])

    # 2순위: 인정된 플랫폼
    for plat_domain, plat_name in AUTHORITY_PLATFORMS.items():
        if plat_domain in domain:
            return (2, plat_name)

    # 제외 대상
    if any(sk in domain for sk in SKIP_DOMAINS):
        return (0, "skip")
    if any(s in url for s in SKIP_PATHS):
        return (0, "skip path")

    # 기타: 일반 사이트 (3순위보다 높지만 공식은 아님)
    return (3, "기타")


class CardInjector:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self.search_client = NaverSearchClient()

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

        # Sort by priority (lower = better), then by order of appearance
        all_links.sort(key=lambda x: x["priority"])

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
                for item in results:
                    link = item.get("link", "")
                    if not link.startswith("http"):
                        continue
                    clean_title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    priority, label = _classify_authority(link, query)
                    if priority == 0:
                        continue
                    all_links.append({
                        "url": link,
                        "title": clean_title[:50],
                        "label": label,
                        "priority": priority,
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
        """공식 안내 링크 카드 shortcode."""
        if not link:
            return ""
        title = link.get("title", "공식 안내")
        url = link.get("url", "https://www.gov.kr")
        label = link.get("label", "공식 사이트")
        return (
            f'{{{{< chain-official-card '
            f'title="{title}" '
            f'url="{url}" '
            f'label="{label}" >}}}}'
        )

    # ── CTA 조회 ──────────────────────────────────────────────

    def get_cta(self, blog_key: str, direction: str) -> str:
        """블로그별 + 방향별 CTA 문구. 없으면 기본값."""
        site = self.config.get("sites", {}).get(blog_key, {})
        cta_map = site.get("card_cta", {})
        return cta_map.get(direction, "계속 읽기 →")

    # ── 카드 HTML 생성 ────────────────────────────────────────

    def build_card_html(self, title: str, url: str, cta: str) -> str:
        """Hugo shortcode card (ChainInjector)."""
        return (
            f'{{{{< chain-card '
            f'title="{title}" '
            f'url="{url}" '
            f'cta="{cta}" >}}}}'
        )

    def build_external_link_card(self, links: dict, seed_keyword: str = "") -> str:
        """외부 링크 카드 HTML (Depth 2용). 공신력 우선순위 적용.

        links: {"primary": {...}, "secondary": [...], "fallback": {...}}
        """
        parts = []

        # 1순위: 공식 사이트
        primary = links.get("primary")
        if primary:
            url = primary["url"]
            label = primary.get("label", "공식 사이트")
            parts.append(
                f'<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;'
                f'border-radius:8px;background:#f0fdf4;text-align:center">'
                f'<p style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">관련 공식 사이트</p>'
                f'<p style="font-size:0.95em;font-weight:bold;margin:0 0 0.5em 0">{label}</p>'
                f'<a href="{url}" target="_blank" rel="noopener" '
                f'style="display:inline-block;padding:0.5em 1.5em;background:#16a34a;color:#fff;'
                f'border-radius:4px;text-decoration:none;font-size:0.9em">'
                f'바로가기 →</a>'
                f'</div>'
            )

        # 2순위: 플랫폼 링크
        secondary = links.get("secondary", [])
        if secondary:
            links_html = []
            for s in secondary[:2]:
                links_html.append(
                    f'<a href="{s["url"]}" target="_blank" rel="noopener" '
                    f'style="display:inline-block;margin:0.2em;padding:0.4em 1em;'
                    f'background:#2563eb;color:#fff;border-radius:4px;text-decoration:none;font-size:0.85em">'
                    f'{s.get("label", "더 보기")} →</a>'
                )
            parts.append(
                f'<div style="margin:1em 0;text-align:center">'
                + " ".join(links_html)
                + "</div>"
            )

        # Fallback: 검색 결과가 없을 때
        if not parts:
            fallback = links.get("fallback", {})
            url = fallback.get("url", "#")
            label = fallback.get("label", f"네이버에서 '{seed_keyword}' 검색")
            parts.append(
                f'<div style="margin:1.5em 0;padding:1em;border:1px solid #e5e7eb;'
                f'border-radius:8px;background:#fafafa;text-align:center">'
                f'<p style="font-size:0.85em;color:#666;margin:0 0 0.3em 0">더 많은 정보</p>'
                f'<a href="{url}" target="_blank" rel="noopener" '
                f'style="display:inline-block;padding:0.5em 1.5em;background:#333;color:#fff;'
                f'border-radius:4px;text-decoration:none;font-size:0.9em">'
                f'{label} →</a>'
                f'</div>'
            )

        return "\n\n".join(parts)

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

    def should_inject_middle_card(self, content: str) -> bool:
        """H2가 3개 이상인지 확인."""
        count = len(re.findall(r"^##\s", content, re.MULTILINE))
        return count >= 3

    def inject_middle_card(self, content: str, card_html: str) -> str:
        """2번째 H2 직후에 중간 카드 삽입."""
        h2_positions = [
            m.start() for m in re.finditer(r"^##\s", content, re.MULTILINE)
        ]
        if len(h2_positions) < 2:
            return content
        insert_at = h2_positions[1]
        next_section = content[insert_at:]
        next_h2 = re.search(r"\n##\s", next_section[3:])
        if next_h2:
            section_end = insert_at + 3 + next_h2.start()
        else:
            section_end = len(content)
        before = content[:section_end].rstrip()
        after = content[section_end:]
        return before + "\n\n" + card_html + "\n" + after

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
            # Depth 2: 외부 링크 카드 (공신력 우선순위)
            links = self.find_external_links(
                title=post_title, keyword=post_keyword, seed=seed_keyword
            )
            external_card = self.build_external_link_card(links, seed_keyword=seed_keyword)
            if external_card:
                body = self.inject_bottom_card(body, external_card)
        else:
            # Depth 0/1: 다음 글 카드
            cta = self.get_cta(blog_key, direction)
            next_card = self.build_card_html(next_title, next_url, cta)
            body = self.inject_bottom_card(body, next_card)
            if self.should_inject_middle_card(body):
                middle_card = self.build_card_html(next_title, next_url, cta)
                body = self.inject_middle_card(body, middle_card)

            # 공식 안내 링크 카드 (Depth 0/1도 마지막에)
            official_link = self.find_official_link(post_title, post_keyword, body)
            official_card = self.build_official_card_html(official_link)
            if official_card:
                body = self.inject_bottom_card(body, official_card)

        return fm + "\n\n" + body if fm else body

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
    """Dual CTA (정보성 + 전환성) 카드 주입. Blowfish-compatible Tailwind HTML."""

    def __init__(self, config: dict = None):
        self.config = config or load_config()
        loop_cfg = self.config.get("loop", {})
        cta_cfg = loop_cfg.get("cta", {})
        self.info_cta_text = cta_cfg.get("info_cta_text", "관련 글 모두 보기 →")
        self.conv_cta_text = cta_cfg.get("conv_cta_text", "추천 상품 보기 →")
        self.conv_cta_url = cta_cfg.get("conv_cta_url", "")

    # ── HTML 생성 ──────────────────────────────────────────

    def build_dual_cta_html(
        self,
        hub_url: str,
        hub_title: str,
        conv_cta_url: str = None,
    ) -> str:
        """Dual CTA shortcode."""
        conv_url = conv_cta_url if conv_cta_url else self.conv_cta_url
        if not conv_url:
            conv_url = "#"
        return (
            f'{{{{< dual-cta '
            f'hub_url="{hub_url}" '
            f'hub_title="{hub_title}" '
            f'info_url="{hub_url}" '
            f'info_title="이 시리즈 전체 보기" '
            f'info_desc="이 시리즈의 모든 글을 한곳에서 확인하세요." '
            f'info_cta="시리즈 보기 →" '
            f'conv_url="{conv_url}" '
            f'conv_title="추천 상품" '
            f'conv_desc="이 주제와 관련된 추천 상품을 확인해보세요." '
            f'conv_cta="상품 보기 →" >}}}}'
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
