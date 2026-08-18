"""Pre-research module for mc chain.

Collects facts about a keyword before drafting, producing a Factsheet
that can be injected into AI prompts to reduce hallucination.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data" / "factsheets"


@dataclass
class Fact:
    """A single verified or sourced fact."""
    claim: str
    source_url: str
    retrieved_date: str
    confidence: str = "medium"  # low | medium | high


@dataclass
class Factsheet:
    """Collection of facts about a keyword, gathered before drafting."""
    facts: list[Fact] = field(default_factory=list)
    keyword: str = ""
    researched_at: str = ""


def _extract_facts_from_results(results: list[dict], keyword: str) -> list[Fact]:
    """Extract structured facts from search results.

    Heuristic extraction: each search result becomes a Fact with its
    description as claim and URL as source.  Confidence is set to
    'medium' since these are unvalidated search snippets.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    facts: list[Fact] = []
    for item in results:
        desc = item.get("description", "").strip()
        link = item.get("link", "").strip()
        title = item.get("title", "").strip()
        claim = desc or title
        if not claim:
            continue
        facts.append(Fact(
            claim=claim,
            source_url=link,
            retrieved_date=today,
            confidence="medium",
        ))
    return facts


def research_keyword(keyword: str) -> Factsheet:
    """Research a keyword via Naver Search API and return a Factsheet.

    Uses the existing NaverSearchClient from search_retriever.
    On any failure (network, API, parse), returns an empty Factsheet
    and logs the error — never raises.
    """
    today = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        from search_retriever import NaverSearchClient
        client = NaverSearchClient()
        ok, data = client.search(keyword, endpoint="webkr", display=5)
        if not ok:
            logger.warning("[pre_researcher] Search failed: %s", data)
            return Factsheet(facts=[], keyword=keyword, researched_at=today)

        import json as _json
        parsed = _json.loads(data)
        items = parsed.get("items", [])
        # Strip HTML tags from descriptions
        for item in items:
            for key in ("title", "description"):
                if key in item:
                    item[key] = item[key].replace("<b>", "").replace("</b>", "")
        facts = _extract_facts_from_results(items, keyword)
        return Factsheet(facts=facts, keyword=keyword, researched_at=today)

    except Exception as e:
        logger.warning("[pre_researcher] research_keyword failed: %s", e)
        return Factsheet(facts=[], keyword=keyword, researched_at=today)


def save_factsheet(factsheet: Factsheet, chain_id: str) -> Path:
    """Persist a Factsheet to data/factsheets/{chain_id}.json."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{chain_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asdict(factsheet), f, ensure_ascii=False, indent=2)
    logger.info("[pre_researcher] Saved factsheet to %s", path)
    return path


def inject_factsheet_to_prompt(factsheet: Factsheet, base_prompt: str) -> str:
    """Prepend a formatted factsheet section to a base prompt.

    If facts are empty, inserts a warning instead.
    """
    if not factsheet.facts:
        return (
            "## 사전 리서치 결과\n\n"
            "사전 리서치 결과 없음. 확인되지 않은 수치/통계를 사용하지 마시오.\n\n"
            + base_prompt
        )

    lines = ["## 사전 리서치 결과", ""]
    for fact in factsheet.facts:
        lines.append(
            f"- {fact.claim} [출처: {fact.source_url}, {fact.retrieved_date}]"
        )
    lines.append("")
    return "\n".join(lines) + base_prompt
