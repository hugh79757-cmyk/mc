"""Quality scorer — aggregates results from all quality modules into a single score."""

from __future__ import annotations

from dataclasses import dataclass, field

from quality._types import DedupResult, GateResult, RoleResult
from quality.factuality_checker import FactualityResult
from quality.html_render_checker import HtmlCheckResult
from quality.title_body_checker import TitleBodyResult


@dataclass
class QualityScore:
    """Aggregated quality score for a blog post."""

    contract_score: float = 0.0
    factuality_score: float = 0.0
    role_score: float = 0.0
    visual_score: float = 0.0
    total: float = 0.0
    breakdown: dict = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)


def calculate_score(
    contract_result: GateResult,
    title_body_result: TitleBodyResult,
    factuality_result: FactualityResult,
    dedup_result: DedupResult,
    role_result: RoleResult,
    html_result: HtmlCheckResult,
) -> QualityScore:
    """Calculate a weighted quality score from all check results.

    Weights:
      contract  = 0.40  (contract_result * 0.5 + title_body_result * 0.5) * 10
      factuality = 0.25  factuality_result.score * 10
      role      = 0.20  (dedup penalty + role fulfillment) * 10
      visual    = 0.15  html pass/fail * 10 with violation penalty
    """
    violations: list[str] = []

    # ── contract (0~10) ──
    contract_raw = contract_result.score * 0.5 + title_body_result.score * 0.5
    contract_score = contract_raw * 10.0

    # ── factuality (0~10) ──
    factuality_score = factuality_result.score * 10.0

    # ── role (0~10) ──
    # dedup penalty: 1.0 if passed, 0.5 if violated
    dedup_penalty = 1.0 if dedup_result.passed else 0.5
    # role fulfillment: 1.0 if no missing sections, else partial
    role_fulfillment = 1.0 if role_result.passed else 0.5
    role_score = (dedup_penalty + role_fulfillment) / 2.0 * 10.0

    # ── visual (0~10) ──
    visual_score = 10.0 if html_result.passed else 5.0
    # violation penalty: -1 per violation, min 0
    if html_result.violations:
        penalty = len(html_result.violations)
        visual_score = max(0.0, visual_score - penalty)

    # ── total (weighted sum) ──
    total = (
        contract_score * 0.40
        + factuality_score * 0.25
        + role_score * 0.20
        + visual_score * 0.15
    )

    # ── collect violations ──
    violations.extend(contract_result.violations)
    violations.extend(
        f"unmet promise: {p}" for p in title_body_result.unmet_promises
    )
    if not factuality_result.passed:
        violations.extend(
            f"unsourced claim: {c}" for c in factuality_result.unsourced_claims
        )
    violations.extend(factuality_result.forbidden_hits)
    violations.extend(dedup_result.violations)
    if not role_result.passed:
        violations.extend(
            f"missing role section: {s}" for s in role_result.missing_sections
        )
    violations.extend(html_result.violations)

    breakdown = {
        "contract": round(contract_score, 2),
        "factuality": round(factuality_score, 2),
        "role": round(role_score, 2),
        "visual": round(visual_score, 2),
        "weights": {"contract": 0.40, "factuality": 0.25, "role": 0.20, "visual": 0.15},
    }

    return QualityScore(
        contract_score=round(contract_score, 2),
        factuality_score=round(factuality_score, 2),
        role_score=round(role_score, 2),
        visual_score=round(visual_score, 2),
        total=round(total, 2),
        breakdown=breakdown,
        violations=violations,
    )
