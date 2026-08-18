"""Load blog contract YAMLs and validate posts against them."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from quality._types import ContractSpec, GateResult

_CONTRACTS_DIR = Path(__file__).resolve().parent.parent / "contracts"

SUPPORTED_CATEGORIES = frozenset({
    "product", "customer_service", "gov_finance",
    "shopping_brand", "golf_course", "medicine",
    "travel", "entertainment", "knowledge",
})


def load(blog_id: str, category: str | None = None) -> ContractSpec:
    """Load a ContractSpec from contracts/{blog_id}.yaml.

    If required_sections is a dict (category-keyed), select by *category*.
    Falls back to GateResult.FAIL if category is None or unsupported.
    If required_sections is a plain list, use it as-is (backward compat).
    """
    path = _CONTRACTS_DIR / f"{blog_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No contract for blog '{blog_id}': {path}")
    data = yaml.safe_load(path.read_text())

    required = data.get("required_sections", [])
    if isinstance(required, dict):
        if not category or category not in required:
            data["required_sections"] = []  # empty → validate_post will fail
        else:
            data["required_sections"] = required[category]

    return ContractSpec(blog_id=blog_id, **data)


def is_category_supported(category: str | None) -> bool:
    """Return True if category has contract support."""
    return category in SUPPORTED_CATEGORIES


def _extract_h2_headings(post_md: str) -> list[str]:
    """Return normalized H2 heading texts from markdown."""
    headings = []
    for line in post_md.splitlines():
        line = line.strip()
        if line.startswith("## ") and not line.startswith("### "):
            headings.append(line[3:].strip())
    return headings


def validate_post(post_md: str, contract: ContractSpec) -> GateResult:
    """Validate a markdown post against a ContractSpec.

    Returns GateResult with:
      - passed: True if no violations
      - violations: list of human-readable violation strings
      - score: 1.0 minus penalty per violation (floored at 0.0)
    """
    violations: list[str] = []

    # --- required sections ---
    headings = _extract_h2_headings(post_md)
    for section in contract.required_sections:
        if section not in headings:
            violations.append(f"Missing required section: '{section}'")

    # --- forbidden patterns ---
    for pattern in contract.forbidden_patterns:
        if re.search(pattern, post_md):
            violations.append(f"Forbidden pattern matched: '{pattern}'")

    # --- score: 1.0 minus 0.1 per violation, floor 0.0 ---
    score = max(0.0, 1.0 - 0.1 * len(violations))

    return GateResult(
        passed=len(violations) == 0,
        violations=violations,
        score=score,
    )
