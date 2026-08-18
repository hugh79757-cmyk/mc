"""Tests for quality.pre_researcher module."""

import json
import os
from dataclasses import asdict
from unittest.mock import patch, MagicMock

import pytest

from quality.pre_researcher import (
    Fact,
    Factsheet,
    _extract_facts_from_results,
    research_keyword,
    save_factsheet,
    inject_factsheet_to_prompt,
    DATA_DIR,
)


class TestFactsheetDataclass:
    """Factsheet/Fact creation and serialization."""

    def test_fact_creation(self):
        f = Fact(claim="test claim", source_url="https://example.com",
                 retrieved_date="2026-08-18", confidence="high")
        assert f.claim == "test claim"
        assert f.confidence == "high"

    def test_factsheet_defaults(self):
        fs = Factsheet()
        assert fs.facts == []
        assert fs.keyword == ""
        assert fs.researched_at == ""

    def test_factsheet_with_facts(self):
        f = Fact(claim="c1", source_url="http://a.com", retrieved_date="2026-01-01")
        fs = Factsheet(facts=[f], keyword="k", researched_at="now")
        assert len(fs.facts) == 1
        assert fs.facts[0].claim == "c1"

    def test_factsheet_serialization(self):
        f = Fact(claim="c", source_url="http://x.com", retrieved_date="2026-01-01")
        fs = Factsheet(facts=[f], keyword="k", researched_at="ts")
        d = asdict(fs)
        assert d["keyword"] == "k"
        assert len(d["facts"]) == 1
        assert d["facts"][0]["claim"] == "c"
        # JSON round-trip
        raw = json.dumps(d, ensure_ascii=False)
        loaded = json.loads(raw)
        fs2 = Factsheet(
            facts=[Fact(**fd) for fd in loaded["facts"]],
            keyword=loaded["keyword"],
            researched_at=loaded["researched_at"],
        )
        assert fs2.facts[0].claim == "c"


class TestInjectFactsheet:
    """inject_factsheet_to_prompt behavior."""

    def test_inject_empty_factsheet(self):
        fs = Factsheet(facts=[], keyword="t", researched_at="now")
        result = inject_factsheet_to_prompt(fs, "base prompt")
        assert "사전 리서치 결과 없음" in result
        assert "확인되지 않은 수치/통계를 사용하지 마시오" in result
        assert "base prompt" in result
        assert "## 사전 리서치 결과" in result

    def test_inject_with_facts(self):
        f1 = Fact(claim="address is X", source_url="http://a.com",
                  retrieved_date="2026-08-01")
        f2 = Fact(claim="hours are Y", source_url="http://b.com",
                  retrieved_date="2026-08-02")
        fs = Factsheet(facts=[f1, f2], keyword="k", researched_at="ts")
        result = inject_factsheet_to_prompt(fs, "PROMPT")
        assert "address is X" in result
        assert "[출처: http://a.com, 2026-08-01]" in result
        assert "hours are Y" in result
        assert "[출처: http://b.com, 2026-08-02]" in result
        assert result.endswith("PROMPT")

    def test_inject_preserves_order(self):
        facts = [
            Fact(claim="first", source_url="http://1.com", retrieved_date="d1"),
            Fact(claim="second", source_url="http://2.com", retrieved_date="d2"),
        ]
        fs = Factsheet(facts=facts, keyword="k", researched_at="ts")
        result = inject_factsheet_to_prompt(fs, "")
        idx_first = result.index("first")
        idx_second = result.index("second")
        assert idx_first < idx_second


class TestResearchKeyword:
    """research_keyword with mocked search API."""

    def test_research_keyword_mock(self):
        mock_items = [
            {"title": "<b>Place</b>", "description": "<b>Great place</b>",
             "link": "http://example.com"},
        ]
        mock_response = json.dumps({"items": mock_items})

        mock_client = MagicMock()
        mock_client.search.return_value = (True, mock_response)

        with patch("search_retriever.NaverSearchClient", return_value=mock_client):
            fs = research_keyword("test keyword")

        assert fs.keyword == "test keyword"
        assert len(fs.facts) == 1
        assert fs.facts[0].claim == "Great place"  # <b> tags stripped
        assert fs.facts[0].source_url == "http://example.com"
        assert fs.facts[0].confidence == "medium"

    def test_research_keyword_search_failure(self):
        mock_client = MagicMock()
        mock_client.search.return_value = (False, "API error")

        with patch("search_retriever.NaverSearchClient", return_value=mock_client):
            fs = research_keyword("bad keyword")

        assert fs.facts == []
        assert fs.keyword == "bad keyword"

    def test_research_keyword_network_error(self):
        with patch("search_retriever.NaverSearchClient",
                   side_effect=ConnectionError("timeout")):
            fs = research_keyword("timeout keyword")

        assert fs.facts == []
        assert fs.keyword == "timeout keyword"

    def test_research_keyword_empty_results(self):
        mock_client = MagicMock()
        mock_client.search.return_value = (True, '{"items":[]}')

        with patch("search_retriever.NaverSearchClient", return_value=mock_client):
            fs = research_keyword("empty keyword")

        assert fs.facts == []


class TestSaveFactsheet:
    """save_factsheet persistence."""

    def test_save_and_load(self, tmp_path):
        with patch("quality.pre_researcher.DATA_DIR", tmp_path):
            fs = Factsheet(
                facts=[Fact(claim="c", source_url="http://x.com",
                            retrieved_date="2026-01-01")],
                keyword="k", researched_at="ts"
            )
            path = save_factsheet(fs, "chain_99")

        assert path.exists()
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data["keyword"] == "k"
        assert len(data["facts"]) == 1
        assert data["facts"][0]["claim"] == "c"

    def test_save_creates_directory(self, tmp_path):
        target = tmp_path / "subdir"
        with patch("quality.pre_researcher.DATA_DIR", target):
            fs = Factsheet(facts=[], keyword="k", researched_at="ts")
            save_factsheet(fs, "chain_1")

        assert target.exists()


class TestExtractFacts:
    """_extract_facts_from_results helper."""

    def test_extracts_valid_items(self):
        items = [
            {"description": "desc1", "link": "http://a.com", "title": "t1"},
            {"description": "desc2", "link": "http://b.com", "title": "t2"},
        ]
        facts = _extract_facts_from_results(items, "kw")
        assert len(facts) == 2
        assert facts[0].claim == "desc1"
        assert facts[1].claim == "desc2"

    def test_skips_empty_items(self):
        items = [
            {"description": "", "link": "", "title": ""},
            {"description": "valid", "link": "http://x.com", "title": ""},
        ]
        facts = _extract_facts_from_results(items, "kw")
        assert len(facts) == 1

    def test_falls_back_to_title(self):
        items = [{"description": "", "link": "http://x.com", "title": "Title Only"}]
        facts = _extract_facts_from_results(items, "kw")
        assert len(facts) == 1
        assert facts[0].claim == "Title Only"
