"""
chain_publisher_core.py — 발행 코어 (Phase 3)

draft_md를 실제 사이트에 발행하고 published_url 반환.
blog_key의 publisher_type에 따라 Hugo/Blogger/Manual 분기 처리.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from mc_paths import ensure_5000_on_path, load_config, CHAIN_CONFIG_PATH

ensure_5000_on_path()

from shared.publishers.hugo_writer import _write_hugo_post


class PublisherCore:
    def __init__(self, config: dict = None):
        self.config = config or load_config()
        self._blogger_clients = {}

    # ── Blog lookup ─────────────────────────────────────────

    def get_blog(self, blog_key: str) -> dict:
        site = self.config.get("sites", {}).get(blog_key)
        if not site:
            raise KeyError(f"Unknown blog_key: {blog_key}")
        return site

    # ── Main entry ──────────────────────────────────────────

    def publish_post(
        self,
        blog_key: str,
        draft_md: str,
        slug: str,
        title: str,
        labels: list = None,
        chain_type: str = "depth",
    ) -> tuple:
        """
        blog_key의 publisher_type에 따라 분기.
        Returns: (published_url, publish_method)
        """
        blog_cfg = self.get_blog(blog_key)
        ptype = blog_cfg.get("publisher_type", "manual")

        if ptype == "hugo":
            return self._publish_hugo(blog_cfg, draft_md, slug, title)
        elif ptype == "blogger":
            return self._publish_blogger(blog_cfg, draft_md, title, labels)
        else:
            return self._publish_manual(blog_cfg, draft_md, slug, title)

    # ── Hugo publish ────────────────────────────────────────

    def _publish_hugo(
        self, blog_cfg: dict, draft_md: str, slug: str, title: str
    ) -> tuple:
        """Hugo 사이트에 마크다운 파일 작성."""
        result = _write_hugo_post(
            blog_cfg={
                "site_path": blog_cfg["hugo_root"],
                "blog_id": blog_cfg["blog_id"],
            },
            title=title,
            body_md=draft_md,
            slug=slug,
            category="일반",
            tags=[title],
            thumbnail_url=None,
            is_draft=False,
        )
        if result.get("success"):
            hugo_path = result.get("file", "")
            self._git_push(blog_cfg["hugo_root"])
            rel_path = os.path.relpath(hugo_path, blog_cfg["hugo_root"])
            url = f"{blog_cfg['base_url']}/{rel_path.replace(os.sep, '/')}"
            return (url, "hugo")
        return ("", "hugo")

    # ── Blogger publish ─────────────────────────────────────

    def _publish_blogger(
        self, blog_cfg: dict, draft_md: str, title: str, labels: list = None
    ) -> tuple:
        """Blogger API로 발행. 마크다운→HTML 변환 후 API 호출."""
        html = self._md_to_html(draft_md)
        client = self._get_blogger_client()
        url = client.publish_post(
            blog_id=blog_cfg["blog_id"],
            title=title,
            html_content=html,
            labels=labels or [],
            is_draft=False,
        )
        return (url, "blogger")

    # ── Manual publish ──────────────────────────────────────

    def _publish_manual(
        self, blog_cfg: dict, draft_md: str, slug: str, title: str
    ) -> tuple:
        """수동 발행: HTML 파일 저장 + 클립보드 복사 + URL 입력 대기."""
        html = self._md_to_html(draft_md)
        manual_dir = Path(__file__).resolve().parent / "output" / "manual"
        manual_dir.mkdir(parents=True, exist_ok=True)
        output_path = manual_dir / f"{slug}.html"
        output_path.write_text(html, encoding="utf-8")

        # macOS pbcopy
        try:
            proc = subprocess.Popen(
                ["pbcopy"], stdin=subprocess.PIPE, text=True
            )
            proc.communicate(input=html)
            print(f"  [publisher] 📋 HTML copied to clipboard: {output_path}")
        except FileNotFoundError:
            print(f"  [publisher] 📄 HTML saved to: {output_path}")

        url = input("  [publisher] 발행된 URL 입력: ").strip()
        return (url, "manual")

    # ── Content update (카드 주입용) ─────────────────────────

    def update_post_content(
        self,
        blog_key: str,
        post_id_or_path: str,
        new_content: str,
        is_html: bool = False,
    ):
        """발행된 글 본문 업데이트."""
        blog_cfg = self.get_blog(blog_key)
        ptype = blog_cfg.get("publisher_type", "manual")

        if ptype == "hugo":
            hugo_file = blog_cfg.get("hugo_file_path") or post_id_or_path
            if os.path.exists(hugo_file):
                with open(hugo_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                self._git_push(blog_cfg["hugo_root"])
        elif ptype == "blogger":
            html = new_content if is_html else self._md_to_html(new_content)
            client = self._get_blogger_client()
            client.update_post(blog_cfg["blog_id"], post_id_or_path, html)

    # ── Helpers ─────────────────────────────────────────────

    def _md_to_html(self, md: str) -> str:
        """마크다운 → HTML 변환."""
        import markdown

        return markdown.markdown(
            md, extensions=["extra", "codehilite", "toc"]
        )

    def _get_blogger_client(self):
        """BloggerClient lazy singleton (blog_id별 캐싱)."""
        from shared.publishers.blogger_client import BloggerClient

        if "_default" not in self._blogger_clients:
            self._blogger_clients["_default"] = BloggerClient()
        return self._blogger_clients["_default"]

    def _git_push(self, repo_path: str):
        """Hugo 사이트 git add/commit/push."""
        try:
            subprocess.run(
                ["git", "-C", repo_path, "add", "-A"],
                capture_output=True, timeout=30, check=False,
            )
            subprocess.run(
                ["git", "-C", repo_path, "commit", "-m", "mc: auto-publish"],
                capture_output=True, timeout=30, check=False,
            )
            subprocess.run(
                ["git", "-C", repo_path, "push"],
                capture_output=True, timeout=60, check=False,
            )
        except subprocess.TimeoutExpired:
            print("  [publisher] ⚠️ git push timeout")
        except Exception as e:
            print(f"  [publisher] ⚠️ git push error: {e}")
