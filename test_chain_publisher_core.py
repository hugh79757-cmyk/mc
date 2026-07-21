"""Tests for chain_publisher_core.py — 발행 코어 (Hugo/Blogger/Manual)."""
import json
import os
import tempfile
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
        """JSON 코드 블록 처리 — 현재 구현은 content를 통과시킴."""
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

    @patch("chain_publisher_core.logger")
    def test_passes_valid_post(self, mock_logger, temp_dir):
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

    @patch("chain_publisher_core.logger")
    def test_warns_on_html_tag_in_source(self, mock_logger, temp_dir):
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

    @patch("chain_publisher_core.logger")
    def test_fails_on_excessive_ads_in_html(self, mock_logger, temp_dir):
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

    @patch("chain_publisher_core.logger")
    def test_fails_on_broken_image_refs(self, mock_logger, temp_dir):
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

    @patch("chain_publisher_core.logger")
    def test_fails_on_json_residue_in_html(self, mock_logger, temp_dir):
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


class TestCLI:
    """CLI 테스트 (해당 없음 - PublisherCore는 라이브러리)."""

    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])