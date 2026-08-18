"""Cross-blog deduplication and role element checker."""

from __future__ import annotations

import re
from itertools import combinations

from quality._types import ContractSpec, DedupResult, RoleResult
from quality.contract_loader import match_section


def split_sentences(body_md: str) -> list[str]:
    """Split markdown body into sentences.

    Handles markdown headers by stripping them first.
    Splits on sentence-ending punctuation including Korean equivalents.
    """
    # Strip markdown headers
    lines = []
    for line in body_md.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            # Remove header markers
            stripped = re.sub(r"^#+\s*", "", stripped)
        lines.append(stripped)

    text = " ".join(lines)

    # Split on sentence-ending punctuation
    # Korean: 한다., 했다., 합니다., 했습니다., etc.
    # English/General: . ! ?
    sentences = re.split(r"(?<=[.!?다요])\s+", text)

    # Filter empty sentences
    return [s.strip() for s in sentences if s.strip()]


def _get_ngrams(tokens: list[str], n: int = 3) -> set[tuple[str, ...]]:
    """Generate n-grams from a list of tokens."""
    if len(tokens) < n:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def calc_similarity(sents_a: list[str], sents_b: list[str]) -> float:
    """Calculate 3-gram Jaccard similarity between two sentence lists.

    No external libraries required.
    """
    if not sents_a or not sents_b:
        return 0.0

    # Tokenize by whitespace
    tokens_a = []
    for sent in sents_a:
        tokens_a.extend(sent.split())

    tokens_b = []
    for sent in sents_b:
        tokens_b.extend(sent.split())

    ngrams_a = _get_ngrams(tokens_a, 3)
    ngrams_b = _get_ngrams(tokens_b, 3)

    if not ngrams_a or not ngrams_b:
        return 0.0

    intersection = ngrams_a & ngrams_b
    union = ngrams_a | ngrams_b

    return len(intersection) / len(union) if union else 0.0


SIMILARITY_THRESHOLD = 0.30


def check_cross_blog_dedup(posts: dict[str, str]) -> DedupResult:
    """Check cross-blog deduplication across 3 posts.

    Args:
        posts: Dict mapping blog_id to markdown body.
               Expected keys: rotcha, issue_techpawz, techpawz

    Returns:
        DedupResult with passed=True if no pair exceeds threshold.
    """
    blog_ids = sorted(posts.keys())
    pair_scores: dict[str, float] = {}
    violations: list[str] = []

    for id_a, id_b in combinations(blog_ids, 2):
        sents_a = split_sentences(posts[id_a])
        sents_b = split_sentences(posts[id_b])
        score = calc_similarity(sents_a, sents_b)
        pair_key = f"{id_a} vs {id_b}"
        pair_scores[pair_key] = score

        if score > SIMILARITY_THRESHOLD:
            violations.append(
                f"High similarity ({score:.2f}) between {id_a} and {id_b}"
            )

    return DedupResult(
        passed=len(violations) == 0,
        pair_scores=pair_scores,
        violations=violations,
    )


def check_role_elements(
    blog_id: str, body_md: str, contract: ContractSpec
) -> RoleResult:
    """Check if a blog post contains required role elements.

    Args:
        blog_id: The blog identifier
        body_md: Markdown body content
        contract: ContractSpec with required_sections

    Returns:
        RoleResult with missing and extra sections.
    """
    # Extract H2 headings from body
    headings: list[str] = []
    for line in body_md.splitlines():
        line = line.strip()
        if line.startswith("## ") and not line.startswith("### "):
            headings.append(line[3:].strip())

    # Check required sections (fuzzy match)
    missing: list[str] = []
    for section in contract.required_sections:
        matched, _method = match_section(section, headings)
        if not matched:
            missing.append(section)

    # No extra sections check needed per plan (extra_sections always empty)
    extra: list[str] = []

    return RoleResult(
        passed=len(missing) == 0,
        missing_sections=missing,
        extra_sections=extra,
    )
