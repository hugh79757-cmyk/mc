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

# Default threshold for fuzzy section matching
DEFAULT_FUZZY_THRESHOLD = 0.5


def match_section(
    contract_section: str,
    headings: list[str],
    threshold: float = DEFAULT_FUZZY_THRESHOLD,
) -> tuple[bool, str]:
    """Match a contract section name against actual H2 headings.

    Returns (matched: bool, method: str) where method is
    "exact", "contains", "fuzzy", or "none".
    """
    # 1. Exact match
    if contract_section in headings:
        return True, "exact"

    # 2. Contains match (either direction, case-insensitive)
    cs_lower = contract_section.lower()
    for h in headings:
        h_lower = h.lower()
        if cs_lower in h_lower or h_lower in cs_lower:
            return True, "contains"

    # 3. Normalized contains: normalize delimiters, then contains
    cs_norm = re.sub(r'[/·,]', ' ', cs_lower).strip()
    for h in headings:
        h_norm = re.sub(r'[/·,]', ' ', h.lower()).strip()
        if cs_norm in h_norm or h_norm in cs_norm:
            return True, "contains"

    # 4. Keyword overlap (tokenize + strip Korean particles)
    cs_tokens = _fuzzy_tokens(cs_lower)
    for h in headings:
        h_tokens = _fuzzy_tokens(h.lower())
        if not cs_tokens or not h_tokens:
            continue
        overlap = len(cs_tokens & h_tokens)
        union = len(cs_tokens | h_tokens)
        if union > 0 and overlap / union >= threshold:
            return True, "fuzzy"

    return False, "none"


# Korean particles/suffixes to strip for fuzzy matching
_PARTICLES = frozenset({
    "와", "과", "의", "를", "을", "은", "는", "이", "가",
    "로", "에", "도", "만", "부터", "까지", "와", "한", "된",
    "와", "や", "と", "で", "の", "に", "も",
})


def _fuzzy_tokens(text: str) -> set[str]:
    """Tokenize text, strip common Korean particles."""
    raw = re.split(r'[\s/·,]+', text)
    tokens = set()
    for t in raw:
        if len(t) <= 1:
            continue
        # Strip trailing particle
        for p in sorted(_PARTICLES, key=len, reverse=True):
            if t.endswith(p) and len(t) - len(p) >= 2:
                t = t[: -len(p)]
                break
        if t:
            tokens.add(t)
    return tokens


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

    # --- required sections (fuzzy match) ---
    headings = _extract_h2_headings(post_md)
    for section in contract.required_sections:
        matched, method = match_section(section, headings)
        if not matched:
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
