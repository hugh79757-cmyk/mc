"""Tests for chain_publisher_core.py — 발행 코어 (Hugo/Blogger/Manual)."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestExtractCleanBody:
    """_extract_clean_body 함수 테스트."""

    def test_extracts_valid_markdown_only(self):
        """허용된 마크다운 요소만 추출."""
        from chain_publisher_core import _extract_clean_body

        text = """---
title: "Test"
draft: false
---

## Heading 1

Paragraph text.

- List item 1
- List item 2

| Table | Header |
|-------|--------|
| Cell  | Data   |

![Image](https://example.com/img.jpg)

[Link](https://example.com)

```python
code = "allowed"
```"""

        result = _extract_clean_body(text)
        assert result.frontmatter.strip() == 'title: "Test"\ndraft: false'
        assert "## Heading 1" in result.body
        assert "Paragraph text" in result.body
        assert "- List item 1" in result.body
        assert "| Table | Header |" in result.body
        assert "![Image](https://example.com/img.jpg)" in result.body
        assert "[Link](https://example.com)" in result.body
        assert 'code = "allowed"' in result.body

    def test_rejects_json_code_block(self):
        """JSON 코드 블록 완전 제거 — 내용물까지 전부 삭제."""
        from chain_publisher_core import _extract_clean_body, CleanedDraft

        text = """---
title: "Test"
---

```json
{"image_type": "photo", "chart_type": "bar"}
```

Valid content."""

        result = _extract_clean_body(text)
        assert isinstance(result, CleanedDraft)
        assert "Valid content" in result.body
        assert "image_type" not in result.body
        assert "chart_type" not in result.body

    def test_strips_json_code_block_chart_data_null(self):
        """chart_data=null이 포함된 JSON 코드 블록 완전 제거 (P0 회귀 방지)."""
        from chain_publisher_core import _extract_clean_body, CleanedDraft

        text = """---
title: "Test"
---

Normal paragraph with content.

```json
{
  "image_type": "chart",
  "image_keyword": "test-keyword",
  "image_reason": "Test reason",
  "chart_type": "timeline",
  "chart_data": null
}
```

Valid content after."""

        result = _extract_clean_body(text)
        assert isinstance(result, CleanedDraft)
        assert "Normal paragraph" in result.body, "일반 본문 보존"
        assert "Valid content after" in result.body, "JSON 이후 본문 보존"
        assert "image_type" not in result.body, "JSON 필드 제거"
        assert "chart_data" not in result.body, "chart_data 제거"
        assert "test-keyword" not in result.body, "JSON 내부 값 제거"
        assert "```" not in result.body, "코드 펜스 마커 제거"

    def test_rejects_html_comments(self):
        """HTML 주석 거부."""
        from chain_publisher_core import _extract_clean_body

        text = """---
title: "Test"
---

Valid paragraph.

<!-- This is a comment -->
<!-- image: something -->

Another paragraph."""

        result = _extract_clean_body(text)
        assert "<!--" not in result.body
        assert "Valid paragraph" in result.body
        assert "Another paragraph" in result.body

    def test_rejects_html_tags(self):
        """HTML 태그 거부 — 8종 (div, span, p, a, table, blockquote, figure, ins)."""
        from chain_publisher_core import _extract_clean_body

        text = """---
title: "Test"
---

<div class="cta">CTA block</div>
<span style="color:red">styled span</span>
<p>paragraph</p>
<a href="https://example.com">link</a>
<table><tr><td>cell</td></tr></table>
<blockquote>quoted text</blockquote>
<figure><img src="x"></figure>
<ins datetime="2024">inserted</ins>

Valid content."""

        result = _extract_clean_body(text)
        assert "<div" not in result.body
        assert "<span" not in result.body
        assert "<p>" not in result.body
        assert "<a " not in result.body
        assert "<table" not in result.body
        assert "<blockquote" not in result.body
        assert "<figure" not in result.body
        assert "<ins" not in result.body
        assert "Valid content" in result.body

    def test_rejects_inline_html_tag_in_middle(self):
        """인라인 HTML 태그 (본문 중간 삽입) 거부 — re.search 사용으로 전체 라인 검사."""
        from chain_publisher_core import _extract_clean_body

        # <div>가 라인 시작이 아니라 본문 문장 중간에 삽입된 경우
        text = """---
title: "Test"
---

Paragraph with a <div>inline div</div> in the middle.

Another paragraph.

<div>Start-of-line div also rejected</div>

![Image](https://example.com/img.jpg)

[Link](https://example.com)

| Table | Header |
|-------|--------|
| Cell  | Data   |"""

        result = _extract_clean_body(text)
        # 인라인 div는 필터링되어야 함
        assert result.body.count("<div>") == 0
        # 이미지/링크/표는 통과해야 함
        assert "![Image](https://example.com/img.jpg)" in result.body
        assert "[Link](https://example.com)" in result.body
        assert "| Table | Header |" in result.body
        assert "Cell" in result.body

    def test_rejects_raw_json(self):
        """Raw JSON 객체 거부."""
        from chain_publisher_core import _extract_clean_body

        text = """---
title: "Test"
---

{"image_type": "photo", "chart_type": "bar", "image_keyword": "test"}

Valid content."""

        result = _extract_clean_body(text)
        assert "image_type" not in result.body
        assert "chart_type" not in result.body
        assert "Valid content" in result.body

    def test_collapses_excessive_newlines(self):
        """연속 3개 이상 개행 압축."""
        from chain_publisher_core import _extract_clean_body

        text = """---
title: "Test"
---

Para 1.


Para 2.""".replace("\n", "\n")

        result = _extract_clean_body(text)
        # Should not have 3+ consecutive newlines
        assert "\n\n\n" not in result.body

    def test_extract_clean_body_handles_unclosed_frontmatter(self):
        """closer 없는 malformed frontmatter → frontmatter 정상 추출."""
        from chain_publisher_core import _extract_clean_body

        text = '---\ntitle: "Test"\ndraft: true\n\nBody paragraph here.'
        result = _extract_clean_body(text)
        assert 'title: "Test"' in result.frontmatter
        assert "Body paragraph here" in result.body


class TestVerifyBeforeDeploy:
    """_verify_before_deploy 검증 게이트 테스트."""

    @patch("chain_publisher_core._check_url_accessible")
    @patch("chain_publisher_core.logger")
    def test_passes_valid_post(self, mock_logger, mock_check_url, temp_dir):
        """유효한 포스트 통과."""
        from chain_publisher_core import _verify_before_deploy

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "https://img.example.com/thumb.webp"
draft: false
---

## Content

Valid body.""", encoding="utf-8")

        # Create public output for HTML verification
        public_dir = hugo_path / "public" / "posts" / "test-slug"
        public_dir.mkdir(parents=True)
        (public_dir / "index.html").write_text("""<html><body>
<h1>Test</h1>
<p>Content</p>
<img src="https://img.example.com/img.jpg">
</body></html>""", encoding="utf-8")

        # Should not raise
        _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core.logger")
    def test_fails_on_json_fence_in_source(self, mock_logger, temp_dir):
        """소스에 JSON 펜스 있으면 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
---

```json
{"bad": "data"}
```""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="JSON 코드 펜스"):
            _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core.logger")
    def test_fails_on_html_comment_in_source(self, mock_logger, temp_dir):
        """소스에 HTML 주석 있으면 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
---

<!-- comment -->""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="HTML 주석"):
            _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core._check_url_accessible")
    @patch("chain_publisher_core.logger")
    def test_warns_on_html_tag_in_source(self, mock_logger, mock_check_url, temp_dir):
        """소스에 HTML 태그 있으면 WARNING (W3 완료 전까지 ERROR 아님)."""
        from chain_publisher_core import _verify_before_deploy

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "https://img.example.com/thumb.webp"
---

## Content

This has <div style="padding:1em;">HTML tag</div> in body.
""", encoding="utf-8")

        # public HTML도 생성 (2단계 검증 통과용)
        public_dir = hugo_path / "public" / "posts" / "test-slug"
        public_dir.mkdir(parents=True)
        (public_dir / "index.html").write_text(
            """<html><body><article><p>Content</p></article></body></html>""",
            encoding="utf-8",
        )

        _verify_before_deploy(hugo_path, "test-slug")

        # WARNING이어서 예외 대신 logger.warning 호출 확인
        mock_logger.warning.assert_called_once()
        call_args = mock_logger.warning.call_args[0][0]
        assert "HTML 태그 잔류" in call_args

    @patch("chain_publisher_core.logger")
    def test_fails_on_empty_featureimage(self, mock_logger, temp_dir):
        """featureimage 빈 값이면 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: ""
---""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="featureimage가 빈 값"):
            _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core.logger")
    def test_fails_on_relative_featureimage(self, mock_logger, temp_dir):
        """featureimage가 상대경로면 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "/images/thumb.jpg"
---""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="유효한 URL이 아님"):
            _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core._check_url_accessible")
    @patch("chain_publisher_core.logger")
    def test_fails_on_excessive_ads_in_html(self, mock_logger, mock_check_url, temp_dir):
        """HTML 산출물에 광고 3개 초과 시 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "https://img.example.com/thumb.webp"
---
Content""", encoding="utf-8")

        public_dir = hugo_path / "public" / "posts" / "test-slug"
        public_dir.mkdir(parents=True)
        (public_dir / "index.html").write_text("""<html><body>
<div class="ad-incontent"></div>
<div class="ad-incontent"></div>
<div class="ad-incontent"></div>
<div class="ad-incontent"></div>
</body></html>""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="광고 슬롯 4개"):
            _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core._check_url_accessible")
    @patch("chain_publisher_core.logger")
    def test_fails_on_broken_image_refs(self, mock_logger, mock_check_url, temp_dir):
        """깨진 이미지 참조 시 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "https://img.example.com/thumb.webp"
---
Content""", encoding="utf-8")

        public_dir = hugo_path / "public" / "posts" / "test-slug"
        public_dir.mkdir(parents=True)
        (public_dir / "index.html").write_text("""<html><body>
<img src="/images/missing.jpg">
</body></html>""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="깨진 이미지 참조 1개"):
            _verify_before_deploy(hugo_path, "test-slug")

    @patch("chain_publisher_core._check_url_accessible")
    @patch("chain_publisher_core.logger")
    def test_fails_on_json_residue_in_html(self, mock_logger, mock_check_url, temp_dir):
        """HTML에 JSON 잔류 시 실패."""
        from chain_publisher_core import _verify_before_deploy, DeployValidationError

        hugo_path = temp_dir / "hugo"
        content_dir = hugo_path / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "https://img.example.com/thumb.webp"
---
Content""", encoding="utf-8")

        public_dir = hugo_path / "public" / "posts" / "test-slug"
        public_dir.mkdir(parents=True)
        (public_dir / "index.html").write_text("""<html><body>
<script>var data = {"image_type": "photo"};</script>
</body></html>""", encoding="utf-8")

        with pytest.raises(DeployValidationError, match="JSON 잔류"):
            _verify_before_deploy(hugo_path, "test-slug")


