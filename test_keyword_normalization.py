import logging
import sys


def test_cli_run_trims_trailing_space(monkeypatch):
    import cli.mc as mc

    captured = {}
    def fake_run(keyword, args, logger):
        captured["keyword"] = keyword
        return 0
    monkeypatch.setattr(mc, "_run_full", fake_run)
    monkeypatch.setattr(mc, "_cleanup_stale_pid_files", lambda: None)
    monkeypatch.setattr(mc, "_setup_logging", lambda: logging.getLogger("test-cli"))
    monkeypatch.setattr(sys, "argv", ["mc", "run", "남양주 물의 정원 ", "--dry-run"])

    assert mc.main() == 0
    assert captured["keyword"] == "남양주 물의 정원"


def test_cli_background_trims_trailing_space(monkeypatch):
    import cli.mc as mc

    captured = {}
    def fake_background(keyword, args, logger):
        captured["keyword"] = keyword
        return 0
    monkeypatch.setattr(mc, "_run_background", fake_background)
    monkeypatch.setattr(mc, "_cleanup_stale_pid_files", lambda: None)
    monkeypatch.setattr(mc, "_setup_logging", lambda: logging.getLogger("test-background"))
    monkeypatch.setattr(sys, "argv", ["mc", "run", "남양주 물의 정원 ", "--background"])

    assert mc.main() == 0
    assert captured["keyword"] == "남양주 물의 정원"


def test_derive_chain_trims_seed_before_classification(monkeypatch):
    import chain_deriver as deriver

    captured = {}
    def fake_resolve(seed, override=None):
        captured["resolved_seed"] = seed
        return "depth"
    def fake_classify(seed):
        captured["classified_seed"] = seed
        return "travel"
    monkeypatch.setattr(deriver, "resolve_chain_type", fake_resolve)
    monkeypatch.setattr(deriver, "classify_keyword", fake_classify)
    monkeypatch.setattr(deriver, "load_prompts", lambda: {"derive_system": "", "derive_user_depth": "{seed}"})
    monkeypatch.setattr(deriver, "generate", lambda **kwargs: {"content": '[{"title":"t"}]'})
    monkeypatch.setattr(deriver.db, "init_db", lambda: None)
    monkeypatch.setattr(deriver.db, "create_chain", lambda *args, **kwargs: 123)
    monkeypatch.setattr(deriver.db, "create_chain_post", lambda *args, **kwargs: 1)
    monkeypatch.setattr(deriver, "_print_chain_summary", lambda chain_id: None)

    assert deriver.derive_chain("남양주 물의 정원 ") == 123
    assert captured["resolved_seed"] == "남양주 물의 정원"
    assert captured["classified_seed"] == "남양주 물의 정원"
