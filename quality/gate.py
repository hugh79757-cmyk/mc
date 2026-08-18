"""Quality gate — runs all quality checks and returns a publish verdict."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from quality._types import ContractSpec, DedupResult
from quality.contract_loader import load as load_contract, validate_post
from quality.cross_blog_checker import check_cross_blog_dedup, check_role_elements
from quality.factuality_checker import validate_factuality
from quality.html_render_checker import check_html_duplicates
from quality.scorer import QualityScore, calculate_score
from quality.title_body_checker import validate_title_body


@dataclass
class GateVerdict:
    """Result of the quality gate check."""

    action: str = "reject"  # "publish" | "review" | "reject"
    scores: dict = field(default_factory=dict)
    violations: dict = field(default_factory=dict)
    total_score: float = 0.0


# Thresholds
REJECT_THRESHOLD = 7.0
REVIEW_THRESHOLD = 9.0


def run_all_checks(
    chain_id: str,
    posts: dict[str, dict],
) -> GateVerdict:
    """Run all quality checks across 3 blog posts.

    Args:
        chain_id: Chain identifier (for logging).
        posts: Dict mapping blog_id to post data.
               Each value must have: title, body_md, html.
               Expected keys: rotcha, issue_techpawz, techpawz.

    Returns:
        GateVerdict with action, scores, and violations.
    """
    # Skip gate if env var is set
    if os.environ.get("MC_SKIP_QUALITY_GATE") == "1":
        return GateVerdict(
            action="publish",
            scores={"skipped": True},
            violations={},
            total_score=10.0,
        )

    all_violations: dict[str, list[str]] = {}
    per_blog_scores: dict[str, dict] = {}

    # ── Load contracts for each blog ──
    # Map blog_id to contract file name (issue.techpawz → issue_techpawz)
    _CONTRACT_MAP = {"issue.techpawz": "issue_techpawz"}
    contracts: dict[str, ContractSpec] = {}
    for blog_id in posts:
        contract_id = _CONTRACT_MAP.get(blog_id, blog_id)
        try:
            contracts[blog_id] = load_contract(contract_id)
        except FileNotFoundError:
            all_violations.setdefault(blog_id, []).append(
                f"Missing contract file for '{blog_id}'"
            )

    # ── Per-blog checks ──
    role_results: dict[str, object] = {}
    for blog_id, post_data in posts.items():
        title = post_data.get("title", "")
        body_md = post_data.get("body_md", "")
        html = post_data.get("html", "")
        contract = contracts.get(blog_id)

        if not contract:
            per_blog_scores[blog_id] = {"skipped": True}
            continue

        # 1. Contract validation
        contract_result = validate_post(body_md, contract)

        # 2. Title-body consistency
        title_body_result = validate_title_body(title, body_md)

        # 3. Factuality check
        factuality_result = validate_factuality(body_md, contract)

        # 4. Role elements check
        role_result = check_role_elements(blog_id, body_md, contract)
        role_results[blog_id] = role_result

        # 5. HTML duplicate check
        html_result = check_html_duplicates(html, contract)

        # Dummy dedup result (will be replaced by cross-blog check)
        dedup_placeholder = DedupResult(passed=True)

        # Calculate score for this blog
        score = calculate_score(
            contract_result, title_body_result, factuality_result,
            dedup_placeholder, role_result, html_result,
        )

        per_blog_scores[blog_id] = {
            "contract": score.contract_score,
            "factuality": score.factuality_score,
            "role": score.role_score,
            "visual": score.visual_score,
            "total": score.total,
        }

        # Collect violations
        if score.violations:
            all_violations.setdefault(blog_id, []).extend(score.violations)

    # ── Cross-blog dedup check (all 3 at once) ──
    body_map = {bid: p.get("body_md", "") for bid, p in posts.items()}
    dedup_result = check_cross_blog_dedup(body_map)

    if dedup_result.violations:
        all_violations.setdefault("cross_blog", []).extend(
            dedup_result.violations
        )

    # ── Calculate aggregate score ──
    # Average across blogs for the total
    blog_totals = [
        s["total"] for s in per_blog_scores.values() if "total" in s
    ]
    avg_total = sum(blog_totals) / len(blog_totals) if blog_totals else 0.0

    # Dedup penalty on aggregate
    if not dedup_result.passed:
        avg_total = max(0.0, avg_total - 1.0)

    # ── Determine action ──
    if avg_total < REJECT_THRESHOLD:
        action = "reject"
    elif avg_total < REVIEW_THRESHOLD:
        action = "review"
    else:
        action = "publish"

    return GateVerdict(
        action=action,
        scores=per_blog_scores,
        violations=all_violations,
        total_score=round(avg_total, 2),
    )