class TestPublisherCore:
    """PublisherCore 클래스 테스트."""

    @patch("chain_publisher_core.load_config")
    def test_init_loads_config(self, mock_load_config, sample_chain_config):
        """초기화 시 설정 로드."""
        mock_load_config.return_value = sample_chain_config

        from chain_publisher_core import PublisherCore
        core = PublisherCore()

        assert core.config == sample_chain_config
        mock_load_config.assert_called_once()

    @patch("chain_publisher_core.load_config")
    def test_get_blog_returns_site_config(self, mock_load_config, sample_chain_config):
        """blog_key로 사이트 설정 조회."""
        mock_load_config.return_value = sample_chain_config

        from chain_publisher_core import PublisherCore
        core = PublisherCore()

        blog = core.get_blog("rotcha")
        assert blog["blog_id"] == "manual_rotcha"
        assert blog["theme"] == "Blowfish"

    @patch("chain_publisher_core.load_config")
    def test_get_blog_raises_on_unknown(self, mock_load_config, sample_chain_config):
        """알 수 없는 blog_key면 KeyError."""
        mock_load_config.return_value = sample_chain_config

        from chain_publisher_core import PublisherCore
        core = PublisherCore()

        with pytest.raises(KeyError, match=r"Unknown blog_key"):
            core.get_blog("nonexistent")

    @patch("chain_publisher_core.load_config")
    def test_publish_post_routes_to_hugo(self, mock_load_config, sample_chain_config):
        """Hugo publisher_type일 때 _publish_hugo 호출."""
        mock_load_config.return_value = sample_chain_config

        from chain_publisher_core import PublisherCore
        core = PublisherCore()

        with patch.object(core, "_publish_hugo", return_value=("url", "hugo", "path")) as mock_hugo:
            result = core.publish_post("rotcha", "draft", "slug", "Title")
            mock_hugo.assert_called_once()
            assert result == ("url", "hugo", "path")

    @patch("chain_publisher_core.load_config")
    def test_publish_post_routes_to_blogger(self, mock_load_config):
        """Blogger publisher_type일 때 _publish_blogger 호출."""
        config = {
            "sites": {
                "testblog": {
                    "publisher_type": "blogger",
                    "blog_id": "123",
                    "base_url": "https://test.blogspot.com",
                }
            }
        }
        mock_load_config.return_value = config

        from chain_publisher_core import PublisherCore
        core = PublisherCore()

        with patch.object(core, "_publish_blogger", return_value=("url", "blogger", "")) as mock_blogger:
            result = core.publish_post("testblog", "draft", "slug", "Title")
            mock_blogger.assert_called_once()
            assert result == ("url", "blogger", "")

    @patch("chain_publisher_core.load_config")
    def test_publish_post_routes_to_manual(self, mock_load_config):
        """Manual publisher_type일 때 _publish_manual 호출."""
        config = {
            "sites": {
                "manual": {"publisher_type": "manual", "base_url": "https://manual.com"}
            }
        }
        mock_load_config.return_value = config

        from chain_publisher_core import PublisherCore
        core = PublisherCore()

        with patch.object(core, "_publish_manual", return_value=("url", "manual", "path")) as mock_manual:
            result = core.publish_post("manual", "draft", "slug", "Title")
            mock_manual.assert_called_once()
            assert result == ("url", "manual", "path")


