"""
chain_card_injector.py — 발행된 체인 포스트에 카드 후처리 삽입 (Phase 3)

카드 삽입 규칙 (정규화, AI 임의 결정 금지):
  - 하단 Next 카드: 모든 글 기본 삽입 (본문 마지막 H2 섹션 이후)
  - 중간 관련 카드: H2가 3개 이상일 때 2번째 H2 직후 1개 삽입
  - 상단: 카드 금지 (광고 전용 영역)
  - CTA 문구: chain_config.yaml의 blog별 card_cta 블록에서 읽기

사용 흐름:
  1. Step 3→2→1 역순 발행 → 모든 published_url 확보
  2. Step 1→2 정순 순회 → inject_cards(post[n], post[n+1])
  3. Hugo: 로컬 MD 파일 수정 + git push
  4. Blogger: API update_post()
"""

import re
import os

from mc_paths import load_config, CHAIN_CONFIG_PATH


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

    # ── 메인 진입점 ──────────────────────────────────────────

    def inject_cards(
        self,
        content: str,
        next_title: str,
        next_url: str,
        blog_key: str,
        direction: str,
    ) -> str:
        """content 에 next_post 카드 주입."""
        cta = self.get_cta(blog_key, direction)
        card_html = self.build_card_html(next_title, next_url, cta)
        content = self.inject_bottom_card(content, card_html)
        if self.should_inject_middle_card(content):
            middle_card_html = self.build_card_html(
                next_title, next_url, cta + " (관련)"
            )
            content = self.inject_middle_card(content, middle_card_html)
        return content

    # ── Hugo 파일 업데이트 ────────────────────────────────────

    def inject_into_hugo_file(self, file_path: str, *args, **kwargs) -> bool:
        """Hugo 마크다운 파일 직접 수정."""
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        updated = self.inject_cards(content, *args, **kwargs)
        if updated == content:
            return False
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated)
        return True
