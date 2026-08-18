"""Factuality checker for mc chain posts.

Extracts factual claims from markdown bodies, checks forbidden patterns,
and validates source attribution.  Used as a quality gate before publishing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from quality._types import ContractSpec

# ---------------------------------------------------------------------------
# Patterns for claim detection
# ---------------------------------------------------------------------------

_NUMBER_PATTERNS: list[str] = [
    r"\d+%",        # percentages
    r"\d+명",       # people count
    r"\d+만원",     # price in 만원
    r"\d+점",       # score/points
    r"만족도\s*\d+",  # satisfaction N
]

_REVIEW_PATTERNS: list[str] = [
    r"리뷰\s*데이터",
    r"후기\s*데이터",
    r"사용자\s*리뷰",
]

_STATISTICS_PATTERNS: list[str] = [
    r"데이터를\s*분석",
    r"설문\s*결과",
    r"조사\s*결과",
]

_SOURCE_TAG_RE = re.compile(r"\[출처:")

# All claim detection compiled patterns (pattern_list, claim_type_label)
_CLAIM_RULES: list[tuple[list[str], str]] = [
    (_NUMBER_PATTERNS, "number"),
    (_REVIEW_PATTERNS, "review"),
    (_STATISTICS_PATTERNS, "statistics"),
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Claim:
    """A factual claim extracted from markdown."""
    sentence: str
    claim_type: str
    has_source_tag: bool


@dataclass
class FactualityResult:
    """Outcome of a factuality validation pass."""
    score: float = 1.0
    unsourced_claims: list[str] = field(default_factory=list)
    forbidden_hits: list[str] = field(default_factory=list)
    passed: bool = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_sentences(text: str) -> list[str]:
    """Split markdown text into sentence-level chunks.

    Splits on sentence-ending punctuation (periods, exclamation marks,
    question marks) followed by whitespace or end-of-string.  Each chunk
    is stripped of leading/trailing whitespace.
    """
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def _has_source_tag(sentence: str) -> bool:
    """Return True if the sentence contains a [출처: ...] marker."""
    return bool(_SOURCE_TAG_RE.search(sentence))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_claims(body_md: str) -> list[Claim]:
    """Extract factual claims from a markdown body.

    A sentence is a "claim" if it matches any of the number, review,
    or statistics patterns.  Each claim records whether a [출처:] tag
    is present for source attribution.
    """
    sentences = _split_sentences(body_md)
    claims: list[Claim] = []

    for sentence in sentences:
        for patterns, claim_type in _CLAIM_RULES:
            for pat in patterns:
                if re.search(pat, sentence):
                    claims.append(Claim(
                        sentence=sentence,
                        claim_type=claim_type,
                        has_source_tag=_has_source_tag(sentence),
                    ))
                    break  # one match per claim_type is enough
            else:
                continue
            break  # sentence already claimed, skip other types

    return claims


def check_forbidden(body_md: str, patterns: list[str]) -> list[str]:
    """Return sentences that match any of the forbidden patterns."""
    sentences = _split_sentences(body_md)
    hits: list[str] = []
    for sentence in sentences:
        for pat in patterns:
            if re.search(pat, sentence):
                hits.append(sentence)
                break  # one match per sentence is enough
    return hits


def validate_factuality(
    body_md: str,
    contract: ContractSpec,
) -> FactualityResult:
    """Validate factuality of a markdown body against a contract.

    Scoring:
      score = sourced_claims / total_claims (1.0 if no claims).
      If score < 0.7 → passed=False.
      If any forbidden_hits → passed=False.
    """
    claims = extract_claims(body_md)
    total = len(claims)
    sourced = sum(1 for c in claims if c.has_source_tag)
    score = sourced / total if total else 1.0

    unsourced = [
        c.sentence for c in claims if not c.has_source_tag
    ]

    forbidden_hits = check_forbidden(body_md, contract.forbidden_patterns)

    passed = score >= 0.7 and not forbidden_hits

    return FactualityResult(
        score=score,
        unsourced_claims=unsourced,
        forbidden_hits=forbidden_hits,
        passed=passed,
    )
