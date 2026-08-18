"""
Chain 10063 regression tests — false-success / state-contamination prevention.

Covers Wave 5 from the triage plan.
"""
import os
import sys
import logging
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# Shared mock post fixtures
def _make_posts(chain_id=999, seed="테스트", step_overrides=None):
    """Create 3 mock posts with optional per-step overrides."""
    step_overrides = step_overrides or {}
    defaults = {
        "draft_md": "d", "image_url": "/img.jpg", "published_url": None,
        "status": "draft", "title": "Test Post",
        "target_keyword": "테스트", "category_guess": "일반",
    }
    posts = []
    for step in range(1, 4):
        p = {
            **defaults,
            "id": step,
            "step": step,
            "chain_id": chain_id,
            "seed": seed,
            "slug": f"test-s{step}",
        }
        if step in step_overrides:
            p.update(step_overrides[step])
        posts.append(p)
    return posts


class TestSinglePostFailure(unittest.TestCase):
    """One publish failure → chain 'failed', no completion."""

    @patch("chain_publisher.db")
    @patch("chain_publisher.load_config")
    @patch("chain_publisher_core.PublisherCore")
    def test_one_failure_sets_chain_failed(self, MockCore, mock_config, mock_db):
        mock_db.get_chain_posts_ordered.return_value = _make_posts()
        mock_db.get_chain.return_value = {"id": 999, "seed": "테스트", "chain_type": "depth"}
        core_inst = MockCore.return_value
        core_inst.publish_post.side_effect = [
            ("https://rotcha.kr/test-s1/", "hugo", "content/test/s1/index.md"),
            Exception("publish failed to issue.techpawz"),
            Exception("publish failed to techpawz"),
        ]

        from chain_publisher import publish_chain
        result = publish_chain(999, mode="auto")

        self.assertFalse(result)
        mock_db.update_chain_status.assert_called_with(999, "failed")

    @patch("chain_publisher.db")
    @patch("chain_publisher.load_config")
    @patch("chain_publisher_core.PublisherCore")
    def test_one_failure_never_sets_completed(self, MockCore, mock_config, mock_db):
        mock_db.get_chain_posts_ordered.return_value = _make_posts()
        mock_db.get_chain.return_value = {"id": 999, "seed": "테스트", "chain_type": "depth"}
        core_inst = MockCore.return_value
        core_inst.publish_post.side_effect = [
            ("https://rotcha.kr/test-s1/", "hugo", "content/test/s1/index.md"),
            Exception("fail"),
            Exception("fail"),
        ]

        from chain_publisher import publish_chain
        publish_chain(999, mode="auto")

        for c in mock_db.update_chain_status.call_args_list:
            self.assertNotEqual(c[0][1], "completed",
                                "Chain must never be set to 'completed' when any post fails")


class TestAllThreeFail(unittest.TestCase):
    """All three posts fail → no card injection, no smoke success."""

    @patch("chain_publisher.smoke_test")
    @patch("chain_publisher.inject_cards_chain")
    @patch("chain_publisher.db")
    @patch("chain_publisher.load_config")
    @patch("chain_publisher_core.PublisherCore")
    def test_all_fail_no_inject_no_smoke(self, MockCore, mock_config, mock_db,
                                         mock_inject, mock_smoke):
        mock_db.get_chain_posts_ordered.return_value = _make_posts()
        mock_db.get_chain.return_value = {"id": 999, "seed": "테스트", "chain_type": "depth"}
        core_inst = MockCore.return_value
        core_inst.publish_post.side_effect = Exception("fail")

        from chain_publisher import publish_chain
        result = publish_chain(999, mode="auto")

        self.assertFalse(result)
        mock_inject.assert_not_called()
        mock_smoke.assert_not_called()


class TestSmokeTestFailOnMissingUrl(unittest.TestCase):
    """published_url=None in smoke test → fail result."""

    def test_missing_url_records_fail(self):
        with patch("chain_publisher.db") as mock_db:
            mock_db.get_chain_posts.return_value = [
                {"id": 1, "step": 1, "slug": "test-s1",
                 "published_url": None, "status": "published"},
            ]

            from chain_publisher import smoke_test
            results = smoke_test(999)
            self.assertEqual(results[1]["overall"], "fail")
            self.assertEqual(results[1]["error"], "missing published_url")