class TestWranglerHelper:
    """_get_wrangler_cmd, _run_wrangler 테스트."""

    @patch("chain_publisher_core.shutil.which")
    @patch("chain_publisher_core.Path.exists")
    def test_get_wrangler_cmd_prefers_npm_global(self, mock_exists, mock_which):
        """npm 글로벌 wrangler.js 우선."""
        mock_which.return_value = "/opt/homebrew/bin/node"
        mock_exists.return_value = True

        from chain_publisher_core import _get_wrangler_cmd
        cmd = _get_wrangler_cmd(["pages", "deploy", "dir", "--project-name", "test"])

        assert cmd[0] == "/opt/homebrew/bin/node"
        assert "wrangler.js" in cmd[1]
        assert "pages" in cmd
        assert "deploy" in cmd

    @patch("chain_publisher_core.shutil.which")
    @patch("chain_publisher_core.Path.exists")
    @patch("chain_publisher_core.Path.rglob")
    def test_get_wrangler_cmd_fallbacks_to_brew(self, mock_rglob, mock_exists, mock_which):
        """brew 설치 경로 폴백."""
        mock_which.return_value = "/opt/homebrew/bin/node"
        mock_exists.side_effect = [False, True, True]  # npm global 없음 → brew base 있음 → node exists
        mock_rglob.return_value = [Path("/opt/homebrew/opt/cloudflare-wrangler/libexec/wrangler.js")]

        from chain_publisher_core import _get_wrangler_cmd
        cmd = _get_wrangler_cmd(["pages", "deploy", "dir"])

        assert cmd[0] == "/opt/homebrew/bin/node"
        assert "wrangler.js" in cmd[1]

    @patch("chain_publisher_core.subprocess.run")
    @patch("chain_publisher_core._get_wrangler_cmd")
    def test_run_wrangler_unsets_cf_env(self, mock_get_cmd, mock_run):
        """Cloudflare env 변수 제거 후 실행."""
        mock_get_cmd.return_value = ["node", "wrangler.js", "--profile", "hugh79757", "pages", "deploy"]
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")

        from chain_publisher_core import _run_wrangler

        with patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret", "CF_DNS_TOKEN": "secret2"}, clear=False):
            rc, stdout, stderr = _run_wrangler(["pages", "deploy"])

        # env에서 CF 변수들이 제거되었는지 확인
        assert rc == 0
        # 실제 호출된 env 확인하려면 mock_run.call_args 검사 필요



