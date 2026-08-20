"""Regression tests for MC root-seed identity preservation."""

from pathlib import Path


def test_chain_deriver_persists_root_seed_not_derived_target_keyword():
    source = Path(__file__).with_name("chain_deriver.py").read_text(encoding="utf-8")
    assert 'target_keyword=seed' in source
    assert 'target_keyword=post.get("target_keyword", "")' not in source


def test_related_angles_remain_allowed_in_title_fields():
    source = Path(__file__).with_name("chain_deriver.py").read_text(encoding="utf-8")
    assert 'title=post.get("title", "")' in source
    assert 'angle=post.get("angle", "")' in source
