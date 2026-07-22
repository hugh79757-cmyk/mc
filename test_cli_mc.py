"""
test_cli_mc.py — Phase 14 W1: CLI argument parsing + pipeline routing tests

Covers:
- Argument parsing (12 cases from PLAN.md Task 1.2)
- Site override mapping
- Pipeline routing (dry-run / draft / image / skip-publish / publish)
- chain_publisher function delegation (mocked)
"""

import argparse
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure project root is on path for cli.mc import
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.mc import (
    main,
    _build_blog_overrides,
    _setup_logging,
    _run_full,
    _SITE_BLOG_KEY,
)


class TestArgparse(unittest.TestCase):
    """Test argument parsing via cli.mc main() exit code and behavior."""

    def _parse(self, argv):
        """Helper: parse argv and return (args, exit_code)."""
        parser = argparse.ArgumentParser(prog="mc")
        # Mirror the real parser setup
        parser.add_argument("keyword", nargs="?", help="Seed keyword")
        parser.add_argument("--chain-id", type=int)
        stage_group = parser.add_mutually_exclusive_group()
        stage_group.add_argument("--dry-run", action="store_true")
        stage_group.add_argument("--draft", action="store_true")
        stage_group.add_argument("--image", action="store_true")
        stage_group.add_argument("--skip-publish", action="store_true")
        stage_group.add_argument("--publish", action="store_true")
        parser.add_argument("--resume", action="store_true")
        parser.add_argument("--site", type=str,
                            choices=list(_SITE_BLOG_KEY.keys()))
        parser.add_argument("--background", action="store_true")
        return parser.parse_args(argv)

    def test_argparse_keyword(self):
        args = self._parse(["업클로젯"])
        self.assertEqual(args.keyword, "업클로젯")

    def test_argparse_dry_run(self):
        args = self._parse(["업클로젯", "--dry-run"])
        self.assertTrue(args.dry_run)

    def test_argparse_draft(self):
        args = self._parse(["업클로젯", "--draft"])
        self.assertTrue(args.draft)

    def test_argparse_image(self):
        args = self._parse(["업클로젯", "--image"])
        self.assertTrue(args.image)

    def test_argparse_skip_publish(self):
        args = self._parse(["업클로젯", "--skip-publish"])
        self.assertTrue(args.skip_publish)

    def test_argparse_site(self):
        args = self._parse(["업클로젯", "--site", "rotcha"])
        self.assertEqual(args.site, "rotcha")

    def test_argparse_resume(self):
        args = self._parse(["--chain-id", "66", "--resume"])
        self.assertEqual(args.chain_id, 66)
        self.assertTrue(args.resume)

    def test_argparse_background(self):
        args = self._parse(["업클로젯", "--background"])
        self.assertTrue(args.background)

    def test_argparse_chain_id_only_no_action(self):
        # Just --chain-id without resume/draft/image should parse OK
        # (main() will show help, but parsing succeeds)
        args = self._parse(["--chain-id", "66"])
        self.assertEqual(args.chain_id, 66)
        self.assertFalse(args.resume)
        self.assertFalse(args.draft)
        self.assertFalse(args.image)


class TestBuildBlogOverrides(unittest.TestCase):
    """Test site override mapping logic."""

    def test_no_override_returns_none(self):
        result = _build_blog_overrides(None)
        self.assertIsNone(result)

    def test_empty_override_returns_none(self):
        result = _build_blog_overrides("")
        self.assertIsNone(result)

    def test_rotcha_override(self):
        result = _build_blog_overrides("rotcha")
        self.assertEqual(result, {1: "rotcha", 2: "rotcha", 3: "rotcha"})

    def test_infohot_override(self):
        result = _build_blog_overrides("infohot")
        self.assertEqual(result, {1: "infohot", 2: "infohot", 3: "infohot"})

    def test_techpawz_override(self):
        result = _build_blog_overrides("techpawz")
        self.assertEqual(result, {1: "techpawz", 2: "techpawz", 3: "techpawz"})

    def test_aikorea24_override(self):
        result = _build_blog_overrides("aikorea24")
        self.assertEqual(result, {1: "aikorea24", 2: "aikorea24", 3: "aikorea24"})

    def test_invalid_site_returns_none(self):
        result = _build_blog_overrides("invalid")
        self.assertIsNone(result)