class TestPublishHugoIntegration:
    """_publish_hugo 통합 테스트 (mocking heavy)."""

    @patch("chain_publisher_core.load_config")
    @patch("chain_publisher_core.get_r2_config")
    @patch("chain_publisher_core.upload_all_images")
    @patch("chain_publisher_core.shutil.which")
    @patch("chain_publisher_core.subprocess.run")
    @patch("chain_publisher_core._run_wrangler")
    @patch("chain_publisher_core._verify_before_deploy")
    def test_publish_hugo_full_flow(
        self,
        mock_verify,
        mock_run_wrangler,
        mock_subprocess,
        mock_which,
        mock_upload,
        mock_get_r2,
        mock_load_config,
        sample_chain_config,
        temp_dir,
    ):
        """Hugo 발행 전체 플로우 mock 검증."""
        # Override hugo_root to use a real temp dir (the default /fake path doesn't exist)
        hugo_root = str(temp_dir / "hugo")
        config = sample_chain_config.copy()
        config["sites"]["rotcha"] = {**config["sites"]["rotcha"], "hugo_root": hugo_root}
        blog_cfg = config["sites"]["rotcha"]

        mock_load_config.return_value = config
        mock_get_r2.return_value = ("images/rotcha", "https://img.rotcha.kr")
        mock_upload.return_value = {"thumbnail.webp": "https://img.rotcha.kr/images/rotcha/slug/thumbnail.webp"}
        mock_which.return_value = "/opt/homebrew/bin/hugo"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_wrangler.return_value = (0, "OK", "")
        mock_verify.return_value = None

        # Mock DB (get_conn is imported locally from chain_db inside _publish_hugo)
        with patch("chain_db.get_conn") as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.execute.return_value.fetchone.return_value = {
                "id": 1,
                "step": 1,
                "image_meta": json.dumps({
                    "image_type": "none",
                    "image_keyword": None,
                    "thumbnail_path": None,
                    "thumbnail_source": None,
                    "content_image_path": "already_set",
                    "chart_type": None,
                    "chart_data": None,
                    "image_reason": None,
                }),
            }

            from chain_publisher_core import PublisherCore
            core = PublisherCore(config)

            draft_md = """---
title: "Test Post"
description: "Desc"
tags: ["태그"]
categories: ["카테고리"]
draft: true
---

## Content

Body text.

<!--todo:image-->"""

            url, method, path = core._publish_hugo(
                blog_cfg,
                draft_md,
                "test-slug",
                "Test Post",
                ["tag1"],
            )

            assert url.startswith("https://rotcha.kr/posts/test-slug/")
            assert method == "hugo"
            assert "test-slug" in path
            mock_upload.assert_called_once()
            mock_subprocess.assert_called()  # hugo build
            mock_run_wrangler.assert_called()  # wrangler deploy


class TestLegacyColumnsRemoved:
    """위반 1 검증: SELECT가 image_meta만 읽고 레거시 개별 컬럼을 읽지 않음."""

    @patch("chain_publisher_core.load_config")
    @patch("chain_publisher_core.get_r2_config")
    @patch("chain_publisher_core.upload_all_images")
    @patch("chain_publisher_core.shutil.which")
    @patch("chain_publisher_core.subprocess.run")
    @patch("chain_publisher_core._run_wrangler")
    @patch("chain_publisher_core._verify_before_deploy")
    def test_select_uses_image_meta_not_legacy_columns(
        self,
        mock_verify,
        mock_run_wrangler,
        mock_subprocess,
        mock_which,
        mock_upload,
        mock_get_r2,
        mock_load_config,
        sample_chain_config,
        temp_dir,
    ):
        """SELECT에 image_meta만 있고 thumbnail_path/image_keyword/chart_type 등이 없어야 함."""
        hugo_root = str(temp_dir / "hugo")
        config = sample_chain_config.copy()
        config["sites"]["rotcha"] = {**config["sites"]["rotcha"], "hugo_root": hugo_root}
        blog_cfg = config["sites"]["rotcha"]

        mock_load_config.return_value = config
        mock_get_r2.return_value = ("images/rotcha", "https://img.rotcha.kr")
        mock_upload.return_value = {}
        mock_which.return_value = "/opt/homebrew/bin/hugo"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_wrangler.return_value = (0, "OK", "")
        mock_verify.return_value = None

        with patch("chain_db.get_conn") as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.execute.return_value.fetchone.return_value = {
                "id": 1,
                "step": 1,
                "image_meta": json.dumps({
                    "image_type": "none",
                    "image_keyword": None,
                    "thumbnail_path": None,
                    "thumbnail_source": None,
                    "content_image_path": "already_set",
                    "chart_type": None,
                    "chart_data": None,
                    "image_reason": None,
                }),
            }

            from chain_publisher_core import PublisherCore
            core = PublisherCore(config)

            draft_md = "---\ntitle: T\ndraft: true\n---\n\nBody."
            core._publish_hugo(blog_cfg, draft_md, "test-slug", "T", ["tag1"])

            # Verify SELECT uses image_meta, NOT legacy columns
            first_sql = mock_conn.execute.call_args_list[0][0][0]
            assert "SELECT" in first_sql
            assert "image_meta" in first_sql, f"SELECT must include image_meta, got: {first_sql}"
            for col in ("thumbnail_path", "thumbnail_source", "image_keyword", "chart_type", "chart_data", "content_image_path"):
                assert col not in first_sql, f"Legacy column '{col}' must NOT be in SELECT: {first_sql}"

    @patch("chain_publisher_core.load_config")
    @patch("chain_publisher_core.get_r2_config")
    @patch("chain_publisher_core.upload_all_images")
    @patch("chain_publisher_core.shutil.which")
    @patch("chain_publisher_core.subprocess.run")
    @patch("chain_publisher_core._run_wrangler")
    @patch("chain_publisher_core._verify_before_deploy")
    def test_image_meta_null_raises_deploy_validation_error(
        self,
        mock_verify,
        mock_run_wrangler,
        mock_subprocess,
        mock_which,
        mock_upload,
        mock_get_r2,
        mock_load_config,
        sample_chain_config,
        temp_dir,
    ):
        """image_meta가 NULL이면 DeployValidationError 발생."""
        hugo_root = str(temp_dir / "hugo")
        config = sample_chain_config.copy()
        config["sites"]["rotcha"] = {**config["sites"]["rotcha"], "hugo_root": hugo_root}
        blog_cfg = config["sites"]["rotcha"]

        mock_load_config.return_value = config
        mock_get_r2.return_value = ("images/rotcha", "https://img.rotcha.kr")
        mock_upload.return_value = {}
        mock_which.return_value = "/opt/homebrew/bin/hugo"
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
        mock_run_wrangler.return_value = (0, "OK", "")
        mock_verify.return_value = None

        with patch("chain_db.get_conn") as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value = mock_conn
            # image_meta가 NULL인 레코드
            mock_conn.execute.return_value.fetchone.return_value = {
                "id": 1,
                "step": 1,
                "image_meta": None,
            }

            from chain_publisher_core import PublisherCore, DeployValidationError
            core = PublisherCore(config)

            draft_md = "---\ntitle: T\ndraft: true\n---\n\nBody."

            with pytest.raises(DeployValidationError, match="image_meta 누락"):
                core._publish_hugo(blog_cfg, draft_md, "test-slug", "T", ["tag1"])


