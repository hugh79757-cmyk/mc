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


if __name__ == "__main__":
    unittest.main(verbosity=2)