class TestContaminatedFrontmatter(unittest.TestCase):
    """Shell commands in frontmatter → block file write (raises DeployValidationError)."""

    def test_shell_command_blocked(self):
        from chain_publisher_core import _validate_hugo_frontmatter_text
        from chain_models import DeployValidationError
        fm = (
            "---\n"
            "title: Test\n"
            "slug: test\n"
            "date: 2026-08-17\n"
            "; rm -rf /\n"
            "---\n"
            "Body"
        )
        with self.assertRaises(DeployValidationError):
            _validate_hugo_frontmatter_text(fm)

    def test_json_fence_blocked(self):
        from chain_publisher_core import _validate_hugo_frontmatter_text
        from chain_models import DeployValidationError
        fm = (
            "---\n"
            "title: Test\n"
            "slug: test\n"
            "date: 2026-08-17\n"
            "```json\n"
            '{"key": "val"}\n'
            "```\n"
            "---\n"
            "Body"
        )
        with self.assertRaises(DeployValidationError):
            _validate_hugo_frontmatter_text(fm)

    def test_valid_frontmatter_passes(self):
        from chain_publisher_core import _validate_hugo_frontmatter_text
        fm = (
            "---\n"
            "title: 남양주 물의 정원 산책\n"
            "description: 소개\n"
            "draft: false\n"
            "slug: 남양주-물의-정원-20260817-s1\n"
            "date: 2026-08-17T13:29:00+09:00\n"
            "---\n"
            "Body"
        )
        # Should not raise
        _validate_hugo_frontmatter_text(fm)


class TestResumePartialFailure(unittest.TestCase):
    """Resume with some posts still unpublished → return 1, not 0."""

    @patch("chain_db.update_chain_status")
    @patch("chain_db.get_chain_posts")
    @patch("chain_db.get_chain")
    @patch("chain_publisher.inject_cards_chain")
    @patch("chain_publisher.publish_chain")
    def test_resume_returns_1_on_partial(
        self, mock_publish, mock_inject, mock_get_chain,
        mock_get_posts, mock_upd_status,
    ):
        mock_get_chain.return_value = {
            "id": 77, "seed": "테스트", "status": "image_generated"
        }
        posts_before = _make_posts(chain_id=77)
        posts_after = _make_posts(chain_id=77, step_overrides={
            1: {"published_url": "https://rotcha.kr/t-s1/"},
        })
        mock_get_posts.side_effect = [posts_before, posts_before, posts_after]
        mock_publish.return_value = False

        from cli.mc import _resume_chain
        result = _resume_chain(77, None, logging.getLogger("test"))
        self.assertEqual(result, 1)


class TestAutoQueuePartialFailure(unittest.TestCase):
    """Auto queue with failed chain → mark_failed, not mark_done."""

    @patch("mc.queue.mark_failed")
    @patch("mc.queue.mark_done")
    @patch("chain_publisher.run_chain")
    @patch("mc.queue.get_next_keyword")
    def test_auto_marks_failed_on_none(
        self, mock_get_kw, mock_run, mock_done, mock_failed
    ):
        mock_get_kw.return_value = {"id": 42, "keyword": "테스트", "priority": 1}
        mock_run.return_value = None

        from cli.mc import _cmd_auto
        args = MagicMock()
        args.dry_run = False
        _cmd_auto(args, logging.getLogger("test"))

        mock_failed.assert_called_once()
        mock_done.assert_not_called()


class TestChainIdentityMismatch(unittest.TestCase):
    """chain_id/seed/slug mismatch → block before publish."""

    @patch("chain_publisher.db")
    def test_mismatch_blocks_publish(self, mock_db):
        mock_db.get_chain.return_value = {"id": 999, "seed": "테스트"}
        # post has wrong seed
        posts = _make_posts(step_overrides={1: {"target_keyword": "完全不同"}})

        from chain_publisher import _validate_chain_post_identity
        result = _validate_chain_post_identity(999, posts)
        self.assertFalse(result)

    @patch("chain_publisher.db")
    def test_matching_passes(self, mock_db):
        mock_db.get_chain.return_value = {"id": 999, "seed": "테스트"}
        posts = _make_posts()
        from chain_publisher import _validate_chain_post_identity
        result = _validate_chain_post_identity(999, posts)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