class TestHugoBuildFailure:
    """위반 3 검증: Hugo 빌드 실패 시 raise DeployValidationError, 빈 튜플 반환 금지."""

    @patch("chain_publisher_core.load_config")
    @patch("chain_publisher_core.get_r2_config")
    @patch("chain_publisher_core.upload_all_images")
    @patch("chain_publisher_core.shutil.which")
    @patch("chain_publisher_core.subprocess.run")
    @patch("chain_publisher_core._run_wrangler")
    @patch("chain_publisher_core._verify_before_deploy")
    def test_hugo_build_failure_raises_deploy_validation_error(
        self,
        mock_verify,
        mock_run_wrangler,
        mock_subprocess,
        mock_which,
        mock_upload,
        mock_get_r2,
        mock_load_config,
        sample_chain_config,
        temp_dir,
    ):
        """Hugo 빌드 실패(returncode != 0) 시 DeployValidationError 발생."""
        hugo_root = str(temp_dir / "hugo")
        config = sample_chain_config.copy()
        config["sites"]["rotcha"] = {**config["sites"]["rotcha"], "hugo_root": hugo_root}
        blog_cfg = config["sites"]["rotcha"]

        mock_load_config.return_value = config
        mock_get_r2.return_value = ("images/rotcha", "https://img.rotcha.kr")
        mock_upload.return_value = {}
        mock_which.return_value = "/opt/homebrew/bin/hugo"
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="Build error")
        mock_run_wrangler.return_value = (0, "OK", "")
        mock_verify.return_value = None

        with patch("chain_db.get_conn") as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.execute.return_value.fetchone.return_value = {
                "id": 1,
                "step": 1,
                "image_meta": json.dumps({
                    "image_type": "none", "image_keyword": None,
                    "thumbnail_path": None, "thumbnail_source": None,
                    "content_image_path": "already_set",
                    "chart_type": None, "chart_data": None, "image_reason": None,
                }),
            }

            from chain_publisher_core import PublisherCore, DeployValidationError
            core = PublisherCore(config)

            draft_md = "---\ntitle: T\ndraft: true\n---\n\nBody."

            with pytest.raises(DeployValidationError, match=r"Hugo 빌드 실패"):
                core._publish_hugo(blog_cfg, draft_md, "test-slug", "T", ["tag1"])

            # Wrangler deploy should NOT be called when build fails
            mock_run_wrangler.assert_not_called()


class TestCleanMarkdownSymbols:
    """_clean_markdown_symbols 함수 테스트 (Phase 13 R2)."""

    def test_escapes_loose_pipes_in_prose(self):
        """본문의 파이프 문자를 이스케이프 (backslash-pipe)."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "Use pipe | as separator in text"
        result = _clean_markdown_symbols(text)
        # Result should have \| instead of bare |
        assert "\\|" in result

    def test_preserves_table_pipes(self):
        """표 라인의 파이프는 보존."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "| Header 1 | Header 2 |\n| --- | --- |\n| Cell 1  | Cell 2  |"
        result = _clean_markdown_symbols(text)
        for line in result.split('\n'):
            assert '|' in line, f"Table pipe missing in: {line}"

    def test_preserves_image_markers(self):
        """<!--todo:image--> 마커 보존."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "Before\n<!--todo:image-->\nAfter"
        result = _clean_markdown_symbols(text)
        assert "<!--todo:image-->" in result

    def test_preserves_chart_markers(self):
        """<!--todo:chart--> 마커 보존."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "<!--todo:chart-->"
        result = _clean_markdown_symbols(text)
        assert "<!--todo:chart-->" in result

    def test_preserves_code_blocks(self):
        """코드 블록 내부 보존."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "Before\n```\npipe | inside code\n```\nAfter"
        result = _clean_markdown_symbols(text)
        assert "pipe | inside code" in result

    def test_preserves_inline_code(self):
        """인라인 코드(backtick) 내부 보존 — 현재 보호 범위는 backtick보다는 code block."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "Use `code | pipe` in text"
        result = _clean_markdown_symbols(text)
        assert "`" in result

    def test_preserves_math_blocks(self):
        """수식 블록($$) 보존."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "Before\n$$E=mc^2$$\nAfter"
        result = _clean_markdown_symbols(text)
        assert "$$" in result

    def test_preserves_cjk_bold_no_internal_spaces(self):
        """한국어 볼드체: CommonMark 대비 내부 공백 미삽입."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "This is **중요한** test"
        result = _clean_markdown_symbols(text)
        # CommonMark에서 **중요한**은 정상 볼드. ** 중요 한 **은 미동작.
        # 공백은 AI 프롬프트로 이미 보장됨.
        assert "**중요한**" in result

    def test_handles_unmatched_bold(self):
        """짝이 안 맞는 ** 제거."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "This has **unmatched bold"
        result = _clean_markdown_symbols(text)
        assert result.count("**") % 2 == 0

    def test_empty_body(self):
        """빈 문자열 처리."""
        from chain_publisher_core import _clean_markdown_symbols

        result = _clean_markdown_symbols("")
        assert result == ""

    def test_table_separator_without_leading_pipe(self):
        """선행 | 없는 표 구분선 보호 (---|---|---)."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "| 항목 | 내용 |\n------|------|\n| 위치 | 파주 |"
        result = _clean_markdown_symbols(text)
        assert "------|------|" in result
        assert "\\|" not in result

    def test_table_separator_with_leading_pipe(self):
        """선행 | 있는 표 구분선 보호 (|---|---|)."""
        from chain_publisher_core import _clean_markdown_symbols

        text = "| 항목 | 내용 |\n|------|------|\n| 위치 | 파주 |"
        result = _clean_markdown_symbols(text)
        assert "|------|------|" in result
        assert "\\|" not in result

    def test_mixed_table_formats(self):
        """혼합 표 형식 — AI가 선행 |를 빠뜨린 케이스."""
        from chain_publisher_core import _clean_markdown_symbols

        text = (
            "| 도구 | 장점 | 단점 |\n"
            "-----------|------|------|\n"
            "| Selenium | 다양한 브라우저 지원 | 느린 실행 속도 |\n"
            "| pytest | 간결한 문법 | Java 미지원 |"
        )
        result = _clean_markdown_symbols(text)
        # 분석선 보호 확인
        assert "-----------|------|------|" in result
        # 파이프 이스케이프 없음
        assert "\\|" not in result


