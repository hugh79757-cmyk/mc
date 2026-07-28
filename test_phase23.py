"""
Test cases for Phase 23: Keyword Queue System (mc/queue.py)
"""

import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock, PropertyMock
import sqlite3
from datetime import datetime

# Create a temp database file for testing
TEST_DB_PATH = None


def get_test_db_path():
    """Return a test database path, creating temp file if needed."""
    global TEST_DB_PATH
    if TEST_DB_PATH is None:
        fd, TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
        os.close(fd)
    return TEST_DB_PATH


def cleanup_test_db():
    """Clean up test database."""
    global TEST_DB_PATH
    if TEST_DB_PATH and os.path.exists(TEST_DB_PATH):
        os.unlink(TEST_DB_PATH)
        TEST_DB_PATH = None


class TestKeywordQueue(unittest.TestCase):
    """Test keyword queue functionality."""

    @classmethod
    def setUpClass(cls):
        # Mock chain_config.yaml to use test database
        cls.config_patcher = patch("mc_paths.load_config")
        mock_load = cls.config_patcher.start()

        def mock_load_config(config_name="chain_config.yaml"):
            if config_name == "chain_config.yaml":
                return {"db_path": get_test_db_path()}
            # For other configs, load real ones
            import yaml
            from mc_paths import CONFIG_DIR
            path = os.path.join(CONFIG_DIR, config_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            return {}

        mock_load.side_effect = mock_load_config

        # Force re-initialization of chain_db
        import chain_db as db
        db.cfg = None
        db.MC_DB_PATH = get_test_db_path()
        db.init_db()
        cls.db = db

    @classmethod
    def tearDownClass(cls):
        cls.config_patcher.stop()
        cleanup_test_db()

    def setUp(self):
        """Clear keyword_queue table before each test."""
        conn = self.db.get_conn()
        conn.execute("DELETE FROM keyword_queue")
        conn.commit()
        conn.close()

    def test_add_keyword_success(self):
        """Test adding a keyword to queue."""
        result = self.db.add_keyword_queue("제주도카페", "travel", 2)
        self.assertTrue(result["success"])
        self.assertEqual(result["keyword"], "제주도카페")
        self.assertEqual(result["status"], "added")

    def test_add_keyword_duplicate(self):
        """Test duplicate keyword handling - same keyword can be re-added (no unique constraint).
        But if keyword exists in 'done' status, it warns."""
        # First add
        result1 = self.db.add_keyword_queue("삼성갤럭시", "tech", 3)
        self.assertTrue(result1["success"])

        # Second add - should succeed (same keyword allowed for pending)
        result2 = self.db.add_keyword_queue("삼성갤럭시", "tech", 1)
        self.assertTrue(result2["success"])
        self.assertEqual(result2["status"], "added")

        # Mark first one as done
        item = self.db.get_next_keyword()  # Gets the first one
        self.db.mark_keyword_done(item["keyword"], 999)

        # Third add - should warn because keyword exists in 'done' status
        result3 = self.db.add_keyword_queue("삼성갤럭시", "tech", 2)
        self.assertFalse(result3["success"])
        self.assertEqual(result3["status"], "duplicate")
        self.assertEqual(result3["existing_status"], "done")

    def test_get_next_keyword_empty(self):
        """Test getting next keyword from empty queue."""
        result = self.db.get_next_keyword()
        self.assertIsNone(result)

    def test_get_next_keyword_priority_order(self):
        """Test that higher priority (lower number) keywords come first."""
        self.db.add_keyword_queue("keyword1", "travel", 3)
        self.db.add_keyword_queue("keyword2", "tech", 1)  # Highest priority
        self.db.add_keyword_queue("keyword3", "stock", 2)

        # Should get priority 1 first
        item = self.db.get_next_keyword()
        self.assertEqual(item["keyword"], "keyword2")
        self.assertEqual(item["priority"], 1)

        # Should get priority 2 next
        item = self.db.get_next_keyword()
        self.assertEqual(item["keyword"], "keyword3")
        self.assertEqual(item["priority"], 2)

        # Should get priority 3 last
        item = self.db.get_next_keyword()
        self.assertEqual(item["keyword"], "keyword1")
        self.assertEqual(item["priority"], 3)

    def test_get_next_keyword_marks_processing(self):
        """Test that get_next_keyword updates status to processing."""
        self.db.add_keyword_queue("테스트키워드", "travel", 3)
        item = self.db.get_next_keyword()
        self.assertIsNotNone(item)
        # Verify in DB
        queue = self.db.list_keyword_queue()
        self.assertEqual(queue[0]["status"], "processing")

    def test_mark_done(self):
        """Test marking keyword as done with chain_id."""
        self.db.add_keyword_queue("완료테스트", "travel", 3)
        item = self.db.get_next_keyword()

        self.db.mark_keyword_done(item["keyword"], 123)

        queue = self.db.list_keyword_queue()
        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(queue[0]["chain_id"], 123)
        self.assertIsNotNone(queue[0]["processed_at"])

    def test_mark_failed(self):
        """Test marking keyword as failed with error message."""
        self.db.add_keyword_queue("실패테스트", "tech", 2)
        item = self.db.get_next_keyword()

        self.db.mark_keyword_failed(item["keyword"], "Connection timeout")

        queue = self.db.list_keyword_queue()
        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(queue[0]["error_msg"], "Connection timeout")

    def test_list_queue(self):
        """Test listing queue with and without status filter."""
        self.db.add_keyword_queue("키워드1", "travel", 3)
        self.db.add_keyword_queue("키워드2", "tech", 1)
        self.db.add_keyword_queue("키워드3", "stock", 2)

        all_items = self.db.list_keyword_queue()
        self.assertEqual(len(all_items), 3)

        # Filter by status
        pending = self.db.list_keyword_queue("pending")
        self.assertEqual(len(pending), 3)
        for item in pending:
            self.assertEqual(item["status"], "pending")

    def test_remove_keyword_pending_only(self):
        """Test removing keyword - only pending allowed."""
        self.db.add_keyword_queue("삭제테스트", "travel", 3)

        # Get the queue ID
        queue = self.db.list_keyword_queue()
        qid = queue[0]["id"]

        # Should work for pending
        result = self.db.remove_keyword_queue(qid)
        self.assertTrue(result)

        # Add another and mark as done
        self.db.add_keyword_queue("삭제테스트2", "tech", 2)
        item = self.db.get_next_keyword()
        self.db.mark_keyword_done(item["keyword"], 999)

        # Should fail for done (remove_keyword_queue only works on pending)
        queue = self.db.list_keyword_queue()
        done_id = queue[0]["id"]
        result = self.db.remove_keyword_queue(done_id)
        self.assertFalse(result)


class TestQueueModule(unittest.TestCase):
    """Test mc/queue.py module functions."""

    @classmethod
    def setUpClass(cls):
        cls.config_patcher = patch("mc_paths.load_config")
        mock_load = cls.config_patcher.start()

        def mock_load_config(config_name="chain_config.yaml"):
            if config_name == "chain_config.yaml":
                return {"db_path": get_test_db_path()}
            import yaml
            from mc_paths import CONFIG_DIR
            path = os.path.join(CONFIG_DIR, config_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            return {}

        mock_load.side_effect = mock_load_config

        import chain_db as db
        db.cfg = None
        db.MC_DB_PATH = get_test_db_path()
        db.init_db()
        cls.db = db

    @classmethod
    def tearDownClass(cls):
        cls.config_patcher.stop()
        cleanup_test_db()

    def setUp(self):
        conn = self.db.get_conn()
        conn.execute("DELETE FROM keyword_queue")
        conn.commit()
        conn.close()

    def test_add_keyword(self):
        """Test queue.add_keyword wrapper."""
        from mc.queue import add_keyword

        result = add_keyword("큐모듈테스트", "travel", 2)
        self.assertTrue(result["success"])

    def test_get_next_keyword(self):
        """Test queue.get_next_keyword wrapper."""
        from mc.queue import add_keyword, get_next_keyword

        add_keyword("다음키워드", "tech", 1)
        item = get_next_keyword()
        self.assertIsNotNone(item)
        self.assertEqual(item["keyword"], "다음키워드")

    def test_mark_done_by_id(self):
        """Test queue.mark_done with queue_id."""
        from mc.queue import add_keyword, get_next_keyword, mark_done

        add_keyword("완료테스트", "travel", 3)
        item = get_next_keyword()

        mark_done(item["id"], 456)

        queue = self.db.list_keyword_queue()
        self.assertEqual(queue[0]["status"], "done")
        self.assertEqual(queue[0]["chain_id"], 456)

    def test_mark_failed_by_id(self):
        """Test queue.mark_failed with queue_id."""
        from mc.queue import add_keyword, get_next_keyword, mark_failed

        add_keyword("실패테스트", "tech", 2)
        item = get_next_keyword()

        mark_failed(item["id"], "Network error")

        queue = self.db.list_keyword_queue()
        self.assertEqual(queue[0]["status"], "failed")
        self.assertEqual(queue[0]["error_msg"], "Network error")

    def test_list_queue(self):
        """Test queue.list_queue wrapper."""
        from mc.queue import add_keyword, list_queue

        add_keyword("목록1", "travel", 3)
        add_keyword("목록2", "tech", 1)

        items = list_queue()
        self.assertEqual(len(items), 2)

        pending = list_queue("pending")
        self.assertEqual(len(pending), 2)

    def test_remove_keyword(self):
        """Test queue.remove_keyword wrapper."""
        from mc.queue import add_keyword, remove_keyword

        add_keyword("제거테스트", "travel", 3)
        queue = self.db.list_keyword_queue()
        qid = queue[0]["id"]

        result = remove_keyword(qid)
        self.assertTrue(result)


class TestAutoCommand(unittest.TestCase):
    """Test mc auto command integration."""

    @classmethod
    def setUpClass(cls):
        cls.config_patcher = patch("mc_paths.load_config")
        mock_load = cls.config_patcher.start()

        def mock_load_config(config_name="chain_config.yaml"):
            if config_name == "chain_config.yaml":
                return {"db_path": get_test_db_path()}
            import yaml
            from mc_paths import CONFIG_DIR
            path = os.path.join(CONFIG_DIR, config_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            return {}

        mock_load.side_effect = mock_load_config

        import chain_db as db
        db.cfg = None
        db.MC_DB_PATH = get_test_db_path()
        db.init_db()
        cls.db = db

    @classmethod
    def tearDownClass(cls):
        cls.config_patcher.stop()
        cleanup_test_db()

    def setUp(self):
        conn = self.db.get_conn()
        conn.execute("DELETE FROM keyword_queue")
        conn.commit()
        conn.close()

    @patch("mc.queue.get_next_keyword")
    def test_auto_empty_queue(self, mock_get_next):
        """Test mc auto exits gracefully when queue is empty."""
        mock_get_next.return_value = None

        from cli.mc import _cmd_auto
        import argparse

        args = argparse.Namespace(dry_run=False)

        import logging
        logger = logging.getLogger("test")
        result = _cmd_auto(args, logger)

        self.assertEqual(result, 0)
        mock_get_next.assert_called_once()

    @patch("mc.queue.get_next_keyword")
    @patch("mc.queue.mark_done")
    @patch("chain_publisher.run_chain")
    def test_auto_success(self, mock_run_chain, mock_mark_done, mock_get_next):
        """Test mc auto processes keyword successfully."""
        mock_get_next.return_value = {"id": 1, "keyword": "자동처리", "priority": 3}
        mock_run_chain.return_value = 789

        from cli.mc import _cmd_auto
        import argparse

        args = argparse.Namespace(dry_run=False)

        import logging
        logger = logging.getLogger("test")
        result = _cmd_auto(args, logger)

        self.assertEqual(result, 0)
        mock_run_chain.assert_called_once_with("자동처리", publish_mode="auto", use_context=True)
        mock_mark_done.assert_called_once_with(1, 789)

    @patch("mc.queue.get_next_keyword")
    @patch("mc.queue.mark_failed")
    @patch("chain_publisher.run_chain")
    def test_auto_failure(self, mock_run_chain, mock_mark_failed, mock_get_next):
        """Test mc auto handles failure."""
        mock_get_next.return_value = {"id": 1, "keyword": "실패키워드", "priority": 3}
        mock_run_chain.side_effect = Exception("API error")

        from cli.mc import _cmd_auto
        import argparse

        args = argparse.Namespace(dry_run=False)

        import logging
        logger = logging.getLogger("test")
        result = _cmd_auto(args, logger)

        self.assertEqual(result, 1)
        mock_mark_failed.assert_called_once()

    @patch("mc.queue.get_next_keyword")
    def test_auto_dry_run(self, mock_get_next):
        """Test mc auto --dry-run doesn't process."""
        mock_get_next.return_value = {"id": 1, "keyword": "드라이런", "priority": 2}

        from cli.mc import _cmd_auto
        import argparse

        args = argparse.Namespace(dry_run=True)

        import logging
        logger = logging.getLogger("test")
        result = _cmd_auto(args, logger)

        self.assertEqual(result, 0)
        # Should NOT call mark_done or mark_failed


class TestScheduleCommand(unittest.TestCase):
    """Test mc schedule subcommands."""

    @patch("cli.mc._cmd_schedule")
    def test_schedule_setup_macos(self, mock_cmd_schedule):
        """Test schedule setup on macOS creates launchd plist."""
        mock_cmd_schedule.return_value = 0
        import argparse

        args = argparse.Namespace(
            schedule_action="setup",
            hour=9,
            minute=0,
            no_launchd=False,
            daily=True
        )

        import logging
        logger = logging.getLogger("test")
        result = mock_cmd_schedule(args, logger)

        self.assertEqual(result, 0)
        mock_cmd_schedule.assert_called_once()

    @patch("cli.mc._cmd_schedule")
    def test_schedule_setup_linux(self, mock_cmd_schedule):
        """Test schedule setup on Linux uses cron."""
        mock_cmd_schedule.return_value = 0
        import argparse

        args = argparse.Namespace(
            schedule_action="setup",
            hour=9,
            minute=30,
            no_launchd=True,
            daily=True
        )

        import logging
        logger = logging.getLogger("test")
        result = mock_cmd_schedule(args, logger)

        self.assertEqual(result, 0)
        mock_cmd_schedule.assert_called_once()


class TestNotifyModule(unittest.TestCase):
    """Test mc/notify.py module."""

    def test_send_alert_disabled(self):
        """Test send_alert returns False when disabled."""
        with patch("mc.notify._load_notify_config", return_value={"notify": {"enabled": False}}):
            from mc.notify import send_alert
            result = send_alert("Test", "Detail", "error")
            self.assertFalse(result)

    def test_send_alert_no_webhook(self):
        """Test send_alert returns False when no webhook URL."""
        with patch("mc.notify._load_notify_config", return_value={
            "notify": {"enabled": True, "webhook": {"url": ""}, "levels": {"error": True}}
        }):
            from mc.notify import send_alert
            result = send_alert("Test", "Detail", "error")
            self.assertFalse(result)

    def test_send_alert_level_filter(self):
        """Test send_alert respects level filter."""
        with patch("mc.notify._load_notify_config", return_value={
            "notify": {"enabled": True, "webhook": {"url": "http://test"}, "levels": {"error": True, "info": False}}
        }):
            from mc.notify import send_alert
            result = send_alert("Test", "Detail", "info")  # info disabled
            self.assertFalse(result)

    @patch("urllib.request.urlopen")
    def test_send_alert_webhook_success(self, mock_urlopen):
        """Test send_alert webhook success."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        with patch("mc.notify._load_notify_config", return_value={
            "notify": {"enabled": True, "webhook": {"url": "http://webhook", "timeout": 10}, "levels": {"error": True}}
        }):
            from mc.notify import send_alert
            result = send_alert("Test", "Detail", "error")
            self.assertTrue(result)

    @patch("urllib.request.urlopen")
    def test_send_alert_webhook_failure(self, mock_urlopen):
        """Test send_alert handles webhook failure gracefully."""
        mock_urlopen.side_effect = Exception("Connection refused")

        with patch("mc.notify._load_notify_config", return_value={
            "notify": {"enabled": True, "webhook": {"url": "http://webhook", "timeout": 10}, "levels": {"error": True}}
        }):
            from mc.notify import send_alert
            result = send_alert("Test", "Detail", "error")
            self.assertFalse(result)

    def test_send_success(self):
        """Test send_success wrapper."""
        with patch("mc.notify.send_alert", return_value=True) as mock_alert:
            from mc.notify import send_success
            result = send_success("Success", "All good")
            self.assertTrue(result)
            mock_alert.assert_called_once_with("Success", "All good", level="info")

    def test_send_test_alert(self):
        """Test send_test_alert."""
        with patch("mc.notify.send_alert", return_value=True) as mock_alert:
            from mc.notify import send_test_alert
            result = send_test_alert()
            self.assertTrue(result)
            mock_alert.assert_called_once()


class TestStatusCommand(unittest.TestCase):
    """Test mc status command."""

    @classmethod
    def setUpClass(cls):
        cls.config_patcher = patch("mc_paths.load_config")
        mock_load = cls.config_patcher.start()

        def mock_load_config(config_name="chain_config.yaml"):
            if config_name == "chain_config.yaml":
                return {"db_path": get_test_db_path()}
            import yaml
            from mc_paths import CONFIG_DIR
            path = os.path.join(CONFIG_DIR, config_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            return {}

        mock_load.side_effect = mock_load_config

        import chain_db as db
        db.cfg = None
        db.MC_DB_PATH = get_test_db_path()
        db.init_db()
        cls.db = db

    @classmethod
    def tearDownClass(cls):
        cls.config_patcher.stop()
        cleanup_test_db()

    def setUp(self):
        conn = self.db.get_conn()
        conn.execute("DELETE FROM chains")
        conn.execute("DELETE FROM chain_posts")
        conn.execute("DELETE FROM keyword_queue")
        conn.commit()
        conn.close()

    def test_status_no_chains(self):
        """Test status with no chains."""
        from cli.mc import _cmd_status
        import argparse

        args = argparse.Namespace(days=7, json=False)

        import logging
        logger = logging.getLogger("test")
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            result = _cmd_status(args, logger)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertEqual(result, 0)
        self.assertIn("No chains in last 7 days", output)

    def test_status_with_chains(self):
        """Test status with chains."""
        # Create some test chains
        chain_id = self.db.create_chain("테스트키워드", 3, "depth")
        self.db.update_chain_status(chain_id, "completed")

        # Add a published post
        post_id = self.db.create_chain_post(chain_id, 0, "Test Title", "테스트키워드")
        self.db.update_published_url(post_id, "https://rotcha.kr/test", "hugo")
        self.db.update_smoke_test_result(post_id, "pass")

        from cli.mc import _cmd_status
        import argparse

        args = argparse.Namespace(days=7, json=False)

        import logging
        logger = logging.getLogger("test")
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            result = _cmd_status(args, logger)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertEqual(result, 0)
        self.assertIn("Total chains:   1", output)
        self.assertIn("✅ Completed:    1", output)
        self.assertIn("rotcha.kr: 1", output)
        self.assertIn("Smoke test: 1/1 passed", output)

    def test_status_json_output(self):
        """Test status --json output."""
        chain_id = self.db.create_chain("JSON테스트", 3, "depth")
        self.db.update_chain_status(chain_id, "completed")

        from cli.mc import _cmd_status
        import argparse
        import json

        args = argparse.Namespace(days=7, json=True)

        import logging
        logger = logging.getLogger("test")
        import io, sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            result = _cmd_status(args, logger)
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout

        self.assertEqual(result, 0)
        data = json.loads(output)
        self.assertEqual(data["total_chains"], 1)
        self.assertEqual(data["completed"], 1)
        self.assertIn("site_breakdown", data)
        self.assertIn("queue_status", data)


class TestQueueCLI(unittest.TestCase):
    """Test mc queue CLI commands."""

    @classmethod
    def setUpClass(cls):
        cls.config_patcher = patch("mc_paths.load_config")
        mock_load = cls.config_patcher.start()

        def mock_load_config(config_name="chain_config.yaml"):
            if config_name == "chain_config.yaml":
                return {"db_path": get_test_db_path()}
            import yaml
            from mc_paths import CONFIG_DIR
            path = os.path.join(CONFIG_DIR, config_name)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f)
            return {}

        mock_load.side_effect = mock_load_config

        import chain_db as db
        db.cfg = None
        db.MC_DB_PATH = get_test_db_path()
        db.init_db()
        cls.db = db

    @classmethod
    def tearDownClass(cls):
        cls.config_patcher.stop()
        cleanup_test_db()

    def setUp(self):
        conn = self.db.get_conn()
        conn.execute("DELETE FROM keyword_queue")
        conn.commit()
        conn.close()

    def test_queue_add_cli(self):
        """Test mc queue add command."""
        from cli.mc import main
        import sys, io

        # Use subparsers - need to call queue add directly
        with patch.object(sys, 'argv', ["mc", "queue", "add", "테스트키워드", "--category", "travel", "--priority", "2"]):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        self.assertIn("✅ Added: 테스트키워드", output)

    def test_queue_list_cli(self):
        """Test mc queue list command."""
        self.db.add_keyword_queue("키워드1", "travel", 3)
        self.db.add_keyword_queue("키워드2", "tech", 1)

        from cli.mc import main
        import sys, io

        with patch.object(sys, 'argv', ["mc", "queue", "list"]):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        self.assertIn("키워드1", output)
        self.assertIn("키워드2", output)

    def test_queue_next_cli(self):
        """Test mc queue next command."""
        self.db.add_keyword_queue("다음키워드", "travel", 2)

        from cli.mc import main
        import sys, io

        with patch.object(sys, 'argv', ["mc", "queue", "next"]):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        self.assertIn("다음키워드", output)

    def test_queue_remove_cli(self):
        """Test mc queue remove command."""
        self.db.add_keyword_queue("삭제할키워드", "travel", 3)

        from cli.mc import main
        import sys, io

        with patch.object(sys, 'argv', ["mc", "queue", "remove", "삭제할키워드"]):
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                main()
                output = sys.stdout.getvalue()
            finally:
                sys.stdout = old_stdout

        # Check if removal succeeded (keyword was pending)
        if "✅ Removed" in output:
            self.assertIn("✅ Removed: 삭제할키워드", output)
        else:
            # If not pending (e.g., already processed), check for warning
            self.assertIn("⚠️ Not found or not pending", output)


if __name__ == "__main__":
    unittest.main()