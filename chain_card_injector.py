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
from datetime import datetime

from mc_paths import load_config, CHAIN_CONFIG_PATH
from chain_db import get_post


class CardInjector:
    def __init__(self, config: dict = None):
        self.config = config or load_config()

    # ── CTA 조회 ──────────────────────────────────────────────

    def get_cta(self, blog_key: str, direction: str) -> str:
        """블로그별 + 방향별 CTA 문구. 없으면 기본값."""
        site = self.config.get("sites", {}).get(blog_key, {})
        cta_map = site.get("card_cta", {})
        return cta_map.get(direction, "계속 읽기 →")

    # ── 카드 HTML 생성 ────────────────────────────────────────

    def build_card_html(self, title: str, url: str, cta: str) -> str:
        """Hugo-compatible card HTML."""
        return (
            '<div style="padding:1em;margin:2em 0;border:1px solid #ddd;'
            'border-radius:8px;background:#fafafa;text-align:center;">\n'
            f'  <p style="font-size:0.9em;color:#666;">다음 글</p>\n'
            f'  <p style="font-size:1.1em;font-weight:bold;">{title}</p>\n'
            f'  <a href="{url}" style="display:inline-block;padding:0.5em 1.5em;'
            f'background:#333;color:#fff;border-radius:4px;text-decoration:none;">'
            f'{cta}</a>\n'
            "</div>"
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
    ) -> str:
        """
        draft_md (frontmatter + body)에 next_post 카드 주입.
        frontmatter 보존, body에만 카드 삽입.
        """
        # frontmatter 분리
        if draft_md.startswith("---"):
            end = draft_md.find("---", 3)
            if end != -1:
                fm = draft_md[:end + 3]
                body = draft_md[end + 3:].lstrip()
            else:
                fm = ""
                body = draft_md
        else:
            fm = ""
            body = draft_md

        cta = self.get_cta(blog_key, direction)
        card_html = self.build_card_html(next_title, next_url, cta)
        body = self.inject_bottom_card(body, card_html)
        if self.should_inject_middle_card(body):
            middle_card_html = self.build_card_html(
                next_title, next_url, cta + " (관련)"
            )
            body = self.inject_middle_card(body, middle_card_html)

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
        DB에서 draft_md 조회 → 카드 주입 → PublisherCore.update_post_content 호출.
        """
        post = get_post(post_id)
        if not post or not post.get("draft_md"):
            return False

        updated_md = self.inject_cards_into_draft(
            post["draft_md"], next_title, next_url, blog_key, direction
        )

        # 발행된 글 업데이트 (Hugo: 파일 수정+push / Blogger: API)
        hugo_file = post.get("hugo_file_path")
        publisher_core.update_post_content(
            blog_key,
            hugo_file or post_id,
            updated_md,
            is_html=False,
        )
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
        """Blowfish-tailwind dual CTA card HTML."""
        conv_url = conv_cta_url if conv_cta_url else self.conv_cta_url
        if not conv_url:
            conv_url = "#"

        return (
            '<div class="max-w-2xl mx-auto my-8 p-6 bg-neutral-50 dark:bg-neutral-800 '
            'rounded-xl border border-neutral-200 dark:border-neutral-700">\n'
            '  <p class="text-lg font-semibold mb-2">이 시리즈 전체 보기</p>\n'
            f'  <p class="text-sm text-neutral-600 dark:text-neutral-400 mb-4">'
            f'{hub_title} 시리즈의 모든 글을 한곳에서 확인하세요.</p>\n'
            f'  <a href="{hub_url}" '
            'class="inline-block w-full text-center px-4 py-3 '
            'bg-neutral-800 dark:bg-neutral-100 text-white dark:text-neutral-800 '
            'rounded-lg font-medium hover:opacity-90 transition-opacity">\n'
            f'    {self.info_cta_text}\n'
            '  </a>\n'
            '\n'
            '  <div class="relative my-4">\n'
            '    <div class="absolute inset-0 flex items-center">'
            '<div class="w-full border-t border-neutral-300 dark:border-neutral-600">'
            '</div></div>\n'
            '    <div class="relative flex justify-center">'
            '<span class="bg-neutral-50 dark:bg-neutral-800 px-3 text-sm text-neutral-500">'
            '또는</span></div>\n'
            '  </div>\n'
            '\n'
            '  <p class="text-lg font-semibold mb-2">추천 상품</p>\n'
            '  <p class="text-sm text-neutral-600 dark:text-neutral-400 mb-4">'
            '이 주제와 관련된 추천 상품을 확인해보세요.</p>\n'
            f'  <a href="{conv_url}" '
            'class="inline-block w-full text-center px-4 py-3 '
            'bg-amber-600 text-white rounded-lg font-medium '
            'hover:bg-amber-700 transition-colors">\n'
            f'    {self.conv_cta_text}\n'
            '  </a>\n'
            "</div>"
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