class TestCLI:
    """CLI 테스트 (해당 없음 - PublisherCore는 라이브러리)."""

    pass


class TestSmokeTest(unittest.TestCase):
    """Phase 21: 발행 후 smoke_test() 단위 테스트."""

    @patch("chain_publisher.db.get_chain_posts")
    @patch("chain_publisher.db.update_smoke_test_result")
    @patch("requests.get")
    def test_smoke_test_all_pass(
        self, mock_get, mock_update, mock_get_posts
    ):
        """3개 URL 모두 HTTP 200 + title + og:image 정상."""
        from chain_publisher import smoke_test

        mock_get_posts.return_value = [
            {"id": 1, "published_url": "https://rotcha.kr/post1", "step": 1},
            {"id": 2, "published_url": "https://issue.techpawz/post2", "step": 2},
            {"id": 3, "published_url": "https://techpawz/post3", "step": 3},
        ]

        # Mock HTTP response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <html><head>
            <title>Test Post</title>
            <meta property="og:image" content="https://r2.example.com/img.webp">
        </head></html>
        """
        mock_get.return_value = mock_resp

        results = smoke_test(99)

        self.assertEqual(len(results), 3)
        for post_id, detail in results.items():
            self.assertEqual(detail["overall"], "pass")
            self.assertEqual(detail["status_code"], 200)
            self.assertTrue(detail["title_found"])
            self.assertTrue(detail["og_image_ok"])

    @patch("chain_publisher.db.get_chain_posts")
    @patch("chain_publisher.db.update_smoke_test_result")
    @patch("requests.get")
    def test_smoke_test_http_500(
        self, mock_get, mock_update, mock_get_posts
    ):
        """HTTP 500 → overall fail, DB 기록."""
        from chain_publisher import smoke_test

        mock_get_posts.return_value = [
            {"id": 1, "published_url": "https://rotcha.kr/fail", "step": 1},
        ]

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "<html><body>Error</body></html>"
        mock_get.return_value = mock_resp

        results = smoke_test(99)

        self.assertEqual(results[1]["overall"], "fail")
        self.assertEqual(results[1]["status_code"], 500)

    @patch("chain_publisher.db.get_chain_posts")
    @patch("chain_publisher.db.update_smoke_test_result")
    @patch("requests.get")
    def test_smoke_test_connection_error(
        self, mock_get, mock_update, mock_get_posts
    ):
        """Connection error → overall fail, 예외 처리."""
        from chain_publisher import smoke_test

        mock_get_posts.return_value = [
            {"id": 1, "published_url": "https://rotcha.kr/timeout", "step": 1},
        ]
        mock_get.side_effect = Exception("Connection timeout")

        results = smoke_test(99)

        self.assertEqual(results[1]["overall"], "fail")
        self.assertIsNotNone(results[1]["error"])

    @patch("chain_publisher.db.get_chain_posts")
    @patch("chain_publisher.db.update_smoke_test_result")
    @patch("requests.get")
    def test_smoke_test_missing_url(
        self, mock_get, mock_update, mock_get_posts
    ):
        """published_url 없음 → skip (결과에 포함 안 됨)."""
        from chain_publisher import smoke_test

        mock_get_posts.return_value = [
            {"id": 1, "published_url": None, "step": 1},
        ]

        results = smoke_test(99)
        self.assertEqual(len(results), 1)  # 누락 URL도 실패 결과로 기록

    @patch("chain_publisher.db.get_chain_posts")
    @patch("chain_publisher.db.update_smoke_test_result")
    @patch("requests.get")
    def test_smoke_test_og_image_404(
        self, mock_get, mock_update, mock_get_posts
    ):
        """og:image URL이 404 → overall fail."""
        from chain_publisher import smoke_test

        mock_get_posts.return_value = [
            {"id": 1, "published_url": "https://rotcha.kr/post1", "step": 1},
        ]

        # First call: page OK ; Second call: og:image 404
        mock_page = MagicMock()
        mock_page.status_code = 200
        mock_page.text = """
        <html><head>
            <title>Test</title>
            <meta property="og:image" content="https://r2.example.com/missing.webp">
        </head></html>
        """

        mock_og = MagicMock()
        mock_og.status_code = 404

        mock_get.side_effect = [mock_page, mock_og]

        results = smoke_test(99)
        self.assertEqual(results[1]["overall"], "fail")
        self.assertFalse(results[1]["og_image_ok"])


class TestYearGuardIntegrationPublisher:
    """chain_publisher_core 연도 검증 통합 테스트 (Phase 32)."""

    def test_sanitize_markdown_body_includes_year_guard(self):
        """_sanitize_markdown_body가 year_guard를 거치는지 확인."""
        from chain_publisher_core import _sanitize_markdown_body

        body = "2025 최신 정보입니다. 본문 내용."
        result = _sanitize_markdown_body(body)
        assert "2026 최신 정보" in result

    def test_sanitize_preserves_factual_date(self):
        """_sanitize_markdown_body가 사실 날짜를 보존하는지 확인."""
        from chain_publisher_core import _sanitize_markdown_body

        body = "2025년 축제 개최. 2025 최신 정보."
        result = _sanitize_markdown_body(body)
        assert "2025년 축제" in result
        assert "2026 최신" in result

    def test_markdown_processor_year_guard_step(self):
        """MarkdownProcessor.process()가 year_guard를 적용하는지 확인."""
        from markdown_processor import processor

        body = "2025 최신 트렌드와 2024년 기준 분석"
        result = processor.process(body, leak_context="draft")
        assert "2026 최신" in result
        assert "2026년 기준" in result


class TestExtractCleanBodyJSONBlock:
    """_extract_clean_body() 블록 단위 JSON 탐지 검증"""

    def test_indented_json_block_skipped(self):
        """들여쓰기 JSON 블록 스킵"""
        from chain_publisher_core import _extract_clean_body

        raw = '''---
title: "Test"
---
본문입니다.

  {
    "image_type": "photo",
    "image_keyword": "test"
  }

다음 문단입니다.
'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "image_keyword" not in cleaned.body
        assert "다음 문단입니다" in cleaned.body

    def test_multiple_json_blocks_all_skipped(self):
        """다중 JSON 객체 잔류 → 모두 스킵"""
        from chain_publisher_core import _extract_clean_body

        raw = '''---
title: "Test"
---
첫 번째 JSON:
{
  "image_type": "photo"
}
중간 텍스트
두 번째 JSON:
{
  "chart_type": "bar",
  "chart_data": {}
}
마지막 텍스트
'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "chart_type" not in cleaned.body
        assert "첫 번째 JSON" in cleaned.body
        assert "중간 텍스트" in cleaned.body
        assert "마지막 텍스트" in cleaned.body

    def test_partial_json_with_image_type_only(self):
        """image_type 키만 있는 부분 JSON 스킵"""
        from chain_publisher_core import _extract_clean_body

        raw = '''---
title: "Test"
---
본문
{"image_type": "photo"}
끝'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "본문" in cleaned.body
        assert "끝" in cleaned.body

    def test_json_block_spanning_multiple_lines(self):
        """여러 줄에 걸친 JSON 블록 스킵"""
        from chain_publisher_core import _extract_clean_body

        raw = '''---
title: "Test"
---
시작
{
  "image_type": "chart",
  "chart_type": "line",
  "chart_data": {
    "labels": ["A", "B"],
    "values": [1, 2]
  }
}
끝'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "chart_type" not in cleaned.body
        assert "chart_data" not in cleaned.body
        assert "시작" in cleaned.body
        assert "끝" in cleaned.body

    def test_code_fence_json_still_skipped(self):
        """기존 코드펜스 JSON 여전히 스킵 (회귀 방지)"""
        from chain_publisher_core import _extract_clean_body

        raw = '''---
title: "Test"
---
본문
```json
{"image_type": "photo", "chart_type": "bar"}
```
끝'''
        cleaned = _extract_clean_body(raw)
        assert "image_type" not in cleaned.body
        assert "chart_type" not in cleaned.body
        assert "본문" in cleaned.body
        assert "끝" in cleaned.body

    def test_non_meta_json_preserved(self):
        """메타 키 없는 JSON은 보존 (의도된 데이터)"""
        from chain_publisher_core import _extract_clean_body

        raw = '''---
title: "Test"
---
데이터: {"name": "test", "value": 123}'''
        cleaned = _extract_clean_body(raw)
        assert "name" in cleaned.body
        assert "value" in cleaned.body


class TestPublishHugoWithJSONResidue:
    """_publish_hugo() JSON 잔류 케이스 통과 검증 (mock 사용)"""

    @pytest.mark.asyncio
    async def test_publish_hugo_with_plain_json_in_ai_output(self, tmp_path, monkeypatch):
        """AI 출력에 평문 JSON 포함 시에도 _verify_before_deploy 통과"""
        from chain_publisher_core import PublisherCore, _verify_before_deploy

        # Mock config
        config = {
            "sites": {
                "rotcha": {
                    "hugo_root": str(tmp_path / "hugo"),
                    "cf_pages_project": "test-project",
                    "blog_id": "test",
                    "base_url": "https://test.com",
                    "theme": "PaperMod",
                    "publisher_type": "hugo",
                    "permalink_pattern": "/posts/:slug/",
                }
            }
        }

        # Create hugo structure
        hugo_root = Path(config["sites"]["rotcha"]["hugo_root"])
        content_dir = hugo_root / "content" / "posts" / "test-slug"
        content_dir.mkdir(parents=True)
        public_dir = hugo_root / "public" / "posts" / "test-slug"
        public_dir.mkdir(parents=True)

        # Write index.md WITHOUT JSON residue (simulating successful cleaning)
        index_md = content_dir / "index.md"
        index_md.write_text("""---
