"""
chain_card_injector.py — 발행된 체인 포스트에 카드 후처리 삽입 (Phase 5)

카드 삽입 규칙 (정규화, AI 임의 결정 금지):
  - 하단 Next 카드: 모든 글 기본 삽입 (본문 마지막 H2 섹션 이후)
  - 중간 관련 카드: H2가 3개 이상일 때 2번째 H2 직후 1개 삽입
  - 상단: 카드 금지 (광고 전용 영역)
  - CTA 문구: chain_config.yaml의 blog별 card_cta 블록에서 읽기

Phase 5 변경:
  - Hugo HTML injection path 제거 → draft_md (DB 저장된 마크다운) 기반으로 변경
  - 카드 주입 후 PublisherCore.update_post_content()로 재발행 (Hugo: 전체 파이프라인 / Blogger: API update)
  - 카드 HTML은 마크다운 내에 raw HTML로 삽입 (Hugo가 통과시킴)
"""

import re
import os
import json
from datetime import datetime

from mc_paths import load_config, CHAIN_CONFIG_PATH
from chain_db import get_post
from search_retriever import NaverSearchClient


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

    def find_official_link(self, title: str = "", keyword: str = "", body: str = "") -> dict | None:
        """Naver 검색으로 공신력 있는 공식 사이트 1개 찾기.
        공공기관 도메인 우선, 블로그/뉴스/하위페이지는 제외.
        """
        search_text = keyword or title
        if not search_text:
            return None
        public_domains = (".go.kr", ".or.kr", ".gov.kr", ".co.kr")
        skip_domains = (
            "naver.com", "blog.naver.com", "brunch.co.kr", "tistory.com",
            "velog.io", "medium.com", "news.naver.com", "dispatch.co.kr",
        )
        skip_paths = (
            "/board/", "/faq", "/customer", "/bbs/", "/menu/",
            "/cruiseinfo/", "/useinfo/", "/terms/", "/?type=",
        )
        for template in self.OFFICIAL_QUERY_TEMPLATES:
            query = template.format(keyword=search_text)
            ok, data = self.search_client.search(query, endpoint="webkr", display=10)
            if not ok:
                continue
            try:
                results = json.loads(data).get("items", [])
                public_first = None
                fallback = None
                for item in results:
                    link = item.get("link", "")
                    domain = self._domain(link)
                    if any(sk in domain for sk in skip_domains):
                        continue
                    if any(s in link for s in skip_paths):
                        continue
                    clean_title = item.get("title", "").replace("<b>", "").replace("</b>", "")
                    clean_desc = item.get("description", "").replace("<b>", "").replace("</b>", "")[:60]
                    entry = {
                        "title": f"공식 {clean_title[:30]}" if clean_title else "공식 안내",
                        "url": link,
                        "label": clean_desc or domain,
                    }
                    if any(domain.endswith(d) for d in public_domains):
                        return entry
                    if fallback is None:
                        fallback = entry
                if fallback:
                    return fallback
            except json.JSONDecodeError:
                continue
        return None

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
    ) -> str:
        """
        draft_md (frontmatter + body)에 다음 글 카드 + 공식 안내 링크 카드 주입.
        frontmatter 보존, body에만 카드 삽입.

        삽입 순서 (하단에서 위로):
          1. 공식 안내 링크 카드 (맨 마지막)
          2. 다음 글 카드 (공식 카드 위)
          3. 중간 관련 카드 (H2 >= 3일 때 2번째 H2 직후)
        """
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

        cta = self.get_cta(blog_key, direction)
        next_card = self.build_card_html(next_title, next_url, cta)
        body = self.inject_bottom_card(body, next_card)
        if self.should_inject_middle_card(body):
            middle_card = self.build_card_html(
                next_title, next_url, cta
            )
            body = self.inject_middle_card(body, middle_card)

        # 공식 안내 링크 카드 (맨 마지막)
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
    ) -> bool:
        """
        DB에서 published_md(또는 draft_md fallback) 조회 → 카드 주입 → 기존 frontmatter 보존 후 파일 업데이트.
        published_md가 있으면 R2 URL이 포함된 버전을 사용 (본문 이미지 깨짐 방지).
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
