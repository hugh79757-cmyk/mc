"""Tests for chain_db.py - SQLite chain database."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_db_path(temp_dir):
    """Override db path to temp dir and init DB."""
    db_path = temp_dir / "test.db"

    import chain_db as db_mod
    import mc_paths

    # Save originals
    orig_get_cfg = db_mod._get_cfg

    # Override config
    from mc_paths import load_config
    test_config = load_config()
    test_config["db_path"] = str(db_path)
    mc_paths.MC_DB_PATH = str(db_path)

    # Force reload
    db_mod.cfg = None
    db_mod._get_cfg = lambda: test_config

    # Init with new path
    db_mod.init_db()
    db_mod.init_loop_tables()

    yield str(db_path)

    # Restore
    db_mod._get_cfg = orig_get_cfg
    mc_paths.MC_DB_PATH = load_config().get("db_path")


class TestChainDB:
    """Test chain_db module functions."""

    def test_init_db_creates_tables(self, temp_db_path):
        """Test database initialization creates all tables."""
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "chains" in tables
        assert "chain_posts" in tables
        assert "publish_log" in tables

    def test_create_chain(self, temp_db_path):
        """Test creating a new chain."""
        from chain_db import create_chain, get_chain

        chain_id = create_chain("테스트 키워드", depth_count=3, chain_type="depth")
        assert isinstance(chain_id, int)
        assert chain_id > 0

        chain = get_chain(chain_id)
        assert chain["seed"] == "테스트 키워드"
        assert chain["chain_type"] == "depth"
        assert chain["status"] == "derived"

    def test_create_chain_post(self, temp_db_path):
        """Test creating a single post."""
        from chain_db import create_chain, create_chain_post, get_chain_posts

        chain_id = create_chain("테스트", chain_type="depth")
        post_id = create_chain_post(
            chain_id=chain_id,
            depth=0,
            title="기초",
            target_keyword="키워드",
            category_guess="기술",
        )

        posts = get_chain_posts(chain_id)
        assert len(posts) == 1
        assert posts[0]["title"] == "기초"
        assert posts[0]["target_keyword"] == "키워드"

    def test_update_post_draft(self, temp_db_path):
        """Test updating post draft markdown."""
        from chain_db import create_chain, create_chain_post, update_post_draft, get_chain_posts

        chain_id = create_chain("테스트", chain_type="depth")
        create_chain_post(chain_id, 0, "테스트", target_keyword="키워드")
        posts = get_chain_posts(chain_id)
        post_id = posts[0]["id"]

        draft_md = "---\ntitle: Test\ndraft: true\n---\n\nContent"
        update_post_draft(post_id, draft_md, "test-slug")

        updated = get_chain_posts(chain_id)[0]
        assert updated["draft_md"] == draft_md
        assert updated["slug"] == "test-slug"

    def test_update_post_image(self, temp_db_path):
        """Test updating post image URL."""
        from chain_db import create_chain, create_chain_post, update_post_image, get_chain_posts

        chain_id = create_chain("테스트", chain_type="depth")
        create_chain_post(chain_id, 0, "테스트", target_keyword="키워드")
        posts = get_chain_posts(chain_id)
        post_id = posts[0]["id"]

        update_post_image(post_id, "/images/test.jpg")
        updated = get_chain_posts(chain_id)[0]
        assert updated["image_url"] == "/images/test.jpg"

    def test_update_chain_status(self, temp_db_path):
        """Test chain status transitions."""
        from chain_db import create_chain, get_chain, update_chain_status

        chain_id = create_chain("테스트", chain_type="depth")
        update_chain_status(chain_id, "drafting")
        chain = get_chain(chain_id)
        assert chain["status"] == "drafting"

        update_chain_status(chain_id, "published")
        chain = get_chain(chain_id)
        assert chain["status"] == "published"

    def test_get_chain_posts_ordered(self, temp_db_path):
        """Test getting posts in order."""
        from chain_db import create_chain, create_chain_post, get_chain_posts_ordered

        chain_id = create_chain("테스트", chain_type="depth")
        for step, title, kw in [
            (3, "3단계", "k3"), (1, "1단계", "k1"), (2, "2단계", "k2")
        ]:
            create_chain_post(chain_id, step - 1, title, target_keyword=kw)

        asc = get_chain_posts_ordered(chain_id, "asc")
        desc = get_chain_posts_ordered(chain_id, "desc")
        assert [p["step"] for p in asc] == [1, 2, 3]
        assert [p["step"] for p in desc] == [3, 2, 1]

    def test_check_duplicate(self, temp_db_path):
        """Test duplicate detection."""
        from chain_db import check_duplicate, log_publish

        assert check_duplicate("blog1", "slug1") is False
        log_publish("blog1", "slug1", "https://example.com/post", "hugo")
        assert check_duplicate("blog1", "slug1") is True

    def test_log_publish(self, temp_db_path):
        """Test publish logging."""
        from chain_db import log_publish

        log_publish("blog1", "slug1", "https://example.com/post", "hugo")

        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM publish_log WHERE blog_id=? AND slug=?", ("blog1", "slug1"))
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[3] == "https://example.com/post"  # url
        assert row[4] == "hugo"  # method

    def test_update_published_url(self, temp_db_path):
        """Test updating published URL on post."""
        from chain_db import create_chain, create_chain_post, update_published_url, get_chain_posts

        chain_id = create_chain("테스트", chain_type="depth")
        create_chain_post(chain_id, 0, "테스트", target_keyword="키워드")
        posts = get_chain_posts(chain_id)
        post_id = posts[0]["id"]

        update_published_url(post_id, "https://example.com/post", "hugo")
        updated = get_chain_posts(chain_id)[0]
        assert updated["published_url"] == "https://example.com/post"

    def test_update_thumbnail(self, temp_db_path):
        """Test thumbnail path update."""
        from chain_db import create_chain, create_chain_post, update_thumbnail, get_chain_posts

        chain_id = create_chain("테스트", chain_type="depth")
        create_chain_post(chain_id, 0, "테스트", target_keyword="키워드")
        posts = get_chain_posts(chain_id)
        post_id = posts[0]["id"]

        update_thumbnail(post_id, "/path/to/thumb.webp", "unsplash")
        updated = get_chain_posts(chain_id)[0]
        assert updated["thumbnail_path"] == "/path/to/thumb.webp"
        assert updated["thumbnail_source"] == "unsplash"

    def test_loop_chain_operations(self, temp_db_path):
        """Test loop chain CRUD."""
        from chain_db import create_chain, insert_loop_chain, get_loop_chain, update_loop_chain_status

        chain_id = create_chain("루프 테스트", chain_type="depth")
        loop_id = insert_loop_chain(chain_id, "hub-slug")
        assert loop_id > 0

        loop = get_loop_chain(chain_id)
        assert loop is not None
        assert loop["hub_slug"] == "hub-slug"
        assert loop["status"] == "hub_pending"

        update_loop_chain_status(loop_id, hub_url="https://rotcha.kr/hub/hub-slug/", status="hub_published")
        loop = get_loop_chain(chain_id)
        assert loop["hub_url"] == "https://rotcha.kr/hub/hub-slug/"
        assert loop["status"] == "hub_published"

    def test_card_injection_tracking(self, temp_db_path):
        """Test card injection status tracking."""
        from chain_db import create_chain, create_chain_post, update_card_injected, get_chain_posts

        chain_id = create_chain("테스트", chain_type="depth")
        create_chain_post(chain_id, 0, "1단계", target_keyword="k1")
        create_chain_post(chain_id, 1, "2단계", target_keyword="k2")

        posts = get_chain_posts(chain_id)
        post1_id = posts[0]["id"]
        post2_id = posts[1]["id"]

        assert get_chain_posts(chain_id)[0].get("card_injected") != 1
        update_card_injected(post1_id)

        posts = get_chain_posts(chain_id)
        assert posts[0]["card_injected"] == 1