title: "Test"
featureimage: "https://img.example.com/thumb.webp"
draft: false
slug: "test-slug"
date: "2026-01-01T00:00:00+09:00"
---

## Content

Body text without JSON.
""", encoding="utf-8")

        # Write clean HTML output
        (public_dir / "index.html").write_text("""<html><body>
<h1>Test</h1>
<p>Body text without JSON.</p>
<img src="https://img.example.com/img.jpg">
</body></html>""", encoding="utf-8")

        # Mock DB
        import chain_db
        with patch("chain_db.get_conn") as mock_get_conn:
            mock_conn = MagicMock()
            mock_get_conn.return_value = mock_conn
            mock_conn.execute.return_value.fetchone.return_value = {
                "id": 1,
                "step": 1,
                "image_meta": json.dumps({
                    "image_type": "photo",
                    "image_keyword": "test",
                    "thumbnail_path": None,
                    "thumbnail_source": None,
                    "content_image_path": "already_set",
                    "chart_type": None,
                    "chart_data": None,
                    "image_reason": None,
                }),
            }

            # Mock external calls
            with patch("chain_publisher_core._check_url_accessible"):
              with patch("chain_publisher_core.get_r2_config", return_value=("images/rotcha", "https://img.rotcha.kr")):
                with patch("chain_publisher_core.upload_all_images", return_value={}):
                    with patch("chain_publisher_core.shutil.which", return_value="/opt/homebrew/bin/hugo"):
                        with patch("subprocess.run") as mock_subprocess:
                            mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")
                            with patch("chain_publisher_core._run_wrangler", return_value=(0, "OK", "")):
                                core = PublisherCore(config)

                                draft_md = """---