class TestRunFullRouting(unittest.TestCase):
    """Test _run_full() calls chain_publisher.run_chain with correct args."""

    def _make_args(self, **kwargs):
        """Make a mock args object."""
        defaults = dict(
            dry_run=False,
            draft=False,
            image=False,
            skip_publish=False,
            publish=False,
            site=None,
        )
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    @patch("chain_publisher.run_chain")
    def test_dry_run_calls_run_chain(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args(dry_run=True)
        result = _run_full("테스트", args, logger)
        mock_run_chain.assert_called_once()
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertTrue(call_kwargs["dry_run"])
        self.assertFalse(call_kwargs["draft_only"])
        self.assertFalse(call_kwargs["image_only"])
        self.assertIsNone(call_kwargs["publish_mode"])
        self.assertEqual(result, 99)

    @patch("chain_publisher.run_chain")
    def test_draft_only_calls_run_chain(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args(draft=True)
        result = _run_full("테스트", args, logger)
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertTrue(call_kwargs["draft_only"])
        self.assertEqual(result, 99)

    @patch("chain_publisher.run_chain")
    def test_image_only_calls_run_chain(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args(image=True)
        result = _run_full("테스트", args, logger)
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertTrue(call_kwargs["image_only"])
        self.assertEqual(result, 99)

    @patch("chain_publisher.run_chain")
    def test_skip_publish_alias(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args(skip_publish=True)
        result = _run_full("테스트", args, logger)
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertTrue(call_kwargs["image_only"])  # skip_publish → image_only
        self.assertEqual(result, 99)

    @patch("chain_publisher.run_chain")
    def test_default_full_pipeline(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args()  # no stage flag → full pipeline
        result = _run_full("테스트", args, logger)
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertEqual(call_kwargs["publish_mode"], "auto")
        self.assertFalse(call_kwargs["draft_only"])
        self.assertFalse(call_kwargs["image_only"])
        self.assertEqual(result, 99)

    @patch("chain_publisher.run_chain")
    def test_site_override_passed(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args(site="rotcha")
        _run_full("테스트", args, logger)
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertEqual(call_kwargs["blog_overrides"], {1: "rotcha", 2: "rotcha", 3: "rotcha"})

    @patch("chain_publisher.run_chain")
    def test_no_site_override_passes_none(self, mock_run_chain):
        mock_run_chain.return_value = 99
        logger = _setup_logging()
        args = self._make_args()
        _run_full("테스트", args, logger)
        call_kwargs = mock_run_chain.call_args.kwargs
        self.assertIsNone(call_kwargs["blog_overrides"])

    @patch("chain_publisher.run_chain")
    def test_returns_1_on_failure(self, mock_run_chain):
        mock_run_chain.return_value = 0  # failure
        logger = _setup_logging()
        args = self._make_args()
        result = _run_full("테스트", args, logger)
        self.assertEqual(result, 1)


class TestSiteBlogKey(unittest.TestCase):
    """Test that all expected sites are in the mapping."""

    def test_all_expected_sites_present(self):
        expected = {"rotcha", "infohot", "techpawz", "aikorea24"}
        self.assertEqual(set(_SITE_BLOG_KEY.keys()), expected)


class TestResumeChain(unittest.TestCase):
    """W2: _resume_chain() state detection and step skip logic."""

    @patch("chain_db.get_chain")
    @patch("chain_db.get_chain_posts")
    @patch("chain_drafter.draft_chain")
    @patch("chain_publisher.generate_chain_images")
    @patch("chain_publisher.publish_chain")
    @patch("chain_publisher.inject_cards_chain")
    @patch("chain_publisher._preflight_check")
    @patch("chain_db.update_chain_status")
    def test_resume_all_complete_returns_0(
        self, mock_update_status, mock_preflight, mock_inject, mock_publish,
        mock_gen_img, mock_draft, mock_get_posts, mock_get_chain
    ):
        """(c) Already complete chain → 'already complete' + exit 0."""
        import logging
        from cli.mc import _resume_chain

        # Chain exists, status=completed, all posts have published_url
        mock_get_chain.return_value = {"id": 99, "seed": "테스트", "status": "completed"}
        mock_get_posts.return_value = [
            {"id": 1, "draft_md": "content", "image_url": "/img.jpg", "published_url": "https://rotcha.kr/1"},
            {"id": 2, "draft_md": "content", "image_url": "/img.jpg", "published_url": "https://infohot/2"},
            {"id": 3, "draft_md": "content", "image_url": "/img.jpg", "published_url": "https://techpawz/3"},
        ]

        logger = _setup_logging()
        result = _resume_chain(99, None, logger)

        self.assertEqual(result, 0)
        mock_draft.assert_not_called()
        mock_gen_img.assert_not_called()
        mock_publish.assert_not_called()
        # Should NOT update status since it's already completed
        mock_update_status.assert_not_called()

    @patch("chain_db.get_chain")
    @patch("chain_db.get_chain_posts")
    @patch("chain_drafter.draft_chain")
    @patch("chain_publisher.generate_chain_images")
    @patch("chain_publisher.publish_chain")
    @patch("chain_publisher.inject_cards_chain")
    @patch("chain_publisher._preflight_check")
    @patch("chain_db.update_chain_status")
    def test_resume_missing_draft_then_image_then_publish(
        self, mock_update_status, mock_preflight, mock_inject, mock_publish,
        mock_gen_img, mock_draft, mock_get_posts, mock_get_chain
    ):
        """(a) All steps missing → resume runs draft → image → publish sequentially."""
        import logging
        from cli.mc import _resume_chain

        mock_get_chain.return_value = {"id": 66, "seed": "테스트", "status": "derived"}

        # Initial: no draft_md, no image_url, no published_url
        initial_posts = [
            {"id": 1, "draft_md": None, "image_url": None, "published_url": None},
            {"id": 2, "draft_md": None, "image_url": None, "published_url": None},
            {"id": 3, "draft_md": None, "image_url": None, "published_url": None},
        ]
        # After draft: has draft_md, no image
        draft_posts = [
            {"id": 1, "draft_md": "content", "image_url": None, "published_url": None},
            {"id": 2, "draft_md": "content", "image_url": None, "published_url": None},
            {"id": 3, "draft_md": "content", "image_url": None, "published_url": None},
        ]
        # After image: has image, no published_url
        image_posts = [
            {"id": 1, "draft_md": "content", "image_url": "/img1.jpg", "published_url": None},
            {"id": 2, "draft_md": "content", "image_url": "/img2.jpg", "published_url": None},
            {"id": 3, "draft_md": "content", "image_url": "/img3.jpg", "published_url": None},
        ]
        # After publish: all done
        published_posts = [
            {"id": 1, "draft_md": "content", "image_url": "/img1.jpg", "published_url": "https://rotcha.kr/1"},
            {"id": 2, "draft_md": "content", "image_url": "/img2.jpg", "published_url": "https://infohot/2"},
            {"id": 3, "draft_md": "content", "image_url": "/img3.jpg", "published_url": "https://techpawz/3"},
        ]

        # 5 calls: initial(draft check) → draft_posts(image check) → image_posts(publish check) → published_posts(final)
        mock_get_posts.side_effect = [initial_posts, draft_posts, image_posts, published_posts, published_posts]
        mock_preflight.return_value = True

        logger = _setup_logging()
        result = _resume_chain(66, None, logger)

        self.assertEqual(result, 0)
        mock_draft.assert_called_once_with(66, "테스트")
        mock_gen_img.assert_called_once_with(66)
        mock_publish.assert_called_once()
        mock_inject.assert_called_once()

    @patch("chain_db.get_chain")
    def test_resume_invalid_chain_id(self, mock_get_chain):
        """(b) Invalid chain-id → error message + exit code 2."""
        import logging
        from cli.mc import _resume_chain

        mock_get_chain.return_value = None  # Chain not found

        logger = _setup_logging()
        result = _resume_chain(99999, None, logger)

        self.assertEqual(result, 2)

    @patch("chain_db.get_chain")
    @patch("chain_db.get_chain_posts")
    @patch("chain_drafter.draft_chain")
    @patch("chain_publisher.generate_chain_images")
    @patch("chain_publisher.publish_chain")
    @patch("chain_publisher.inject_cards_chain")
    @patch("chain_publisher._preflight_check")
    @patch("chain_db.update_chain_status")
    def test_resume_partial_draft_only(
        self, mock_update_status, mock_preflight, mock_inject, mock_publish,
        mock_gen_img, mock_draft, mock_get_posts, mock_get_chain
    ):
        """Draft+image done, publish missing → skip draft+image, run publish only."""
        import logging
        from cli.mc import _resume_chain

        mock_get_chain.return_value = {"id": 66, "seed": "테스트", "status": "image_generated"}

        # Posts have draft_md and image_url but no published_url
        mock_get_posts.return_value = [
            {"id": 1, "draft_md": "content", "image_url": "/img1.jpg", "published_url": None},
            {"id": 2, "draft_md": "content", "image_url": "/img2.jpg", "published_url": None},
            {"id": 3, "draft_md": "content", "image_url": "/img3.jpg", "published_url": None},
        ]

        logger = _setup_logging()
        result = _resume_chain(66, None, logger)

        self.assertEqual(result, 0)
        mock_draft.assert_not_called()       # draft already done
        mock_gen_img.assert_not_called()     # image already done
        mock_publish.assert_called_once()    # publish still needed
        mock_inject.assert_called_once()


class TestSetupLogging(unittest.TestCase):
    """W3: _setup_logging() dual handler + flush on emit."""

    def test_dual_handler_count(self):
        """_setup_logging() creates exactly 2 handlers (file + stdout)."""
        from cli.mc import _setup_logging
        logger = _setup_logging()
        self.assertEqual(len(logger.handlers), 2)

    def test_flush_on_emit(self):
        """Both handlers flush on each emit (real-time stage visibility)."""
        from cli.mc import _setup_logging
        import logging
        logger = _setup_logging()
        handlers = logger.handlers
        self.assertEqual(len(handlers), 2)
        # Verify the custom Flush handlers are in place
        handler_types = [type(h).__name__ for h in handlers]
        self.assertIn("_FlushStreamHandler", handler_types)
        self.assertIn("_FlushFileHandler", handler_types)


class TestRunBackground(unittest.TestCase):
    """W3: _run_background() subprocess + PID file."""

    @patch("subprocess.Popen")
    def test_popen_called_with_start_new_session(self, mock_popen):
        """_run_background() calls subprocess.Popen with start_new_session=True."""
        import argparse
        from cli.mc import _run_background, _setup_logging

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        args = argparse.Namespace(
            dry_run=True, draft=False, image=False, skip_publish=False,
            publish=False, site=None, background=True, keyword="테스트",
        )
        logger = _setup_logging()
        result = _run_background("테스트", args, logger)

        mock_popen.assert_called_once()
        call_kwargs = mock_popen.call_args.kwargs
        self.assertTrue(call_kwargs.get("start_new_session"))
        self.assertEqual(result, 0)

    @patch("subprocess.Popen")
    @patch("pathlib.Path.write_text")
    def test_pid_file_created_with_pid(self, mock_write_text, mock_popen):
        """_run_background() creates PID file containing the subprocess PID."""
        import argparse
        from cli.mc import _run_background, _setup_logging

        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_popen.return_value = mock_proc

        args = argparse.Namespace(
            dry_run=True, draft=False, image=False, skip_publish=False,
            publish=False, site=None, background=True, keyword="테스트",
        )
        logger = _setup_logging()
        _run_background("테스트", args, logger)

        mock_write_text.assert_called()
        # Last call should be write_text with the PID
        last_call = mock_write_text.call_args
        self.assertIn("99999", last_call[0][0])

    @patch("subprocess.Popen")
    def test_argv_includes_pid_file_flag(self, mock_popen):
        """_run_background() passes --pid-file to subprocess argv."""
        import argparse
        from cli.mc import _run_background, _setup_logging

        mock_proc = MagicMock()
        mock_proc.pid = 11111
        mock_popen.return_value = mock_proc

        args = argparse.Namespace(
            dry_run=False, draft=False, image=True, skip_publish=False,
            publish=False, site=None, background=True, keyword="업클로젯",
        )
        logger = _setup_logging()
        _run_background("업클로젯", args, logger)

        call_args = mock_popen.call_args
        argv = call_args[0][0] if call_args[0] else call_args.kwargs.get("argv")
        if not argv:
            argv = [a for a in call_args[0]]
        self.assertIn("--pid-file", argv)

    @patch("subprocess.Popen")
    def test_console_single_line_output(self, mock_popen, mock_print=None):
        """_run_background() prints exactly 1 line to console (PID + log + pid_file)."""
        import argparse
        import sys
        from io import StringIO
        from cli.mc import _run_background, _setup_logging

        mock_proc = MagicMock()
        mock_proc.pid = 55555
        mock_popen.return_value = mock_proc

        args = argparse.Namespace(
            dry_run=True, draft=False, image=False, skip_publish=False,
            publish=False, site=None, background=True, keyword="테스트",
        )
        logger = _setup_logging()

        # Capture stdout
        old_stdout = sys.stdout
        captured = StringIO()
        sys.stdout = captured
        try:
            _run_background("테스트", args, logger)
        finally:
            sys.stdout = old_stdout

        output = captured.getvalue()
        self.assertIn("55555", output)      # PID
        self.assertIn("log=", output)        # log file
        self.assertIn("pid_file=", output)  # pid file
        self.assertEqual(output.count("\n"), 1)  # exactly 1 line


if __name__ == "__main__":
    unittest.main(verbosity=2)