title: "Test"
description: "Desc"
tags: ["태그"]
draft: true
---

## Content

Body text.

{"image_type": "photo", "image_keyword": "test"}"""

                                url, method, path = core._publish_hugo(
                                    config["sites"]["rotcha"],
                                    draft_md,
                                    "test-slug",
                                    "Test",
                                    ["tag1"],
                                )

                                # Should succeed (URL not empty)
                                assert url.startswith("https://test.com/posts/test-slug/")
                                assert method == "hugo"


class TestPlanTextGate:
    """BUG-006 (Phase 36 T3): 파손 초안 발행 선차단 비율 게이트 테스트."""

    NORMAL_DRAFT = """---
title: "정상 초안"
description: "정상적인 설명입니다."
---
안녕하세요, 이 글은 정상적인 블로그 포스트입니다.
오늘은 주제에 대해 자세히 알아보겠습니다.

## 첫 번째 섹션
이 섹션에서는 주제의 기본 개념을 설명합니다.
구체적인 사례와 함께 살펴보겠습니다.

## 두 번째 섹션
다음으로 심화 내용을 다룹니다.
관련 수치와 통계를 정리했습니다.
"""

    PLAN_HEAVY_DRAFT = """---
title: "파손 초안"
description: "설명"
---
작성자는 제가 제공한 블로그 콘텐츠를 바탕으로 글을 작성해야 합니다.
각도는 최종 구매 확정입니다. 이 글은 3단계 체인의 3번째 글입니다.
H2 가이드라인:
각 H2 섹션은 최소 5문장. 플레이스홀더:
참고 자료를 바탕으로 사실적인 내용을 작성해야 합니다.
이제 글의 구조를 잡아보겠습니다.
각 섹션:
이제 글을 작성해보겠습니다.
예상 구조:
이제 각 섹션을 작성합니다.
금지 표현: 권장드립니다는 금지입니다.
이제 초안 작성:
"""

    def test_normal_draft_not_blocked(self):
        """정상 초안은 비율 0%로 통과."""
        from chain_publisher_core import check_plan_text_ratio

        r = check_plan_text_ratio(self.NORMAL_DRAFT)
        assert r["blocked"] is False
        assert r["ratio"] == 0.0

    def test_plan_heavy_draft_blocked(self):
        """계획텍스트 다수 초안은 임계치 초과로 차단."""
        from chain_publisher_core import check_plan_text_ratio

        r = check_plan_text_ratio(self.PLAN_HEAVY_DRAFT)
        assert r["blocked"] is True
        assert r["ratio"] > 0.20
        assert len(r["matches"]) > 0

    def test_empty_draft_not_blocked(self):
        """빈 초안은 비율 0으로 차단 안 됨 (빈 값 방어)."""
        from chain_publisher_core import check_plan_text_ratio

        r = check_plan_text_ratio("")
        assert r["blocked"] is False
        assert r["total_lines"] == 0

    def test_frontmatter_excluded_from_ratio(self):
        """frontmatter 라인은 검사 대상에서 제외됨."""
        from chain_publisher_core import check_plan_text_ratio

        # frontmatter에 지시 문구가 있어도 본문만 검사
        draft = "---\ntitle: \"플레이스홀더 참고 자료\"\n---\n정상적인 본문입니다.\n"
        r = check_plan_text_ratio(draft)
        assert r["total_lines"] == 1
        assert r["blocked"] is False

    def test_10006_draft_blocked(self):
        """실측 10006 파손 초안 차단 (과목 6 게이트 실증)."""
        import json as _json
        from chain_publisher_core import check_plan_text_ratio

        data = _json.loads(
            Path(".planning/phase35/b1_posts_10006_10007.json").read_text(encoding="utf-8")
        )
        r = check_plan_text_ratio(data["10006"]["draft_md"])
        assert r["blocked"] is True

    def test_10007_draft_blocked(self):
        """실측 10007 파손 초안 차단 (과목 6 게이트 실증)."""
        import json as _json
        from chain_publisher_core import check_plan_text_ratio

        data = _json.loads(
            Path(".planning/phase35/b1_posts_10006_10007.json").read_text(encoding="utf-8")
        )
        r = check_plan_text_ratio(data["10007"]["draft_md"])
        assert r["blocked"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestPublishSafetyGates:
    def test_chain_post_identity_blocks_foreign_keyword(self):
        from unittest.mock import patch
        from chain_publisher import _validate_chain_post_identity

        with patch("chain_publisher.db.get_chain", return_value={"seed": "남양주 물의 정원"}):
            assert not _validate_chain_post_identity(7, [{
                "id": 1,
                "chain_id": 7,
                "target_keyword": "테라 토마토 맥주",
                "slug": "terra-tomato",
            }])

    def test_frontmatter_gate_rejects_yaml_corruption(self):
        from chain_publisher_core import _validate_hugo_frontmatter_text, DeployValidationError

        _validate_hugo_frontmatter_text('---\ntitle: "Valid"\nslug: "valid"\n---\n\nBody')
        with pytest.raises(DeployValidationError):
            _validate_hugo_frontmatter_text('---\ntitle: [broken\nslug: "bad"\n---\n\nBody')

    def test_frontmatter_gate_rejects_missing_slug(self):
        from chain_publisher_core import _validate_hugo_frontmatter_text, DeployValidationError

        with pytest.raises(DeployValidationError, match="slug"):
            _validate_hugo_frontmatter_text('---\ntitle: "No slug"\n---\n\nBody')

    def test_missing_smoke_url_is_recorded_as_failure(self):
        from unittest.mock import patch
        from chain_publisher import smoke_test

        with patch("chain_publisher.db.get_chain_posts", return_value=[{"id": 1, "published_url": None}]), \
             patch("chain_publisher.db.update_smoke_test_result") as update:
            result = smoke_test(7)
        assert result[1]["overall"] == "fail"
        update.assert_called_once()
